# -*- coding: utf-8 -*-
"""
:synopsis: views diplaying and processing main content post forms

This module contains views that allow adding, editing, and deleting main textual content.
"""
import datetime
import logging
import os
import os.path

from coffin.template.loader import render_to_string
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core import exceptions
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404, HttpResponsePermanentRedirect, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators import csrf

from openode import const, forms, models
from openode.document.models import Document
from openode.document.forms import DocumentFileForm
from openode.document.views import add_document_view, create_document_revision

from openode.conf import settings as openode_settings
from openode.models.node import Node
from openode.skins.loaders import render_into_skin, render_into_skin_as_string
from openode.templatetags import extra_filters_jinja as template_filters
from openode.utils import decorators, url_utils
from openode.utils.file_utils import store_file
from openode.utils.html import bleach_html
from openode.utils.forms import format_errors
from openode.utils.http import render_forbidden
from openode.utils.path import sanitize_file_name
from openode.views import context

# used in index page
INDEX_PAGE_SIZE = 20
INDEX_TAGS_SIZE = 100
# used in tags list
DEFAULT_PAGE_SIZE = 60
# used in questions
QUESTIONS_PAGE_SIZE = 10
# used in answers
ANSWERS_PAGE_SIZE = 10


@csrf.csrf_exempt
def upload(request):  # ajax upload file to a question or answer
    """view that handles file upload via Ajax
    """

    # check upload permission
    result = ''
    error = ''
    new_file_name = ''

    try:
        #may raise exceptions.PermissionDenied
        if request.user.is_anonymous():
            msg = _('Sorry, anonymous users cannot upload files')
            raise exceptions.PermissionDenied(msg)

        request.user.assert_can_upload_file()

        #todo: build proper form validation
        file_name_prefix = request.POST.get('file_name_prefix', '')
        if file_name_prefix not in ('', 'organization_logo_'):
            raise exceptions.PermissionDenied('invalid upload file name prefix')

        #todo: check file type
        f = request.FILES['file-upload']  # take first file
        #todo: extension checking should be replaced with mimetype checking
        #and this must be part of the form validation

        file_extension = os.path.splitext(f.name)[1].lower()
        if not file_extension in settings.OPENODE_ALLOWED_UPLOAD_FILE_TYPES:
            file_types = "', '".join(settings.OPENODE_ALLOWED_UPLOAD_FILE_TYPES)
            msg = _("allowed file types are '%(file_types)s'") % \
                    {'file_types': file_types}
            raise exceptions.PermissionDenied(msg)

        # generate new file name and storage object
        file_storage, new_file_name, file_url = store_file(
            f, file_name_prefix
        )

        # create document to document storage
        document = Document.objects.create(
            author=request.user,
        )
        dr = document.revisions.create(
            author=request.user,
            file_data=f,
            original_filename=new_file_name.replace(file_extension, ""),
            suffix=file_extension.replace(".", ""),
            filename_slug=sanitize_file_name(new_file_name),
        )
        file_url = dr.file_data.url

        file_storage.delete(new_file_name)

        # # check file size
        # # byte
        # size = file_storage.size(new_file_name)
        # if size > settings.OPENODE_MAX_UPLOAD_FILE_SIZE:
        #     file_storage.delete(new_file_name)
        #     msg = _("maximum upload file size is %(file_size)sK") % \
        #             {'file_size': settings.OPENODE_MAX_UPLOAD_FILE_SIZE}
        #     raise exceptions.PermissionDenied(msg)

    except exceptions.PermissionDenied, e:
        error = unicode(e)
    except Exception, e:
        logging.critical(unicode(e))
        error = _('Error uploading file. Please contact the site administrator. Thank you.')

    if error == '':
        result = 'Good'
    else:
        result = ''
        file_url = ''

    #data = simplejson.dumps({
    #    'result': result,
    #    'error': error,
    #    'file_url': file_url
    #})
    #return HttpResponse(data, mimetype = 'application/json')
    xml_template = "<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url></result>"
    xml = xml_template % (result, error, file_url)

    return HttpResponse(xml, mimetype="application/xml")


