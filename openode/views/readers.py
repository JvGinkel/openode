# -*- coding: utf-8 -*-
"""
:synopsis: views "read-only" for main textual content

By main textual content is meant - text of Questions, Answers and Comments.
The "read-only" requirement here is not 100% strict, as for example "question" view does
allow adding new comments via Ajax form post.
"""

import datetime
import operator
import os

from django.conf import settings
from django.views.decorators import csrf
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage
from django.core.urlresolvers import reverse
from django.contrib.humanize.templatetags import humanize
from django.contrib.auth.models import User
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    Http404,
    HttpResponseNotAllowed,
    QueryDict,
    )
from django.shortcuts import get_object_or_404
from django.template import Context
from django.utils import simplejson, translation
from django.utils.html import escape
from django.utils.translation import ugettext as _, ungettext
from jinja2 import Environment, FileSystemLoader

from openode import conf, const, models, schedules
from openode.conf import settings as openode_settings
from openode.models import StaticPage
from openode.models.actuality import Actuality
from openode.models.node import Node
from openode.models.post import Post
from openode.models.tag import Tag
from openode.models.thread import ThreadCategory, Thread
from openode.utils import JsonResponse
from openode.utils import functions
from openode.utils.decorators import anonymous_forbidden, ajax_only, get_only
from openode.utils.diff import textDiff as htmldiff
from openode.utils.html import bleach_html
from openode.utils.http import render_forbidden
from openode.views.node import node_ask_to_join
from openode.search.state_manager import SearchState
from openode.skins.loaders import render_into_skin, get_template  # jinja2 template loading enviroment
from openode.templatetags import extra_tags
from openode.views.thread import thread as thread_detail_view


#######################################


# used in index page
#TODO: - take these out of const or settings

INDEX_PAGE_SIZE = 30
INDEX_TAGS_SIZE = 25
# used in tags list
DEFAULT_PAGE_SIZE = 60
# used in questions
# used in answers

OPENED_NODES_KEY = "opened_nodes___"
OPENED_CATEGORIES_KEY = "opened_categories___"
DISPLAY_MODE_KEY = "display_mode"

DISPLAY_MODE_ACTIVE = 1
DISPLAY_MODE_ACTIVE_AND_CLOSED = 2
# DISPLAY_MODES = {
#     1: DISPLAY_MODE_ACTIVE,
#     2: DISPLAY_MODE_ACTIVE_AND_CLOSED,
# }

#######################################

#refactor? - we have these
#views that generate a listing of questions in one way or another:
#index, unanswered, questions, search, tag
#should we dry them up?
#related topics - information drill-down, search refinement

# from openode.search.state_manager import SearchState


def _render_homepage_content_fx(request):
    """
        return content - loaded from template - for homepage
    """
    env = Environment(loader=FileSystemLoader([
        os.path.join(settings.PROJECT_ROOT, "templates"),
        os.path.join(settings.OPENODE_ROOT, "templates"),
    ]))

    template = env.get_template("homepage_content_%s.html" % request.LANGUAGE_CODE)
    return template.render(**{
        "request": request
    })


