# -*- coding: utf-8 -*-

import datetime
import logging
import os

from django.contrib import admin, messages
from django.core.files.base import File
from django.core.urlresolvers import reverse
from django.db import connections
from django.contrib.admin.options import ModelAdmin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from openode.document import tasks
from openode.document.client import document_api_client
from openode.document.models import Document, DocumentRevision, Page

################################################################################


class DocumentAdmin(ModelAdmin):
    # list_display = ("uuid", "run", "text")
    # readonly_fields = ("run", "img")
    # fields = ("doc", "text", "run")

#     def __init__(self, *args, **kwargs):
#         super(DocumentAdmin, self).__init__(*args, **kwargs)

#     def img(self, obj):
#         return ""

#     def run(self, obj):
#         return "<a href='/admin/test_document/document/run/%s/'>run - %s</a>" % (obj.pk, obj.uuid)
#     run.short_description = "Run"
#     run.allow_tags = True

    def get_urls(self):
        """
            add extra admin views
        """
        from django.conf.urls.defaults import patterns, url
        return patterns('',
            url(r'^state/$', self.admin_site.admin_view(self.state), name='document_state'),

            url(r'^joachim/$', self.admin_site.admin_view(self.joachim), name='document_joachim'),
            url(r'^joachim/(?P<pk>\d+)/$', self.admin_site.admin_view(self.joachim_one), name='document_joachim_one'),

            url(r'^retrive-text/$', self.admin_site.admin_view(self.retrive_text), name='document_retrive_text'),
            url(r'^retrive-text/(?P<pk>\d+)/$', self.admin_site.admin_view(self.retrive_text_one), name='document_retrive_text_one'),

            url(r'^re-queue/(?P<qd_pk>\d+)/$', self.admin_site.admin_view(self.re_queue), name='re_queue'),
            url(r'^clean-queue/(?P<pk>\d+)/$', self.admin_site.admin_view(self.clean_queue), name='clean_queue'),
        ) + super(DocumentAdmin, self).get_urls()

    ###################################
    # views
    ###################################

    def state(self, request):
        """
            overview page
        """

        qs = self.get_invalid_documents_qs()

        try:
            mayan_state = document_api_client.proxy.get_documents_in_queue()
            mayan_communication_error = None
        except Exception, e:
            mayan_state = None
            mayan_communication_error = e

        to_tmpl = {
            "documents_total": Document.objects.count(),
            "documents_with_error_count": qs.count(),
            "documents_with_error": qs,

            "documents_with_error_with_file": self.get_invalid_documents_with_file(qs),
            "documents_with_error_with_file_count": len(self.get_invalid_documents_with_file(qs)),

            "mayan_state": mayan_state,
            "mayan_communication_error": mayan_communication_error
        }
        return render(request, 'admin/document/state.html', to_tmpl)

    def joachim(self, request):
        """
            create celery tasks for retrive complete content of document from Mayan
        """
        limit = request.GET.get("limit")
        if limit and str(limit).isdigit():
            limit = int(limit)

        documents_with_no_pages = self.get_invalid_documents_qs()

        i = 0
        for document in documents_with_no_pages.iterator():
            if os.path.exists(document.latest_revision.file_data.path):
                document_revision = document.latest_revision
                document.revisions.create(**{
                    "file_data": File(
                        open(document_revision.file_data.path),
                        name=document_revision.get_file_name()
                        ),
                    'approved': document_revision.approved,
                    'revised_at': datetime.datetime.now(),
                    'summary': document_revision.summary,
                    'suffix': document_revision.suffix,
                    'original_filename': document_revision.original_filename,
                    'filename_slug': document_revision.filename_slug,
                    'author_id': document_revision.author_id,
                    'has_preview': document_revision.has_preview,
                })
                i += 1
                if limit and limit <= i:
                    break

        messages.info(request, u"%s documents has added to reprocess queue." % i)

        return HttpResponseRedirect(reverse("admin:document_state"))

    def joachim_one(self, request, pk):
        """
            create celery tasks for retrive complete content of one document from Mayan
        """

        document = get_object_or_404(Document, pk=pk)

        if os.path.exists(document.latest_revision.file_data.path):
            document_revision = document.latest_revision
            document.revisions.create(**{
                "file_data": File(
                    open(document_revision.file_data.path),
                    name=document_revision.get_file_name()
                    ),
                'approved': document_revision.approved,
                'revised_at': datetime.datetime.now(),
                'summary': document_revision.summary,
                'suffix': document_revision.suffix,
                'original_filename': document_revision.original_filename,
                'filename_slug': document_revision.filename_slug,
                'author_id': document_revision.author_id,
                'has_preview': document_revision.has_preview,
            })

            messages.info(request, u"Document (pk=%s) has added to reprocess queue." % document.pk)

        return HttpResponseRedirect(reverse("admin:document_state"))

    def re_queue(self, request, qd_pk):
        res = document_api_client.proxy.requeue(qd_pk)
        if res["success"]:
            messages.info(request, u"Re-queue success")
        else:
            messages.error(request, u"Re-queue error: %s" % res["error"])

        return HttpResponseRedirect(reverse("admin:document_state"))

    def retrive_text(self, request):
        """
            create celery tasks for retrive (only) text from Mayan
        """

        limit = request.GET.get("limit")
        qs = self.get_invalid_documents_qs()
        if limit and str(limit).isdigit():
            qs = qs[:int(limit)]

        pi = 0
        di = len(qs)

        page_pks = Page.objects.filter(
            document_revision__document__id__in=qs.values_list("pk", flat=True)
        ).values_list("pk", flat=True)

        for page_pk in page_pks:
            tasks.process_page.delay(page_pk)
            pi += 1

        messages.info(request, u"%s documents (%s pages) has added to queue for retrive text." % (di, pi))
        return HttpResponseRedirect(reverse("admin:document_state"))

    def retrive_text_one(self, request, pk):
        """
            create celery tasks for retrive (only) text from Mayan
        """
        document = get_object_or_404(Document, pk=pk)
        page_pks = Page.objects.filter(document_revision__document=document).values_list("pk", flat=True)
        for page_pk in page_pks:
            tasks.process_page.delay(page_pk)
        messages.info(request, u"Documents (pk=%s) has added to queue for retrive text." % document.pk)
        return HttpResponseRedirect(reverse("admin:document_state"))

    def clean_queue(self, request, pk):
        """
            clean Mayan OCR queue
        """
        e = None
        try:
            state = document_api_client.proxy.clean_queue(pk)
            if (state["success"] is False):
                e = state["error"]
            else:
                messages.info(request, u"Queue has been cleaned.")
        except Exception, e:
            pass
        finally:
            if e:
                messages.error(request, u"Error during clean queue: %s" % e)

        return HttpResponseRedirect(reverse("admin:document_state"))

    ###################################
    # helpers
    ###################################

    def get_invalid_documents_qs(self):
        """
            return document QuerySet with no OCR bugs
        """
        sql = """SELECT
                latest_revisions.document_id AS document_id
            FROM
                "document_page"
                RIGHT JOIN
                (SELECT
                        dr.id,
                        dr.document_id
                    FROM "document_document" d
                    JOIN "document_documentrevision" dr ON ( dr."document_id"=d.id )
                    WHERE (d.id, dr.revision) = (
                        SELECT document_id, MAX(revision)
                        FROM "document_documentrevision"
                        WHERE
                            "document_documentrevision".document_id=d.id
                            AND
                            "document_documentrevision".suffix NOT IN (%s)
                        GROUP BY "document_id"
                    )
                ) latest_revisions
                ON (
                    "document_page".document_revision_id=latest_revisions.id
                    AND
                    NOT "document_page"."plaintext" IN ('', '-- ? --')
                )
            GROUP BY
                latest_revisions.document_id
            HAVING COUNT(document_page.id) = 0
        """

        cursor = connections["default"].cursor()
        cursor.execute(
            # sorry, I have no more time for solving best formatting
            sql % ','.join(["'zip'", "'rar'"])
            )
        ret = cursor.fetchall()

        return Document.objects.filter(pk__in=[r[0] for r in ret])

    def get_invalid_documents_with_file(self, qs=None):
        """
            return documents objects with existing file
        """
        qs = qs or self.get_invalid_documents_qs()

        docs = []
        for document in qs:
            if os.path.exists(document.latest_revision.file_data.path):
                docs.append(document)
        return docs


#     def run_req(self, request, obj_pk):

#         document = get_object_or_404(Document, pk=obj_pk)
#         # status = self.openode_client.api.upload_document(
#         #     open(document.doc.path, "r").read(),
#         #     document.uuid
#         # )

#         # print self.openode_client.retrive_thumbnails_wrapper(document.uuid, "/tmp")

#         text = self.openode_client.api.retrive_plaintext(document.uuid)
#         # print text
#         document.text = text
#         document.save()

#         return HttpResponseRedirect('/admin/test_document/document/%s/' % document.pk)


class PageInlineAdmin(admin.TabularInline):
    model = Page

    extra = 0
    fields = ("number", "plaintext", "thumbnail_link")
    readonly_fields = ("thumbnail_link",)

    def thumbnail_link(self, obj):
        return obj.get_thumbnail_path()


class DocumentRevisionAdmin(ModelAdmin):
    inlines = [
        PageInlineAdmin
    ]


admin.site.register(Document, DocumentAdmin)
admin.site.register(DocumentRevision, DocumentRevisionAdmin)
# admin.site.register(Page)#, DocumentAdmin)