#@login_required #actually you can post anonymously, but then must register
@csrf.csrf_protect
@login_required
@decorators.check_spam('text')
def thread_add(request, node_id, node_slug, module):  # view used to add a new thread
    """a view to ask a new question
    gives space for q title, body, tags

    user can start posting a question anonymously but then
    must login/register in order for the question go be shown
    """

    node = get_object_or_404(Node, pk=node_id)

    if not request.user.has_openode_perm('node_%s_create' % module, node):
        return render_forbidden(request)

    if node.slug != node_slug:
        return HttpResponsePermanentRedirect(reverse('thread_add', kwargs={'node_id': node.pk, 'node_slug': node.slug, 'module': module}))

    if module not in const.THREAD_TYPE_BY_NODE_MODULE:
        raise Http404()

    thread_type = const.THREAD_TYPE_BY_NODE_MODULE[module]

    if module == "library":
        return add_document_view(request, node, thread_type)

    ThreadAddForm = forms.thread_add_form_factory(thread_type)

    form = ThreadAddForm(request.REQUEST, user=request.user, node=node)
    if request.method == 'POST':
        if form.is_valid():
            timestamp = datetime.datetime.now()
            title = form.cleaned_data['title']

            if request.user.has_perm('openode.change_tag'):
                tagnames = form.cleaned_data['tags']
            text = form.cleaned_data['text']

            if request.user.is_authenticated():
                drafts = models.DraftQuestion.objects.filter(
                    author=request.user
                )
                drafts.delete()

                user = request.user
                try:
                    kw = dict(
                        title=title,
                        body_text=text,
                        timestamp=timestamp,
                        node=node,
                        thread_type=thread_type
                    )
                    if request.user.has_perm('openode.change_tag'):
                        kw.update({"tags": tagnames})
                    post = user.post_thread(**kw)

                    # user must follow self created question
                    if post.is_question():
                        user.toggle_followed_thread(post.thread)

                    if thread_type == const.THREAD_TYPE_QUESTION:
                        request.user.message_set.create(message=_('Question has been successfully saved and added to your followed items.'))
                    if thread_type == const.THREAD_TYPE_DISCUSSION:
                        request.user.message_set.create(message=_('Discussion has been successfully added.'))
                    return HttpResponseRedirect(post.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message=unicode(e))
                    return HttpResponseRedirect(reverse('index'))

    if request.method == 'GET':
        form = ThreadAddForm(user=request.user, node=node)

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

    if request.user.has_perm('openode.change_tag'):
        form.initial['tags'] = request.REQUEST.get('tags', draft_tagnames)

    data = {
        'active_tab': 'ask',
        'page_class': 'ask-page',
        'form': form,
        'node': node,
        'thread_type': thread_type,
        'tag_names': list()  # need to keep context in sync with edit_thread for tag editor
    }
    data.update(context.get_for_tag_editor())
    return render_into_skin('node/%s/add.html' % thread_type, data, request)