def index(request):  # generates front page - shows listing of questions sorted in various ways
    """index view mapped to the root url of the site
    """
    # actuality
    try:
        latest_actuality = Actuality.objects.latest("created")
    except Actuality.DoesNotExist:
        latest_actuality = None

    contributors = User.objects.filter(
        is_active=True, is_hidden=False,
        id__in=Post.objects.values_list('author', flat=True)
    ).order_by('avatar_type', '?')[:12] #todo to live settings

    tags = Tag.objects.filter(
        used_count__gte=1
    )[:10]

    # set and store display mode
    _mode = request.session.setdefault(DISPLAY_MODE_KEY, None)
    try:
        dm = int(request.GET.get("dm"))
    except (TypeError, ValueError):
        dm = _mode or DISPLAY_MODE_ACTIVE
    if dm in [DISPLAY_MODE_ACTIVE, DISPLAY_MODE_ACTIVE_AND_CLOSED]:
        mode = dm
    else:
        mode = DISPLAY_MODE_ACTIVE
    if _mode != mode:
        request.session[DISPLAY_MODE_KEY] = mode

    # filter nodes
    root_nodes_qs = Node.objects.filter(level=0, deleted=False)
    if mode == DISPLAY_MODE_ACTIVE:
        with_closed = False
        root_nodes_qs = root_nodes_qs.filter(closed=with_closed)
    else:
        with_closed = True

    # load opened nodes from session
    opened_nodes = list(
        request.session.setdefault(
            OPENED_NODES_KEY,
            set(Node.objects.filter(display_opened=True).values_list("pk", flat=True))
        )
    )

    context_dict = {
        # 'node_items': Node.objects.filter(level=0),
        "nodes": root_nodes_qs,
        "with_closed": with_closed,
        "display_mode": mode,
        "_render_homepage_content_fx": _render_homepage_content_fx,

        "latest_actuality": latest_actuality,
        "opened_nodes": simplejson.dumps(opened_nodes),

        "contributors": contributors,

        "DISPLAY_MODE_ACTIVE": DISPLAY_MODE_ACTIVE,
        "DISPLAY_MODE_ACTIVE_AND_CLOSED": DISPLAY_MODE_ACTIVE_AND_CLOSED,

        "tags": tags,
        "tag_html_tag": "li",
        "tag_list_type": "list"
    }
    return render_into_skin('homepage.html', context_dict, request)

#######################################
#######################################


def toggle_node(request):
    """
        close / open node tree and store this information to session
    """
    try:
        node_id = int(request.GET.get("node_id"))
    except (ValueError, TypeError):
        node_id = None

    opened_nodes = set(request.session.setdefault(OPENED_NODES_KEY, []))

    try:
        _node = Node.objects.get(pk=node_id)
    except Node.DoesNotExist:
        _node = None

    if node_id:
        if node_id in opened_nodes:
            # close sub node
            if _node:
                opened_nodes.difference_update(_node.get_descendants().values_list("id", flat=True))
            # close node
            opened_nodes.remove(node_id)

        # open node
        elif (_node.parent_id in opened_nodes) or (_node.level == 0):
            opened_nodes.add(node_id)

        request.session[OPENED_NODES_KEY] = opened_nodes

    return JsonResponse({})


def toggle_category(request):
    """
        close / open category tree and store this information to session
    """
    try:
        category_id = int(request.GET.get("category_id"))
    except (ValueError, TypeError):
        category_id = None

    opened_categories = set(request.session.setdefault(OPENED_CATEGORIES_KEY, []))

    try:
        _category = ThreadCategory.objects.get(pk=category_id)
    except ThreadCategory.DoesNotExist:
        _category = None

    if category_id:
        if category_id in opened_categories:
            # close sub category
            if _category:
                opened_categories.difference_update(_category.get_descendants().values_list("id", flat=True))
            # close category
            opened_categories.remove(category_id)

        # open category
        elif (_category.parent_id in opened_categories) or (_category.level == 0):
            opened_categories.add(category_id)

        request.session[OPENED_CATEGORIES_KEY] = opened_categories

    return JsonResponse({})

#######################################
#######################################


def static_page(request, slug):
    """
        static page detail page
    """
    static_page = get_object_or_404(
        StaticPage,
        slug=slug,
        language=request.LANGUAGE_CODE
    )
    to_tmpl = {
        "static_page": static_page
    }
    return render_into_skin('cms/static_page.html', to_tmpl, request)


def archive(request):
    """
        archive of Actualities
    """
    PER_PAGE = 3

    actualities = Actuality.objects.all().order_by("created")
    paginator = Paginator(actualities, PER_PAGE)

    page = request.GET.get('page')
    try:
        actualities = paginator.page(page)
    except TypeError:
        actualities = paginator.page(1)
    except EmptyPage:
        actualities = paginator.page(paginator.num_pages)

    to_tmpl = {
        "actualities": actualities,
        "paginator": paginator
    }
    return render_into_skin("cms/archive.html", to_tmpl, request)


NODE_MODULE_TEMPLATE_FILE = {
    const.NODE_MODULE_ANNOTATION: 'node/annotation/show.html',
    const.NODE_MODULE_QA: 'node/question/list.html',
    const.NODE_MODULE_FORUM: 'node/discussion/list.html',
    const.NODE_MODULE_LIBRARY: 'node/document/list.html',
}


