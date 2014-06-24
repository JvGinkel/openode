# -*- coding: utf-8 -*-

import codecs
import datetime
import logging
import os
import shutil
import tempfile
import zipfile

from django.contrib.auth.decorators import login_required
from django.core import exceptions
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile, SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_unicode, DjangoUnicodeDecodeError
from django.utils.translation import ugettext as _
from django.views.decorators import csrf

from openode import const
from openode import models
from openode.document.forms import (
        AddThreadCategoryForm,
        DocumentForm,
        DownloadZipForm,
        CategoryMoveForm,
        EditThreadCategoryForm,
    )
from openode.document.models import Document
from openode.models.node import Node
from openode.models.thread import ThreadCategory
from openode.skins.loaders import render_into_skin
from openode.utils import count_visit, decorators
from openode.utils.http import render_forbidden
from openode.utils.path import sanitize_file_name
from openode.views import context

from django.conf import settings


################################################################################


def category_add(request, node_id, node_slug):
    """
        add ThreadCategory
        recently used only for structuring Document Threads, so is called Directory
    """
    node = get_object_or_404(Node, pk=node_id)

    if not request.user.has_openode_perm("document_directory_create", node):
        return render_forbidden(request)

    if request.method == "POST":
        form = AddThreadCategoryForm(request.POST, node=node)
        if form.is_valid():
            thread_category = form.save()
            request.user.log(thread_category, const.LOG_ACTION_ADD_THREAD_CATEGORY)
            return HttpResponseRedirect(reverse("node_module", args=[node.pk, node.slug, "library"]))
    else:
        form = AddThreadCategoryForm(node=node, initial={"node": node})

    to_tmpl = {
        "node": node,
        "form": form,
        "directory": None,
    }
    return render_into_skin('node/document/edit_directory.html', to_tmpl, request)


def category_reorg(request, node_id, node_slug):
    node = get_object_or_404(Node, pk=node_id)

    if not request.user.has_openode_perm("document_directory_create", node):
        return render_forbidden(request)

    to_tmpl = {
        "categories": node.thread_categories.filter(level=0),
        "node": node
    }
    return render_into_skin('node/document/reorg_directory.html', to_tmpl, request)


def category_move(request, node_id, node_slug, category_id):
    node = get_object_or_404(Node, pk=node_id)

    try:
        category = node.thread_categories.get(pk=category_id)
    except ThreadCategory.DoesNotExist:
        raise Http404

    if request.method == "POST":
        form = CategoryMoveForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            request.user.log(category, const.LOG_ACTION_THREAD_CATEGORY_MOVE)
            return HttpResponseRedirect(reverse("category_reorg", args=[node.pk, node.slug]))
    else:
        form = CategoryMoveForm(instance=category)

    to_tmpl = {
        "categories": node.thread_categories.filter(level=0),
        "category": category,
        'form': form,
    }

    return render_into_skin('node/document/move_directory.html', to_tmpl, request)

#######################################


def category_delete(request, node_id, node_slug, category_id):

    # TODO: check perm

    node = get_object_or_404(Node, pk=node_id)

    try:
        category = node.thread_categories.get(pk=category_id)
    except ObjectDoesNotExist:
        raise Http404
    else:
        if not category.has_delete_perm(request.user):
            return render_forbidden(request)
        category.delete()

    return HttpResponseRedirect(
        reverse("node_module", args=[node.pk, node.slug, const.NODE_MODULE_LIBRARY])
    )


def category_edit(request, node_id, node_slug, category_id):
    """
        edit ThreadCategory
        recently used only for structuring Document Threads, so is called Directory
    """
    node = get_object_or_404(Node, pk=node_id)
    try:
        category = node.thread_categories.get(pk=category_id)
    except ObjectDoesNotExist:
        raise Http404

    if not category.has_update_perm(request.user):
        return render_forbidden(request)

    if request.method == "POST":
        form = EditThreadCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            request.user.log(category, const.LOG_ACTION_THREAD_CATEGORY_EDIT)

            return HttpResponseRedirect(reverse("node_module", args=[node.pk, node.slug, "library"]))
    else:
        form = EditThreadCategoryForm(instance=category)

    to_tmpl = {
        "node": node,
        "form": form,
        "directory": category,
    }
    return render_into_skin('node/document/edit_directory.html', to_tmpl, request)