@login_required
@csrf.csrf_exempt
def retag_question(request, id):
    """retag question view
    """
    question = get_object_or_404(models.Post, pk=id)

    if not question.thread.can_retag(request.user):
        response_data = {
            'message': _(u"PermissionDenied: you can not retag this object."),
            'success': False
        }
        data = simplejson.dumps(response_data)
        return HttpResponse(data, mimetype="application/json")

    try:
        request.user.assert_can_retag_question(question)
        if request.method == 'POST':
            form = forms.RetagQuestionForm(question, request.POST)

            if form.is_valid():
                if form.has_changed():
                    request.user.log(question, const.LOG_ACTION_UPDATE_TAGS)
                    request.user.retag_question(question=question, tags=form.cleaned_data['tags'])

                if request.is_ajax():
                    response_data = {
                        'success': True,
                        # 'new_tags': question.thread.tagnames,
                        'new_tags': render_into_skin_as_string('node/snippets/get_tag_list.html', {"thread": question.thread}, request)
                    }
                    # print response_data

                    if request.user.message_set.count() > 0:
                        #todo: here we will possibly junk messages
                        message = request.user.get_and_delete_messages()[-1]
                        response_data['message'] = message

                    data = simplejson.dumps(response_data)
                    return HttpResponse(data, mimetype="application/json")
                else:
                    return HttpResponseRedirect(question.get_absolute_url())
            elif request.is_ajax():
                response_data = {
                    'message': format_errors(form.errors['tags']),
                    'success': False
                }
                data = simplejson.dumps(response_data)
                return HttpResponse(data, mimetype="application/json")
        else:
            form = forms.RetagQuestionForm(question)

        data = {
            'active_tab': 'questions',
            'question': question,
            'form': form,
        }
        return render_into_skin('thread_retag.html', data, request)
    except exceptions.PermissionDenied, e:
        if request.is_ajax():
            response_data = {
                'message': unicode(e),
                'success': False
            }
            data = simplejson.dumps(response_data)
            return HttpResponse(data, mimetype="application/json")
        else:
            request.user.message_set.create(message=unicode(e))
            return HttpResponseRedirect(question.get_absolute_url())


@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
def edit_thread(request, id):
    """edit question view
    """
    thread = get_object_or_404(models.Thread, id=id)
    main_post = thread._main_post()
    revision = main_post.get_latest_revision()
    revision_form = None

    if not thread.has_edit_perm(request.user):
        return render_forbidden(request)

    is_document = bool(thread.thread_type == const.THREAD_TYPE_DOCUMENT)
    is_document_form = bool("file_data" in (request.FILES.keys() + request.POST.keys()))

    data = {
        "is_document": is_document,
    }

    try:
        ###############################
        # DOCUMENT FILE EDIT
        ###############################

        if is_document:
            if (request.method == "POST") and is_document_form:
                document_form = DocumentFileForm(request.POST, request.FILES)
                if document_form.is_valid():

                    if document_form.cleaned_data["remove"]:
                        document = thread.get_document(with_deleted=True)
                        doc_pk = int(document.pk)
                        document.delete()
                        request.user.log(
                            document,
                            const.LOG_ACTION_DELETE_DOCUMENT,
                            object_force_pk=doc_pk
                        )
                        request.user.message_set.create(message=_('Document has been deleted.'))
                        del document
                    else:
                        document_revision = create_document_revision(
                            thread,
                            document_form.cleaned_data,
                            request
                        )

                        request.user.log(document_revision.document, const.LOG_ACTION_UPDATE_DOCUMENT)
                        request.user.message_set.create(message=_('Document has been successfully saved.'))
                    return HttpResponseRedirect(thread.get_absolute_url())

            else:
                document_form = DocumentFileForm()

            data.update({
                "document_form": document_form,
                "document": thread.get_document(),
            })

        ###############################
        # EDIT THREAD
        ###############################

        request.user.assert_can_edit_thread(thread)
        if request.method == 'POST' and (is_document_form is False):
            if request.POST['select_revision'] == 'true':
                #revert-type edit - user selected previous revision
                revision_form = forms.RevisionForm(
                    main_post,
                    revision,
                    request.POST
                )

                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev_id = revision_form.cleaned_data['revision']
                    revision = main_post.revisions.get(revision=rev_id)
                    form = forms.EditQuestionForm(
                        main_post=main_post,
                        user=request.user,
                        revision=revision,
                        node=thread.node,
                        text_required=not is_document
                    )
                else:
                    form = forms.EditQuestionForm(
                        request.POST,
                        main_post=main_post,
                        user=request.user,
                        revision=revision,
                        node=thread.node,
                        text_required=not is_document
                    )

            else:  # new content edit
                # Always check modifications against the latest revision
                form = forms.EditQuestionForm(
                    request.POST,
                    main_post=main_post,
                    revision=revision,
                    user=request.user,
                    node=thread.node,
                    text_required=not is_document
                )

                revision_form = forms.RevisionForm(main_post, revision)
                if form.is_valid():
                    if form.has_changed():
                        _data = {
                            "thread": thread,
                            "title": form.cleaned_data['title'],
                            "body_text": form.cleaned_data['text'],
                            "revision_comment": form.cleaned_data['summary'],
                        }
                        # if request.user.has_perm('openode.change_tag'):
                        if thread.can_retag(request.user):
                            _data.update({
                                "tags": form.cleaned_data['tags']
                            })
                        request.user.edit_thread(**_data)
                        del _data

                    category = form.cleaned_data["category"]
                    allow_external_access = form.cleaned_data["allow_external_access"]
                    do_save = False

                    if is_document and (thread.category != category):
                        thread.category = category
                        do_save = True
                        request.user.log(thread, const.LOG_ACTION_DOCUMENT_MOVE)

                    if is_document and (thread.external_access != allow_external_access):
                        thread.external_access = allow_external_access
                        do_save = True

                    if do_save:
                        thread.save()

                    if thread.thread_type == const.THREAD_TYPE_QUESTION:
                        request.user.log(thread, const.LOG_ACTION_UPDATE_QUESTION)
                        request.user.message_set.create(message=_('Question has been successfully saved.'))
                    if thread.thread_type == const.THREAD_TYPE_DISCUSSION:
                        request.user.log(thread, const.LOG_ACTION_UPDATE_DISCUSSION)
                        request.user.message_set.create(message=_('Discussion has been successfully saved.'))
                    if thread.thread_type == const.THREAD_TYPE_DOCUMENT:
                        request.user.log(thread, const.LOG_ACTION_UPDATE_DOCUMENT)
                        request.user.message_set.create(message=_('Document has been successfully saved.'))
                    return HttpResponseRedirect(thread.get_absolute_url())
        else:
            revision_form = forms.RevisionForm(main_post, revision)
            form = forms.EditQuestionForm(
                main_post=main_post,
                revision=revision,
                user=request.user,
                initial={},
                node=thread.node,
                text_required=not is_document
            )

        data.update({
            'page_class': 'edit-question-page',
            'active_tab': 'questions',
            'main_post': main_post,
            'revision': revision,
            'revision_form': revision_form,
            'form': form,
            'thread_type': thread.thread_type,
            'tag_names': thread.get_tag_names(),
        })
        data.update(context.get_for_tag_editor())
        return render_into_skin('node/%s/edit.html' % thread.thread_type, data, request)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message=unicode(e))
        return HttpResponseRedirect(thread.get_absolute_url())