def node_module_thread(request, node, module, **kwargs):
    search_state = SearchState(
        user_logged_in=request.user.is_authenticated(),
        node=node,
        module=module,
        **kwargs
        )
    page_size = int(openode_settings.DEFAULT_QUESTIONS_PAGE_SIZE)

    qs, meta_data = models.Thread.objects.run_advanced_search(
        request_user=request.user,
        search_state=search_state
        )
    if meta_data['non_existing_tags']:
        search_state = search_state.remove_tags(meta_data['non_existing_tags'])

    paginator = Paginator(qs, page_size)
    if paginator.num_pages < search_state.page:
        search_state.page = 1
    page = paginator.page(search_state.page)
    page.object_list = list(page.object_list)  # evaluate the queryset

    # INFO: Because for the time being we need question posts and thread authors
    #       down the pipeline, we have to precache them in thread objects

    models.Thread.objects.precache_view_data_hack(threads=page.object_list)

    related_tags = Tag.objects.get_related_to_search(
        threads=page.object_list,
        ignored_tag_names=meta_data.get('ignored_tag_names', [])
    )
    tag_list_type = openode_settings.TAG_LIST_FORMAT
    if tag_list_type == 'cloud':  # force cloud to sort by name
        related_tags = sorted(related_tags, key=operator.attrgetter('name'))

    contributors = list(
        models.Thread.objects.get_thread_contributors(
            thread_list=page.object_list
        ).only('id', 'username', 'gravatar')
    )

    paginator_context = {
        'is_paginated': (paginator.count > page_size),

        'pages': paginator.num_pages,
        'page': search_state.page,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'previous': page.previous_page_number(),
        'next': page.next_page_number(),

        'base_url': search_state.query_string(),
        'page_size': page_size,
    }

    # We need to pass the rss feed url based
    # on the search state to the template.
    # We use QueryDict to get a querystring
    # from dicts and arrays. Much cleaner
    # than parsing and string formating.
    rss_query_dict = QueryDict("").copy()
    if search_state.query:
        # We have search string in session - pass it to
        # the QueryDict
        rss_query_dict.update({"q": search_state.query})
    if search_state.tags:
        # We have tags in session - pass it to the
        # QueryDict but as a list - we want tags+
        rss_query_dict.setlist("tags", search_state.tags)

    reset_method_count = len(filter(None, [search_state.query, search_state.tags, meta_data.get('author_name', None)]))

    if request.is_ajax():
        # q_count = paginator.count

        # question_counter = ungettext('%(q_num)s question', '%(q_num)s questions', q_count)
        # question_counter = question_counter % {'q_num': humanize.intcomma(q_count)}

        # if q_count > page_size:
        #     paginator_tpl = get_template('node/paginator.html', request)
        #     paginator_html = paginator_tpl.render(Context({
        #         'context': functions.setup_paginator(paginator_context),
        #         'questions_count': q_count,
        #         'page_size': page_size,
        #         'search_state': search_state,
        #     }))
        # else:
        #     paginator_html = ''

        # questions_tpl = get_template('node/questions_loop.html', request)
        # questions_html = questions_tpl.render(Context({
        #     'threads': page,
        #     'search_state': search_state,
        #     'reset_method_count': reset_method_count,
        #     'request': request
        # }))

        # ajax_data = {
        #     'query_data': {
        #         'tags': search_state.tags,
        #         'sort_order': search_state.sort,
        #         'ask_query_string': search_state.ask_query_string(),
        #     },
        #     'paginator': paginator_html,
        #     'question_counter': question_counter,
        #     'faces': [],  # [extra_tags.gravatar(contributor, 48) for contributor in contributors],
        #     'query_string': search_state.query_string(),
        #     'page_size': page_size,
        #     'questions': questions_html.replace('\n', ''),
        #     'non_existing_tags': meta_data['non_existing_tags']
        # }
        # ajax_data['related_tags'] = [{
        #     'name': escape(tag.name),
        #     'used_count': humanize.intcomma(tag.local_used_count)
        # } for tag in related_tags]

        ajax_data = {"msg": "bad request"}
        node.visit(request.user)
        return HttpResponse(simplejson.dumps(ajax_data), mimetype='application/json')

    else:  # non-AJAX branch

        template_data = {

            # ThreadCategory Tree root
            "categories": node.thread_categories.filter(level=0),

            'active_tab': 'questions',
            'author_name': meta_data.get('author_name', None),
            'contributors': contributors,
            'context': paginator_context,
            'is_unanswered': False,  # remove this from template
            'interesting_tag_names': meta_data.get('interesting_tag_names', None),
            'ignored_tag_names': meta_data.get('ignored_tag_names', None),
            'subscribed_tag_names': meta_data.get('subscribed_tag_names', None),
            'language_code': translation.get_language(),
            'name_of_anonymous_user': models.get_name_of_anonymous_user(),
            'page_class': 'main-page',
            'page_size': page_size,
            'threads': page,
            'questions_count': paginator.count,
            'reset_method_count': reset_method_count,
            'tags': related_tags,
            'tag_list_type': tag_list_type,
            'font_size': extra_tags.get_tag_font_size(related_tags),
            'display_tag_filter_strategy_choices': conf.get_tag_display_filter_strategy_choices(),
            'email_tag_filter_strategy_choices': const.TAG_EMAIL_FILTER_STRATEGY_CHOICES,
            'update_avatar_data': schedules.should_update_avatar_data(request),
            'search_state': search_state,
            'node': node,
            'module': module
        }

        # load opened nodes from session
        opened_categories = list(
            request.session.setdefault(
                OPENED_CATEGORIES_KEY,
                set()
                # set(ThreadCategory.objects.filter(display_opened=True).values_list("pk", flat=True))
            )
        )
        template_data.update({"opened_categories": opened_categories})

        template_file = NODE_MODULE_TEMPLATE_FILE[module]

        if module == 'library':

            # get categories (with path to root) with thread (documents) with is unread
            # maybe is better way to create document/category tree structure in python and in template only render.

            categories_ids_witn_unread_thread = set()

            def _recursively(categories):
                for category in categories.iterator():
                    for thread in category.threads.iterator():
                        if thread.has_unread_main_post_for_user(request.user):
                            categories_ids_witn_unread_thread.update(
                                category.get_ancestors(include_self=True).values_list("pk", flat=True)
                            )
                            break
                    _recursively(category.get_children())
            _recursively(node.thread_categories.filter(level=0))

            ####################################################################

            template_data.update({
                "free_threads": node.threads.filter(is_deleted=False, category=None, thread_type=const.THREAD_TYPE_DOCUMENT).order_by("title"),  # Thread.objects.filter(thread__node=node, thread__category=None).select_related("thread"),
                "categories_ids_witn_unread_thread": categories_ids_witn_unread_thread
                # "categorized_threads": node.threads.exclude(category=None),  # Thread.objects.filter(thread__node=node, thread__category=None).select_related("thread"),
                # "free_documents": Document.objects.filter(thread__node=node, thread__category=None).select_related("thread"),
                # "category_documents": Document.objects.filter(thread__node=node).exclude(thread__category=None),
            })
        node.visit(request.user)
        return render_into_skin(template_file, template_data, request)