#######################################


@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
def add_document_view(request, node, thread_type):
    """
        create new document (and related Thread)
    """

    def _create_doc(user, post, file_data):
        document = Document.objects.create(
            author=user,
            thread=post.thread
        )

        parsed_file_name = os.path.splitext(
            force_unicode(file_data.name, strings_only=True, errors="ignore")
        )
        file_name = parsed_file_name[0].lower()
        suffix = parsed_file_name[1].replace(".", "").lower()

        return document.revisions.create(
            file_data=file_data,
            original_filename=file_name,
            suffix=suffix,
            filename_slug=sanitize_file_name(file_name),
            author=user,
        )

    def _is_zip_file_extended(name, path):
        """
            test if file on path is zip archive,
            test for special extension is simple test for exclude zip like files (docx, xlsx, ...)
        """
        ZIP_FILES_EXT = ["zip"]
        return (name.split(".")[-1].lower() in ZIP_FILES_EXT) and zipfile.is_zipfile(path)

    def recursive_process_dir(directory):
        """
            recursive read directory content and create Documents from all files on any level of direcotry tree.
            Final structure is flat.
        """
        for file_name in os.listdir(directory):
            _path = os.path.join(directory, file_name)

            if os.path.isdir(_path):
                recursive_process_dir(_path)
            else:
                title = force_unicode(file_name, strings_only=True, errors="ignore")
                _post = user.post_thread(**{
                    "title": "%s: %s" % (form.cleaned_data['title'], title),
                    "body_text": "",
                    "timestamp": timestamp,
                    "node": node,
                    "thread_type": thread_type,
                    "category": category,
                    "external_access": form.cleaned_data["allow_external_access"],
                })

                with codecs.open(_path, "r", errors="ignore") as file_content:
                    _create_doc(user, _post, SimpleUploadedFile(title, file_content.read()))


    ################################################################################

    if request.method == 'POST':

        form = DocumentForm(request.REQUEST, request.FILES, node=node, user=request.user)

        if form.is_valid():

            timestamp = datetime.datetime.now()
            text = form.cleaned_data['text']
            category = form.cleaned_data['thread_category']

            if request.user.is_authenticated():
                drafts = models.DraftQuestion.objects.filter(
                    author=request.user
                )
                drafts.delete()

                user = request.user
                try:

                    _data = {
                        "title": form.cleaned_data['title'],
                        "body_text": text,
                        "timestamp": timestamp,
                        "node": node,
                        "thread_type": thread_type,
                        "category": category,
                        "external_access": form.cleaned_data["allow_external_access"],
                    }
                    post = user.post_thread(**_data)
                    del _data

                    file_data = form.cleaned_data["file_data"]

                    if file_data:

                        # create Document from uploaded file
                        dr = _create_doc(user, post, file_data)

                        # if uploaded file is zip archive, create documents from all files in.
                        if _is_zip_file_extended(dr.file_data.name, dr.file_data.path):

                            # extract zip to temp directory
                            temp_dir = tempfile.mkdtemp()
                            with zipfile.ZipFile(dr.file_data.path, "r") as zf:
                                zf.extractall(temp_dir)

                            # recursive process all files in all directories of zip file
                            # create flat structure from directory tree
                            recursive_process_dir(temp_dir)

                            # clear
                            shutil.rmtree(temp_dir)

                    request.user.message_set.create(message=_('Document has been successfully added.'))
                    return HttpResponseRedirect(post.thread.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message=unicode(e))
                    return HttpResponseRedirect(reverse('index'))

    elif request.method == 'GET':
        form = DocumentForm(node=node, user=request.user)

    draft_title = ''
    draft_text = ''
    draft_tagnames = ''
    if request.user.is_authenticated():
        drafts = models.DraftQuestion.objects.filter(author=request.user)
        if len(drafts) > 0:
            draft = drafts[0]
            draft_title = draft.title
            draft_text = draft.text
            draft_tagnames = draft.tagnames

    form.initial = {
        'title': request.REQUEST.get('title', draft_title),
        'text': request.REQUEST.get('text', draft_text),
    }

    # TODO: use Thread.can_retag method
    if request.user.has_perm('openode.change_tag'):
        form.initial['tags'] = request.REQUEST.get('tags', draft_tagnames)

    data = {
        'active_tab': 'ask',
        'page_class': 'ask-page',
        'node': node,
        'form': form,
        'thread_type': const.THREAD_TYPE_DOCUMENT,
        'tag_names': list()  # need to keep context in sync with edit_thread for tag editor
    }
    data.update(context.get_for_tag_editor())
    return render_into_skin('node/document/add.html', data, request)

    ############   THIS CODE IS USELESS  ##############
    #########     handeled in writers.py:437     ###########

    # if request.method == "POST":
    #     form = DocumentRevisionModelForm(
    #         request.POST,
    #         request.FILES,
    #         request=request,
    #         node=node,
    #     )
    #     form.fields['thread_category'].queryset = node.thread_categories.all()
    #     if form.is_valid():
    #         dr = form.save()

    #         return HttpResponseRedirect(
    #             reverse("document_detail", args=[node.pk, node.slug, dr.document.pk])
    #         )
    # else:
    #     form = DocumentRevisionModelForm(
    #         node=node,
    #         initial={
    #             "node": node,
    #         },
    #     )
    #     form.fields['thread_category'].queryset = node.thread_categories.all()
    # to_tmpl = {
    #     "form": form,
    #     "node": node,
    # }
    # return render_into_skin('node/document/edit.html', to_tmpl, request)