@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
def edit_answer(request, id):

    # TODO rename answer to post
    answer = get_object_or_404(models.Post, id=id)

    if not answer.has_edit_perm(request.user):
        return render_forbidden(request)

    revision = answer.get_latest_revision()
    try:
        request.user.assert_can_edit_answer(answer)

        if request.method == "POST":

            if request.POST['select_revision'] == 'true':
                # user has changed revistion number
                revision_form = forms.RevisionForm(answer, revision, request.POST)
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev = revision_form.cleaned_data['revision']
                    revision = answer.revisions.get(revision=rev)
                    form = forms.EditAnswerForm(answer, revision)
                else:
                    form = forms.EditAnswerForm(answer, revision, request.POST)
            else:
                form = forms.EditAnswerForm(answer, revision, request.POST)
                revision_form = forms.RevisionForm(answer, revision)

                if form.is_valid():
                    if form.has_changed():
                        user = request.user
                        user.edit_answer(
                            answer=answer,
                            body_text=form.cleaned_data['text'],
                            revision_comment=form.cleaned_data['summary'],
                        )
                    return HttpResponseRedirect(answer.get_absolute_url())
        else:
            revision_form = forms.RevisionForm(answer, revision)
            form = forms.EditAnswerForm(answer, revision)

        data = {
            'page_class': 'edit-answer-page',
            'active_tab': 'questions',
            'answer': answer,
            'revision': revision,
            'revision_form': revision_form,
            'form': form,
        }
        return render_into_skin('node/%s/edit_post.html' % answer.thread.thread_type, data, request)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message=unicode(e))
        return HttpResponseRedirect(answer.get_absolute_url())