def node_module_forum(request, node_id, node_slug, module, **kwargs):
    """
    Forum module bypass. Direct render only one discussion
    """

    node = get_object_or_404(Node, pk=node_id, module_forum=True)
    thread_qs = node.threads.filter(
        thread_type=const.THREAD_TYPE_BY_NODE_MODULE[module]
    )[:1]

    if thread_qs:
        thread = thread_qs[0]
    else:
        post = request.user.post_thread(
            title=node.title,
            body_text="",
            timestamp=datetime.datetime.now(),
            node=node,
            thread_type=const.THREAD_TYPE_BY_NODE_MODULE[module]
        )
        thread = post.thread
    return HttpResponseRedirect(thread.get_absolute_url())


def node_module(request, node_id, node_slug, module, **kwargs):
    """
    node detail modulu

    thread_type -> setup Thread.thread_type or summary
    """

    # bypass for forum module
    if module == const.NODE_MODULE_FORUM:
        return node_module_forum(request, node_id, node_slug, module, **kwargs)

    node = get_object_or_404(Node, pk=node_id)

    if module in node.get_modules() and module not in [m[0] for m in node.get_modules()]:
        raise Http404()

    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_module', kwargs={'node_id': node.pk, 'node_slug': node.slug, 'module': module}))

    if not request.user.has_openode_perm('node_read', node):
        if node.visibility == const.NODE_VISIBILITY_SEMIPRIVATE:
            return node_ask_to_join(request, node.pk, node.slug)
        return render_forbidden(request)

    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    if module in const.THREAD_TYPE_BY_NODE_MODULE:
        return node_module_thread(request, node, module, **kwargs)

    template_file = NODE_MODULE_TEMPLATE_FILE[module]
    template_data = {'node': node, 'module': module}
    return render_into_skin(template_file, template_data, request)


