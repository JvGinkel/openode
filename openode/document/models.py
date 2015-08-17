# -*- coding: utf-8 -*-

# from uuid import uuid4
import logging
import os
import shutil
from uuid import uuid4

from Pyro4.errors import CommunicationError

# from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Max  # , signals
from django.utils.translation import ugettext as _

from openode.document.client import document_api_client
from openode.document.storage import DocumentStorage
from openode.utils.path import sanitize_file_name
from openode.utils.file_utils import format_size
from openode.utils.text import get_urllist_from_text
from openode.models.base import BaseQuerySetManager
from django.db.models.query import QuerySet

from django.conf import settings

# import magic

################################################################################

DOCUMENT_PAGE_CONTENT_IF_ERROR = "-- ? --"

ICON_PATH = "default/media/images/fileicons/%s.png"
FALLBACK_ICON = "file"

################################################################################


class BaseModel(models.Model):

    class Meta:
        abstract = True

################################################################################


class DocumentQuerySet(QuerySet):

    def public(self):
        return self.filter(is_deleted=False)


#######################################

class DocumentManager(BaseQuerySetManager):

    def get_query_set(self):
        return DocumentQuerySet(self.model, using=self._db)


class AllDocumentManager(BaseQuerySetManager):
    pass

#######################################


class Document(BaseModel):
    """
        TODO
    """
    thread = models.ForeignKey("openode.Thread", null=True, blank=True,
        verbose_name=u"Thread", related_name="documents", unique=True,
        )
    plain_text = models.TextField(null=True, blank=True)
    html = models.TextField(null=True, blank=True)
    author = models.ForeignKey("auth.User", related_name='documents')
    is_deleted = models.BooleanField(default=False, verbose_name=_(u'Is deleted'))

    objects = DocumentManager()
    all_objects = AllDocumentManager()

    class Meta:
        verbose_name = _(u"Document")
        verbose_name_plural = _(u"Documents")

    def __unicode__(self):
        return "Document: %s" % repr({"thread": self.thread.pk, "pk": self.pk})

    @property
    def latest_revision(self):
        try:
            return self.revisions.order_by("-revision")[:1][0]
        except IndexError:
            return None

    # def get_file_type(self):
    #     return magic.from_file(self.latest_revision.file_data.path, mime=True)

    def preview(self):
        """
            return image url
        """
        return self.latest_revision.preview()

    def get_file_name(self):
        return self.latest_revision.get_file_name()

    def get_file_url(self):
        return self.latest_revision.file_data.url

    def get_pages(self, page_number=None):
        if not self.latest_revision:
            return Page.objects.none()

        qs = self.latest_revision.pages.all()
        if page_number:
            qs = qs.filter(number=page_number)
        return qs

    def get_icon(self):
        """
            return url of document icon
        """
        if self.latest_revision:
            return self.latest_revision.get_icon()
        return "%s%s" % (settings.STATIC_URL, ICON_PATH % FALLBACK_ICON)

    def get_absolute_url(self):
        return self.thread.get_absolute_url()

#######################################


