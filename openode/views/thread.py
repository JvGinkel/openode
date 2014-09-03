# -*- coding: utf-8 -*-

import datetime
import logging
from sys import maxint

from django.shortcuts import get_object_or_404
from django.core import exceptions as django_exceptions
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator  # , EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import ugettext as _
from django.views.decorators import csrf

from openode import const, exceptions as openode_exceptions, models
from openode.conf import settings as openode_settings
from openode.document.views import document_detail_view
from openode.forms import AnswerForm, ShowQuestionForm
from openode.models import Vote
from openode.models.node import Node
from openode.models.thread import Thread
# from openode.utils.diff import textDiff as htmldiff
from openode.skins.loaders import render_into_skin  # , get_template  # jinja2 template loading enviroment
from openode.utils import count_visit, functions, url_utils
from openode.utils.http import render_forbidden
from openode.views import context


@csrf.csrf_protect
#@cache_page(60 * 5)
def thread(request, node_id, node_slug, module, thread_id, thread_slug):  # refactor - long subroutine. display question body, answers and comments
    """view that displays body of the question and
    all answers to it
    """

    node = get_object_or_404(Node, pk=node_id)
    thread = get_object_or_404(Thread, pk=thread_id, node=node)

    # raise not found if module is disabled
    if not getattr(node, "module_%s" % const.NODE_MODULE_BY_THREAD_TYPE[thread.thread_type], False):
        raise Http404

    if not request.user.has_openode_perm('%s_read' % thread.thread_type, thread):
        return render_forbidden(request)

    if module not in const.THREAD_TYPE_BY_NODE_MODULE or const.THREAD_TYPE_BY_NODE_MODULE[module] != thread.thread_type:
        raise Http404()

    if module == const.NODE_MODULE_LIBRARY:
        return document_detail_view(request, node, thread)

    if node.slug != node_slug or thread.slug != thread_slug:
        return HttpResponseRedirect(reverse('thread', kwargs={
            'node_id': node_id,
            'node_slug': node.slug,
            'module': module,
            'thread_id': thread_id,
            'thread_slug': thread.slug
        }))

    #process url parameters
    #todo: fix inheritance of sort method from questions
    #before = datetime.datetime.now()
    default_sort_method = request.session.get('questions_sort_method', thread.get_default_sort_method())
    form = ShowQuestionForm(request.GET, default_sort_method)
    form.full_clean()  # always valid
    show_answer = form.cleaned_data['show_answer']
    show_comment = form.cleaned_data['show_comment']
    show_page = form.cleaned_data['show_page']
    answer_sort_method = form.cleaned_data['answer_sort_method']

    main_post = thread._main_post()
    try:
        main_post.assert_is_visible_to(request.user)
    except openode_exceptions.QuestionHidden, error:
        request.user.message_set.create(message=unicode(error))
        return HttpResponseRedirect(reverse('index'))

    #redirect if slug in the url is wrong
    # if request.path.split('/')[-2] != question_post.slug:
    #     logging.debug('no slug match!')
    #     question_url = '?'.join((
    #                         question_post.get_absolute_url(),
    #                         urllib.urlencode(request.GET)
    #                     ))
    #     return HttpResponseRedirect(question_url)

    #resolve comment and answer permalinks
    #they go first because in theory both can be moved to another question
    #this block "returns" show_post and assigns actual comment and answer
    #to show_comment and show_answer variables
    #in the case if the permalinked items or their parents are gone - redirect
    #redirect also happens if id of the object's origin post != requested id
    show_post = None  # used for permalinks

    if show_comment:
        #if url calls for display of a specific comment,
        #check that comment exists, that it belongs to
        #the current question
        #if it is an answer comment and the answer is hidden -
        #redirect to the default view of the question
        #if the question is hidden - redirect to the main page
        #in addition - if url points to a comment and the comment
        #is for the answer - we need the answer object
        try:
            show_comment = models.Post.objects.get_comments().get(id=show_comment)
        except models.Post.DoesNotExist:
            error_message = _(
                'Sorry, the comment you are looking for has been '
                'deleted and is no longer accessible'
            )
            request.user.message_set.create(message=error_message)
            return HttpResponseRedirect(thread.get_absolute_url())

        if str(show_comment.thread.id) != str(thread_id):
            return HttpResponseRedirect(show_comment.get_absolute_url())
        show_post = show_comment.parent

        try:
            show_comment.assert_is_visible_to(request.user)
        except openode_exceptions.AnswerHidden, error:
            request.user.message_set.create(message=unicode(error))
            #use reverse function here because question is not yet loaded
            return HttpResponseRedirect(thread.get_absolute_url())
        except openode_exceptions.QuestionHidden, error:
            request.user.message_set.create(message=unicode(error))
            return HttpResponseRedirect(reverse('index'))

    elif show_answer:
        #if the url calls to view a particular answer to
        #question - we must check whether the question exists
        #whether answer is actually corresponding to the current question
        #and that the visitor is allowed to see it
        show_post = get_object_or_404(models.Post, post_type='answer', id=show_answer)
        if str(show_post.thread.id) != str(thread_id):
            return HttpResponseRedirect(show_post.get_absolute_url())

        try:
            show_post.assert_is_visible_to(request.user)
        except django_exceptions.PermissionDenied, error:
            request.user.message_set.create(message=unicode(error))
            return HttpResponseRedirect(thread.get_absolute_url())

    # logging.debug('answer_sort_method=' + unicode(answer_sort_method))

    #load answers and post id's->athor_id mapping
    #posts are pre-stuffed with the correctly ordered comments

    authors = []

    qs = thread.posts.filter(
        author__in=authors,
        deleted=False
    )

    updated_main_post, answers, post_to_author = thread.get_cached_post_data(
        sort_method=answer_sort_method,
        user=request.user,
        qs=qs
    )

    if updated_main_post:
        main_post.set_cached_comments(
            updated_main_post.get_cached_comments()
        )

    #Post.objects.precache_comments(for_posts=[question_post] + answers, visitor=request.user)

    user_votes = {}
    user_post_id_list = list()
    #todo: cache this query set, but again takes only 3ms!
    if request.user.is_authenticated():
        user_votes = Vote.objects.filter(
            user=request.user,
            voted_post__id__in=post_to_author.keys()
        ).values_list(
            'voted_post_id',
            'vote'
        )
        user_votes = dict(user_votes)
        #we can avoid making this query by iterating through
        #already loaded posts
        user_post_id_list = [
            post_id for post_id in post_to_author if post_to_author[post_id] == request.user.id
        ]

    #resolve page number and comment number for permalinks
    show_comment_position = None
    if show_comment:
        show_page = show_comment.get_page_number(answer_posts=answers)
        show_comment_position = show_comment.get_order_number()
    elif show_answer:
        show_page = show_post.get_page_number(answer_posts=answers)

    ###################################
    # paginator
    ###################################

    if thread.is_question():
        per_page = maxint
    else:
        per_page = const.ANSWERS_PAGE_SIZE

    # define posts position on paginator pages
    posts_per_pages = {}
    for i, post in enumerate(answers):
        posts_per_pages[post.pk] = 1 + (i // per_page)

    objects_list = Paginator(answers, per_page)
    if show_page > objects_list.num_pages:
        return HttpResponseRedirect(main_post.get_absolute_url())
    page_objects = objects_list.page(show_page)

    count_visit(request, thread, main_post)

    paginator_data = {
        'is_paginated': (objects_list.count > per_page),
        'pages': objects_list.num_pages,
        'page': show_page,
        'has_previous': page_objects.has_previous(),
        'has_next': page_objects.has_next(),
        'previous': page_objects.previous_page_number(),
        'next': page_objects.next_page_number(),
        'base_url': request.path + '?sort=%s&amp;' % answer_sort_method,
    }
    paginator_context = functions.setup_paginator(paginator_data)

    ###################################

    initial = {
        'email_notify': thread.is_subscribed_by(request.user)
    }

    #maybe load draft
    if request.user.is_authenticated():
        #todo: refactor into methor on thread
        drafts = models.DraftAnswer.objects.filter(
            author=request.user,
            thread=thread
        )
        if drafts.count() > 0:
            initial['text'] = drafts[0].text

    #answer form
    if request.method == "POST":

        if not thread.has_response_perm(request.user):
            return render_forbidden(request)

        answer_form = AnswerForm(request.POST, node=node)
        if answer_form.is_valid():
            text = answer_form.cleaned_data['text']
            update_time = datetime.datetime.now()

            if request.user.is_authenticated():
                drafts = models.DraftAnswer.objects.filter(
                    author=request.user,
                    thread=thread
                    )
                drafts.delete()
                try:
                    follow = answer_form.cleaned_data['email_notify']

                    user = request.user

                    answer = user.post_answer(
                        question=main_post,
                        body_text=text,
                        follow=follow,
                        timestamp=update_time,
                        )
                    return HttpResponseRedirect(answer.get_absolute_url())
                except openode_exceptions.AnswerAlreadyGiven, e:
                    request.user.message_set.create(message=unicode(e))
                    answer = thread.get_answers_by_user(request.user)[0]
                    return HttpResponseRedirect(answer.get_absolute_url())
                except django_exceptions.PermissionDenied, e:
                    request.user.message_set.create(message=unicode(e))
            else:
                request.session.flush()
                models.AnonymousAnswer.objects.create(
                    question=main_post,
                    text=text,
                    summary=strip_tags(text)[:120],
                    session_key=request.session.session_key,
                    ip_addr=request.META['REMOTE_ADDR'],
                )
                return HttpResponseRedirect(url_utils.get_login_url())
    else:
        answer_form = AnswerForm(initial=initial, node=node)

    user_can_post_comment = (
        request.user.is_authenticated() and request.user.can_post_comment()
    )

    user_already_gave_answer = False
    previous_answer = None
    if request.user.is_authenticated():
        if openode_settings.LIMIT_ONE_ANSWER_PER_USER and module == const.NODE_MODULE_QA:
            for answer in answers:
                if answer.author == request.user:
                    user_already_gave_answer = True
                    previous_answer = answer
                    break

    data = {
        'is_cacheable': False,  # is_cacheable, #temporary, until invalidation fix
        'long_time': const.LONG_TIME,  # "forever" caching
        'page_class': 'question-page',
        'active_tab': 'questions',
        'main_post': main_post,
        'thread': thread,
        'answer_form': answer_form,
        'answers': page_objects.object_list,
        'answer_count': thread.get_answer_count(request.user),
        'user_votes': user_votes,
        'user_post_id_list': user_post_id_list,
        'user_can_post_comment': user_can_post_comment,  # in general
        'user_already_gave_answer': user_already_gave_answer,
        'previous_answer': previous_answer,
        'tab_id': answer_sort_method,
        'similar_threads': thread.get_similar_threads(),
        'language_code': translation.get_language(),
        'paginator_context': paginator_context,
        'show_post': show_post,
        'show_comment': show_comment,
        'show_comment_position': show_comment_position,
        'enable_comments': module == const.NODE_MODULE_QA,
        'thread': thread,
        'module': module,
        "posts_per_pages": posts_per_pages,
    }

    # show last visit for posts (comments, ...)
    try:
        thread_view = thread.viewed.get(user=request.user)
        thread_view_last_visit = thread_view.last_visit

    except (ObjectDoesNotExist, TypeError):
        # print 8*'-', 'EXCEPT'
        thread_view = None
        thread_view_last_visit = datetime.datetime.now()

    # print thread_view_last_visit
    # thread_view_last_visit = datetime.datetime(2000,1,1,15,00)

    data.update({
        "thread_view": thread_view,
        "thread_view_last_visit": thread_view_last_visit
    })

    data.update(context.get_for_tag_editor())

    thread.visit(request.user)

    # future functions
    template = 'node/%s/detail.html' % thread.thread_type

    return render_into_skin(template, data, request)