# #todo: rename this function to post_new_answer
# @decorators.check_authorization_to_post(_('Please log in to answer questions'))
# @decorators.check_spam('text')
# def answer(request, main_post_id):  # process a new answer
#     """view that posts new answer

#     and redirected to login page

#     authenticated users post directly
#     """

#     main_post = get_object_or_404(models.Post, pk=main_post_id)
#     thread = main_post.thread

#     if thread.thread_type not in const.NODE_MODULE_BY_THREAD_TYPE:
#         raise Http404()

#     if thread.thread_type != main_post.post_type:
#         raise Http404()

#     if request.method == "POST":
#         form = forms.AnswerForm(request.POST)
#         if form.is_valid():
#             text = form.cleaned_data['text']
#             update_time = datetime.datetime.now()

#             if request.user.is_authenticated():
#                 drafts = models.DraftAnswer.objects.filter(
#                                                 author=request.user,
#                                                 thread=thread
#                                             )
#                 drafts.delete()
#                 try:
#                     follow = form.cleaned_data['email_notify']

#                     user = request.user

#                     answer = user.post_answer(
#                                         question=main_post,
#                                         body_text=text,
#                                         follow=follow,
#                                         timestamp=update_time,
#                                     )
#                     return HttpResponseRedirect(answer.get_absolute_url())
#                 except openode_exceptions.AnswerAlreadyGiven, e:
#                     request.user.message_set.create(message=unicode(e))
#                     answer = thread.get_answers_by_user(request.user)[0]
#                     return HttpResponseRedirect(answer.get_absolute_url())
#                 except exceptions.PermissionDenied, e:
#                     request.user.message_set.create(message=unicode(e))
#             else:
#                 request.session.flush()
#                 models.AnonymousAnswer.objects.create(
#                     question=main_post,
#                     text=text,
#                     summary=strip_tags(text)[:120],
#                     session_key=request.session.session_key,
#                     ip_addr=request.META['REMOTE_ADDR'],
#                 )
#                 return HttpResponseRedirect(url_utils.get_login_url())

#     return
#     return HttpResponseRedirect(main_post.get_absolute_url())


def __generate_comments_json(obj, user, new_comment=None):  # non-view generates json data for the post comments
    """non-view generates json data for the post comments
    """
    models.Post.objects.precache_comments(for_posts=[obj], visitor=user)
    comments = obj._cached_comments

    # {"Id":6,"PostId":38589,"CreationDate":"an hour ago","Text":"hello there!","UserDisplayName":"Jarrod Dixon","UserUrl":"/users/3/jarrod-dixon","DeleteUrl":null}
    json_comments = []

    for comment in comments:

        if user and user.is_authenticated():
            try:
                user.assert_can_delete_comment(comment)
                #/posts/392845/comments/219852/delete
                #todo translate this url
                is_deletable = True
            except exceptions.PermissionDenied:
                is_deletable = False
            is_editable = template_filters.can_edit_comment(comment.author, comment)
        else:
            is_deletable = False
            is_editable = False

        comment_owner = comment.author
        tz = ' ' + template_filters.TIMEZONE_STR
        comment_data = {'id': comment.id,
            'object_id': obj.id,
            'comment_added_at': str(comment.added_at.replace(microsecond=0)) + tz,
            'html': mark_safe(comment.text),
            'user_display_name': escape(comment_owner.username),
            'user_url': comment_owner.get_profile_url(),
            'user_id': comment_owner.id,
            'is_deletable': is_deletable,
            'is_editable': is_editable,
            'points': comment.points,
            'score': comment.points,  # to support js
            'upvoted_by_user': getattr(comment, 'upvoted_by_user', False)
        }
        json_comments.append(comment_data)

    if new_comment:

        # show last visit for posts (comments, ...)
        try:
            thread_view_last_visit = new_comment.thread.viewed.get(user=user).last_visit
        except (exceptions.ObjectDoesNotExist, TypeError):
            thread_view_last_visit = datetime.datetime.now()

        data = simplejson.dumps({
            "parent_post_type": new_comment.parent.post_type,
            "all_comments": json_comments,
            "html": mark_safe(render_to_string("node/snippets/one_comment.html", {
                "comment": new_comment,
                "user": user,
                "thread_view_last_visit": thread_view_last_visit,
                "wrap_content": True,
            }))
        })
        new_comment.thread.visit(user)

        # add new comment is "activity" a must be reflected
        new_comment.thread.set_last_activity(
            last_activity_at=datetime.datetime.now(),
            last_activity_by=user
        )
    else:
        data = simplejson.dumps(json_comments)

    return HttpResponse(data, mimetype="application/json")