class DocumentRevision(BaseModel):
    """
        TODO
    """
    document = models.ForeignKey("document.Document", related_name='revisions')
    author = models.ForeignKey("auth.User", related_name='document_revisions')
    uuid = models.CharField(max_length=40, unique=True, editable=False)

    def get_path(self):
        return "/".join([
            self.uuid[:2],
            self.uuid[2:4],
            self.uuid,
        ])

    def upload_to_fx(self, original_name):
        return "/".join([
            self.get_path(),
            sanitize_file_name(original_name),
        ])

    file_data = models.FileField(
        upload_to=upload_to_fx,
        storage=DocumentStorage(
            location=settings.DOCUMENT_ROOT,
            base_url=settings.DOCUMENT_URL
        ),
        max_length=512,
        blank=True,
    )
    revision = models.IntegerField()
    revised_at = models.DateTimeField(auto_now_add=True, editable=False, )
    summary = models.CharField(max_length=255)
    approved = models.BooleanField(default=False)
    original_filename = models.CharField(max_length=255)
    filename_slug = models.CharField(max_length=255)
    suffix = models.CharField(max_length=255)
    has_preview = models.BooleanField(default=False)

    class Meta:
        verbose_name = _(u"Document revision")
        verbose_name_plural = _(u"Documents revisions")
        unique_together = ('document', "revision")
        ordering = ("-revised_at", )

    def __unicode__(self):
        return self.uuid

    def save(self, *args, **kwargs):
        """
            save DocumentRevision and store uuid and revision number
        """
        if not self.uuid:
            self.uuid = str(uuid4())
        if not self.revision:
            self.revision = 1 + (self.document.revisions.aggregate(Max("revision"))["revision__max"] or 0)
        return super(DocumentRevision, self).save(*args, **kwargs)

    def get_size(self):
        try:
            return format_size(self.file_data.size)
        except (OSError, IOError):
            logging.error("File does not exist: %s" % repr({
                "path": self.file_data.path,
                "module": "%s.%s" % (type(self)._meta.app_label, type(self)._meta.module_name),
                "pk": self.pk,
            }))
            return None

    def serve_url(self):
        pass

    def plaintext(self):
        """
            return all pages plaintext
        """
        return "\n".join(self.pages.values_list("plaintext", flat=True))

    def html(self):
        pass

    def preview(self):
        """
            return image url
        """
        page_qs = self.pages.order_by("number")[:1]
        if page_qs:
            return page_qs[0].get_thumbnail_url()

    def get_file_name(self):
        return ".".join([self.original_filename, self.suffix])

    def get_icon(self):
        suffix = self.suffix.lower()
        if os.path.exists(os.path.join(settings.STATIC_ROOT, ICON_PATH % suffix)):
            return "%s%s" % (settings.STATIC_URL, ICON_PATH % suffix)
        return "%s%s" % (settings.STATIC_URL, ICON_PATH % FALLBACK_ICON)

    # def delete_thumbnails_directory(self):
    #     first_page = self.pages.all()[:1]
    #     if first_page:
    #         directory = os.path.abspath(os.path.join(
    #             settings.DOCUMENT_ROOT,
    #             first_page[0].get_file_dir()
    #         ))
    #         if os.path.exists(directory):
    #             # print directory
    #             shutil.rmtree(directory)
    #     else:
    #         print "not found"

    ###################################
    # API
    ###################################

    def api_process_document(self, logger=None):
        status = {}
        e = None
        try:
            if logger:
                logger.info("Start processing DocumentRevision: %s" % repr({
                    "uuid": self.uuid,
                    "pk": self.pk,
                    "size": self.get_size(),
                    "name": unicode(self.file_data)
                }))

            status = document_api_client.proxy.upload_document(
                open(self.file_data.path, "r").read(),
                self.uuid
            )

            if logger:
                logger.info("Upload DocumentRevision to Mayan done: %s" % repr(status))

            pages_count = status.get("pages", 0)
            self._pages_count = pages_count

            pi = 0
            for i in xrange(1, pages_count + 1):
                self.pages.create(number=i)
                pi += 1

            ti = 0
            for page in self.pages.iterator():
                page.api_store_thumbnail(logger)
                ti += 1

            if logger:
                logger.info("Processing DocumentRevision: %s" % repr({
                    "created_pages": pi,
                    "thumbnails_retrived": ti
                }))

        except CommunicationError, e:
            connection_success = document_api_client.connect()
            if logger:
                logger.error(u"api_process_document: CommunicationError: %s" % (unicode(e)))

            if connection_success:
                raise e  # it will retry task
            else:
                logger.error(u"Pyro connection fail")

        # except Exception, e:
        #     raise e
        #     if logger:
        #         logger.error(u"api_process_document: %s: %s" % (type(e), unicode(e)))

        finally:
            if logger:
                if isinstance(status, dict):
                    if e:
                        status.update({"error": repr(e)})
                logger.info("Processing DocumentRevision done: %s" % repr(status))

#######################################