def revisions(request, id, post_type=None):
    assert post_type in ('question', 'answer')
    post = get_object_or_404(models.Post, post_type=post_type, id=id)
    revisions = list(models.PostRevision.objects.filter(post=post))
    revisions.reverse()
    for i, revision in enumerate(revisions):
        if i == 0:
            revision.diff = bleach_html(revisions[i].html)
            revision.summary = _('initial version')
        else:
            revision.diff = htmldiff(
                bleach_html(revisions[i - 1].html),
                bleach_html(revision.html)
            )

    data = {
        'page_class': 'revisions-page',
        'active_tab': 'questions',
        'post': post,
        'revisions': revisions,
    }
    return render_into_skin('revisions.html', data, request)


@csrf.csrf_exempt
@ajax_only
@anonymous_forbidden
@get_only
def get_comment(request):
    """returns text of a comment by id
    via ajax response requires request method get
    and request must be ajax
    """
    id = int(request.GET['id'])
    comment = models.Post.objects.get(post_type='comment', id=id)
    request.user.assert_can_edit_comment(comment)
    return {'text': comment.text}


def set_lang(request):
    language = request.GET.get('language', '')
    if language in [lang[0] for lang in getattr(settings, 'LANGUAGES', ())]:
        request.session['language'] = language
    next = request.GET.get('next', '/')
    return HttpResponseRedirect(next)


def thread_followers(request, node_id, node_slug, module, thread_id, thread_slug):

    node = get_object_or_404(Node, pk=node_id)
    thread = get_object_or_404(Thread, pk=thread_id, node=node)

    if node.slug != node_slug or thread.slug != thread_slug:
        return HttpResponseRedirect(reverse('thread_followers', kwargs={
            'node_id': node_id,
            'node_slug': node.slug,
            'module': module,
            'thread_id': thread_id,
            'thread_slug': thread.slug,
        }))

    data = {
        'follows': thread.thread_following_users.order_by("-added_at"),
        'thread': thread,
        'node': node,
        "can_make_remove_from_followers": node.node_users.filter(user=request.user, role=const.NODE_USER_ROLE_MANAGER).exists()
    }

    return render_into_skin('node/%s/followers.html' % thread.thread_type, data, request)


def thread_last_visit(request, node_id, node_slug, module, thread_id, thread_slug):
    """
    """
    LIMIT = 100
    node = get_object_or_404(Node, pk=node_id)
    thread = get_object_or_404(Thread, pk=thread_id, node=node)

    if node.slug != node_slug or thread.slug != thread_slug:
        return HttpResponseRedirect(reverse('thread_last_visit', kwargs={
            'node_id': node_id,
            'node_slug': node.slug,
            'module': module,
            'thread_id': thread_id,
            'thread_slug': thread.slug
        }))

    data = {
        'thread_viewed': thread.viewed.all().order_by("-last_visit")[:LIMIT],
        'thread': thread,
        "is_limit_overflow": thread.viewed.count() > LIMIT
    }

    return render_into_skin('node/%s/last_visit.html' % thread.thread_type, data, request)


def discussion_answer(request, pk):
    try:
        post = Post.objects.get(pk=pk)
        thread = post.thread
        node = thread.node
    except ObjectDoesNotExist:
        raise Http404

    if not request.user.has_openode_perm('discussion_read', node):
        return render_forbidden(request)

    to_tmpl = {
        "answer": post,
        "posts_per_pages": {}
    }
    return render_into_skin('node/discussion/discussion_answer.html', to_tmpl, request)