@csrf.csrf_exempt
@decorators.check_spam('comment')
def post_comments(request):
    # generic ajax handler to load comments to an object
    # only support get post comments by ajax now

    post_type = request.REQUEST.get('post_type', '')
    if not request.is_ajax() or post_type not in ('question', 'answer', 'discussion'):
        # TODO: Shouldn't be 404! More like 400, 403 or sth more specific
        raise Http404

    user = request.user
    obj = get_object_or_404(models.Post, pk=request.REQUEST['post_id'])

    if obj.thread and not user.has_openode_perm("%s_answer_comment_create" % obj.thread.thread_type, obj.thread):
        return HttpResponseForbidden(mimetype="application/json")

    if request.method == "GET":
        response = __generate_comments_json(obj, user)
    elif request.method == "POST":
        text = request.POST.get('comment')

        clean_text = strip_tags(text).replace("&nbsp;", "").strip()

        if not clean_text:
            return HttpResponse(
                simplejson.dumps({"errors": _("Comment is empty.")}),
                mimetype="application/json"
            )
        elif len(clean_text) < openode_settings.MIN_ANSWER_BODY_LENGTH:
            return HttpResponse(
                simplejson.dumps({
                    "errors": _("Comment must be at least %d character long." % openode_settings.MIN_ANSWER_BODY_LENGTH)
                }),
                mimetype="application/json"
            )

        try:
            if user.is_anonymous():
                msg = _('Sorry, you appear to be logged out and '
                        'cannot post comments. Please '
                        '<a href="%(sign_in_url)s">sign in</a>.') % \
                        {'sign_in_url': url_utils.get_login_url()}
                raise exceptions.PermissionDenied(msg)

            response = __generate_comments_json(
                obj,
                user,
                new_comment=user.post_comment(
                    parent_post=obj,
                    body_text=bleach_html(text)
                    )
                )
        except exceptions.PermissionDenied, e:
            response = HttpResponseForbidden(unicode(e), mimetype="application/json")

    return response


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.check_spam('comment')
def edit_comment(request):

    if request.user.is_anonymous():
        raise exceptions.PermissionDenied(_('Sorry, anonymous users cannot edit comments'))

    comment_id = int(request.POST['comment_id'])
    try:
        comment_post = models.Post.objects.get(
            post_type='comment',
            pk=comment_id
        )
    except models.Post.DoesNotExist:
        return HttpResponseNotFound(mimetype="application/json")

    thread = comment_post.thread
    if thread and not request.user.has_openode_perm("question_answer_comment_update_any", thread):
        return HttpResponseForbidden(mimetype="application/json")

    request.user.edit_comment(comment_post=comment_post, body_text=request.POST['comment'])

    is_deletable = template_filters.can_delete_comment(comment_post.author, comment_post)
    is_editable = template_filters.can_edit_comment(comment_post.author, comment_post)
    tz = ' ' + template_filters.TIMEZONE_STR

    tz = template_filters.TIMEZONE_STR

    # show last visit for posts (comments, ...)
    try:
        thread_view_last_visit = thread.viewed.get(user=request.user).last_visit
    except (exceptions.ObjectDoesNotExist, TypeError):
        thread_view_last_visit = datetime.datetime.now()

    thread.visit(request.user)

    return {
        'id': comment_post.id,
        'object_id': comment_post.parent.id,
        'comment_added_at': str(comment_post.added_at.replace(microsecond=0)) + tz,
        "html": mark_safe(render_to_string("node/snippets/one_comment.html", {"comment": comment_post, "user": request.user, "thread_view_last_visit": thread_view_last_visit, "wrap_content": False})),
        'user_display_name': comment_post.author.username,
        'user_url': comment_post.author.get_profile_url(),
        'user_id': comment_post.author.id,
        'is_deletable': is_deletable,
        'is_editable': is_editable,
        'score': comment_post.points,  # to support unchanged js
        'points': comment_post.points,
        'voted': comment_post.is_upvoted_by(request.user),
    }