class Page(BaseModel):
    """
        TODO
    """
    document_revision = models.ForeignKey("document.DocumentRevision", related_name='pages')
    number = models.IntegerField()
    plaintext = models.TextField(blank=True)

    TH_PREFIX = "th_p"
    TH_DIR_SUFIX = "_th"

    class Meta:
        verbose_name = _(u"Page")
        verbose_name_plural = _(u"Pages")
        ordering = ("number", )

    def get_file_dir(self):
        """
            @return relative path for thumbnail dir
                example: f7/73/f7734fe2-0d43-4d50-adc0-5e03f0fd17db_th
        """
        return "%s%s" % (
            self.document_revision.get_path(),
            self.TH_DIR_SUFIX
        )

    def get_thumbnail_absolute_dir(self, create=False):
        """
            @return: absolute path for store page thumbnail
            @param create: bool - create this path, if not exist
        """
        p = os.path.abspath(
            os.path.join(
                settings.DOCUMENT_ROOT,
                self.get_file_dir()
            )
        )
        if create and not os.path.exists(p):
            os.mkdir(p)
        return p

    def get_file_name(self):
        """
            @return: thumbnail filename
                example: th_p000003.jpg
        """
        return "%s%s.%s" % (
            self.TH_PREFIX,
            str(self.number).zfill(6),
            "jpg"  # TODO: remove hardcored ext.
        )

    def get_thumbnail_url(self, create_dir=False):
        """
            @return: url of thumbnail
                example: f7/73/f7734fe2-0d43-4d50-adc0-5e03f0fd17db_th/th_p000011.jpg
        """

        thumbnail_file = os.path.abspath(os.path.join(
            settings.DOCUMENT_ROOT,
            self.get_file_dir(),
            self.get_file_name()
        ))
        if os.path.exists(thumbnail_file):
            return os.path.join(
                settings.DOCUMENT_URL,
                self.get_file_dir(),
                self.get_file_name()
            )
        else:
            logging.error("Thumbnail file does not exist: %s" % repr({
                "path": thumbnail_file,
                "page": self.pk,
                "number": self.number
            }))
            return None

    def get_thumbnail_path(self, create_dir=False):
        """
            @return: absolute path to thumbnail
        """
        return os.path.join(
            self.get_thumbnail_absolute_dir(create=create_dir),
            self.get_file_name()
        )

    ###################################
    # API methods
    ###################################

    def api_get_plaintext(self, update=False, logger=None):
        """
            @return: page's text returned from remote API
        """
        plaintext = ""
        try:
            plaintext = unicode(document_api_client.proxy.retrive_plaintext(
                self.document_revision.uuid,
                page=self.number,
                default=DOCUMENT_PAGE_CONTENT_IF_ERROR
            ))
        except Exception, e:
            if logger:
                logger.error("ERROR Document page retrive_plaintext: %s" % repr({
                    "error": e,
                    "page_number": self.number,
                    "document_revision_uuid": self.document_revision.uuid,
                }))
        else:
            if logger:
                logger.info("Document page retrive_plaintext: %s" % repr({
                    "plaintext": plaintext[:50],
                    "length": len(plaintext),
                    "document_revision_uuid": self.document_revision.uuid,
                    "document_id": self.document_revision.document_id,
                }))

        if update and (self.plaintext != plaintext):
            self.plaintext = plaintext
            self.save()
            # self.__class__.objects.filter(pk=self.pk).update(plaintext=plaintext)

            # remove old links, if exists
            self.links.all().delete()

            # create new links for file
            for url in get_urllist_from_text(plaintext):
                self.links.create(url=url)

            # DEPRECATED: old index
            # try:
            #     thread = self.document_revision.document.thread
            # except ObjectDoesNotExist, e:
            #     logging.error("ERROR Page.api_get_plaintext: %s" % repr({
            #         "error": e,
            #         "pk": self.pk,

            #     }))
            # else:
            #     signals.post_save.send(
            #         sender=thread.__class__,
            #         instance=thread,
            #         created=False
            #     )
        return plaintext

    def api_store_thumbnail(self, logger=None):
        """
            Store thumbnails using remote API
        """
        _uuid = self.document_revision.uuid
        file_content = None
        thumbnail_path = None
        e = None
        try:
            # file_content = document_api_client.proxy.retrive_thumbnails(
            #     _uuid,
            #     self.number
            # )

            thumbnail_path = document_api_client.proxy.get_thumbnail_path(
                _uuid,
                self.number
            )

        except CommunicationError, e:
            document_api_client.connect()
            if logger:
                logger.error(e)
        except Exception, e:
            if logger:
                logger.error(e)
        # finally:
        #     document_api_client.proxy.clean_file(_uuid, self.number)

        if file_content:
            file_path = self.get_thumbnail_path(create_dir=True)
            # f = open(file_path, "w")
            # f.write(file_content)
            # f.close()

        if thumbnail_path:
            file_path = self.get_thumbnail_path(create_dir=True)
            # logger.info("%s | %s" % (thumbnail_path, file_path))
            shutil.copyfile(thumbnail_path, file_path)


#######################################


class PageLink(BaseModel):
    """
        TODO
    """
    page = models.ForeignKey("document.Page", related_name='links')
    url = models.URLField(max_length=255)

    class Meta:
        verbose_name = _(u"Page link")
        verbose_name_plural = _(u"Pages links")

################################################################################

from openode.document.signals import *