#######################################


def document_detail_view(request, node, thread):
    """
        Detail of library Document
    """

    document = thread.get_document()
    main_post = thread._main_post()

    to_tmpl = {
        "node": thread.node,
        "document": document,
        "file_size": None,
        "main_post": main_post,
        "module": const.NODE_MODULE_LIBRARY,
        'similar_threads': thread.get_similar_threads(),
        "thread": thread,
    }

    if document and document.latest_revision:
        to_tmpl.update({
            "file_size": document.latest_revision.get_size()
        })

    # count visit for thread
    count_visit(request, thread, main_post)

    # at the end we call thread.visit, we dont need celery for this
    # operate with ThreadView
    thread.visit(request.user)

    if document and document.latest_revision:
        try:
            page_no = int(request.GET.get("page", 1))
        except ValueError:
            page_no = 1

        page_qs = document.get_pages(page_no)
        if page_qs.exists():
            page = page_qs[0]
        else:
            page = None

        to_tmpl.update({
            "page": page,
            "pages_numbers": document.latest_revision.pages.values_list("number", flat=True)
        })

    return render_into_skin("node/document/detail.html", to_tmpl, request)

#######################################


def retry_process_document(request, node_id, node_slug, thread_pk):
    """

    """
    try:
        node = get_object_or_404(Node, pk=node_id)
        thread = node.threads.get(pk=thread_pk)
        document = thread.get_document()
        document_revision = document.latest_revision
    except ObjectDoesNotExist:
        raise Http404

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

    request.user.message_set.create(message=_('Document has been succesfully re-processed.'))
    return HttpResponseRedirect(thread.get_absolute_url())


    # tasks.process_document_revision.delay(
    #     document_revision.uuid,
    #     document_pk=document.pk
    #     )

#######################################