@csrf.csrf_exempt
def delete_comment(request):
    """ajax handler to delete comment
    """
    try:
        if request.user.is_anonymous():
            msg = _('Sorry, you appear to be logged out and '
                    'cannot delete comments. Please '
                    '<a href="%(sign_in_url)s">sign in</a>.') % \
                    {'sign_in_url': url_utils.get_login_url()}
            raise exceptions.PermissionDenied(msg)
        if request.is_ajax():

            comment = get_object_or_404(
                models.Post,
                post_type='comment',
                pk=request.POST['comment_id']
                )
            request.user.assert_can_delete_comment(comment)

            if not request.user.has_openode_perm("question_answer_comment_delete_any", comment.thread):
                raise exceptions.PermissionDenied("msg")

            parent = comment.parent
            comment.delete()
            #attn: recalc denormalized field
            parent.comment_count = max(parent.comment_count - 1, 0)
            parent.save()
            parent.thread.invalidate_cached_data()

            return __generate_comments_json(parent, request.user)

        raise exceptions.PermissionDenied(_('sorry, we seem to have some technical difficulties'))
    except exceptions.PermissionDenied, e:
        return HttpResponseForbidden(
            unicode(e),
            mimetype='application/json'
        )


@decorators.admins_only
@decorators.post_only
def comment_to_answer(request):
    comment_id = request.POST.get('comment_id')
    if comment_id:
        comment_id = int(comment_id)
        comment = get_object_or_404(models.Post,
                post_type='comment', id=comment_id)
        comment.post_type = 'answer'
        old_parent = comment.parent

        comment.parent = comment.thread._main_post()
        comment.save()

        comment.thread.update_answer_count()

        comment.parent.comment_count += 1
        comment.parent.save()

        #to avoid db constraint error
        if old_parent.comment_count >= 1:
            old_parent.comment_count -= 1
        else:
            old_parent.comment_count = 0

        old_parent.save()

        comment.thread.invalidate_cached_data()

        return HttpResponseRedirect(comment.get_absolute_url())
    else:
        raise Http404


@decorators.admins_only
@decorators.post_only
def answer_to_comment(request):
    answer_id = request.POST.get('answer_id')
    if answer_id:
        answer_id = int(answer_id)
        answer = get_object_or_404(models.Post,
                post_type='answer', id=answer_id)
        if len(answer.text) <= 300:
            answer.post_type = 'comment'
            answer.parent = answer.thread._main_post()
            #can we trust this?
            old_comment_count = answer.comment_count
            answer.comment_count = 0

            answer_comments = models.Post.objects.get_comments().filter(parent=answer)
            answer_comments.update(parent=answer.parent)

            answer.parse_and_save(author=answer.author)
            answer.thread.update_answer_count()

            answer.parent.comment_count = 1 + old_comment_count
            answer.parent.save()

            answer.thread.invalidate_cached_data()
        else:
            request.user.message_set.create(message=_("the selected answer cannot be a comment"))

        return HttpResponseRedirect(answer.get_absolute_url())
    else:
        raise Http404