def download_as_zip(request, node_id, node_slug):
    form = DownloadZipForm(request.POST)
    if form.is_valid():
        documents_ids = form.cleaned_data["documents_ids"]
        try:
            documents_ids = [int(_id) for _id in documents_ids.split(",")]
        except ValueError, e:
            return HttpResponseForbidden("Invalid value")
    else:
        return HttpResponseForbidden("Invalid form")

    documents = Document.objects.filter(
        pk__in=documents_ids,
        thread__node__id=node_id
    )

    if not documents.exists():
        raise Http404

    hash_base = [node_id]
    hash_base.extend(documents.values_list("pk", flat=True))
    _hash = abs(hash("".join([str(x) for x in hash_base])))

    new_zip_name = '%s_%s.zip' % (node_slug, _hash)
    new_zip_path = os.path.join(tempfile.mkdtemp(), new_zip_name)
    new_zip = zipfile.ZipFile(new_zip_path, 'w')

    for document in documents:
        dr = document.latest_revision
        if dr is None:
            logging.error("DocumentRevision not found: %s" % repr({
                "document": document.pk,
                "node": node_id
            }))
            continue

        abs_path = os.path.join(settings.MEDIA_ROOT, dr.file_data.path)
        if not os.path.exists(abs_path):
            logging.error("DocumentRevision file not found: %s" % repr({
                "document": document.pk,
                "document_revision": dr.pk,
                "file_path": abs_path,
                "node": node_id,
            }))
            continue

        new_zip.write(abs_path, os.path.basename(abs_path))
    new_zip.close()

    with open(new_zip_path, 'rb') as _file:
        response = HttpResponse(_file.read(), mimetype='application/zip')
    response['Content-Disposition'] = 'attachment; filename=%s' % str(new_zip_name)
    return response

#######################################
#######################################

# DEPRECATED
# # @login_required
# def document_edit(request, node_id, node_slug, document_id):
#     """
#         document edit, it create new revision - TODO
#     """

#     document = get_object_or_404(Document, pk=document_id)
#     node = document.thread.node

#     document_revision = document.latest_revision

#     if request.method == "POST":
#         form = DocumentRevisionModelForm(
#             request.POST, request.FILES,
#             request=request,
#             document=document,
#             instance=document_revision,
#             node=document.thread.node,
#         )
#         if form.is_valid():
#             form.save()
#             return HttpResponseRedirect(reverse("document_edit", args=[node.pk, node.slug, document.pk]))
#     else:
#         form = DocumentRevisionModelForm(
#             instance=document_revision,
#             initial={
#                 "node": document.thread.node,
#                 "title": document.thread.title,
#                 "thread_category": document.thread.category,
#             },
#             node=document.thread.node,
#         )

#     to_tmpl = {
#         "form": form,
#         "document": document,
#         "document_revision": document_revision
#     }
#     return render_into_skin('document/edit.html', to_tmpl, request)

#######################################


# @login_required
# def view(request, document_id):

#     document = get_object_or_404(Document, pk=document_id)

#     revision_id = request.GET.get("revision")
#     if revision_id:
#         try:
#             document_revision = document.revisions.get(revision=int(revision_id))
#         except (ValueError, DocumentRevision.DoesNotExist):
#             raise Http404
#     else:
#         document_revision = document.latest_revision

#     to_tmpl = {
#         "document": document,
#         "document_revision": document_revision
#     }
#     return render_into_skin('document/view.html', to_tmpl, request)


# @login_required
# def reprocess(request, uuid):
#     import tasks
#     dr = get_object_or_404(DocumentRevision, uuid=uuid)
#     print tasks.process_document_revision.delay(dr.uuid)
#     print uuid
#     return HttpResponseRedirect(reverse("document:edit", args=[dr.document_id]))
# @login_required


#######################################

def create_document_revision(thread, form_data, request):
    """
        helpers fx for edit document in thread edit form
    """

    file_data = form_data["file_data"]
    remove = form_data["remove"]

    document = thread.get_document(with_deleted=True)

    if document is None:
        document = Document.objects.create(
            author=request.user,
            thread=thread
        )

    if remove:
        document.is_deleted = True
        document.save()
        return

    if document.is_deleted:
        document.is_deleted = False
        document.save()

    # create document revision
    parsed_file_name = os.path.splitext(file_data.name)
    file_name = parsed_file_name[0].lower()
    suffix = parsed_file_name[1].replace(".", "").lower()

    return document.revisions.create(
        file_data=file_data,
        original_filename=file_name,
        suffix=suffix,
        filename_slug=sanitize_file_name(file_name),
        author=request.user,
    )
