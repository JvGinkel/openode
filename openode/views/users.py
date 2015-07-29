# -*- coding: utf-8 -*-

"""
:synopsis: user-centric views for openode

This module includes all views that are specific to a given user - his or her profile,
and other views showing profile-related information.

Also this module includes the view listing all forum users.
"""

import collections
import datetime
import functools
import logging
import urllib
from urlparse import urlparse

from django.db.models import Count
from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render as django_render
from django.http import HttpResponse, HttpResponseForbidden
from django.http import HttpResponseRedirect, Http404
from django.utils.translation import ugettext as _
from django.utils import simplejson
from django.views.decorators import csrf

from openode.const.perm_rules import RULES, MEMBERS_RULES

from openode import const, forms, models  # , exceptions
from openode.conf import settings as openode_settings
from openode.forms.organization import OrganizationLogoForm
from openode.forms.user import UserEmailForm, EditUserForm, QuestionFlowNodeResponsibleUsersForm
from openode.mail import send_mail
from openode.models.tag import get_organizations
from openode.models.thread import Thread
from openode.skins.loaders import render_into_skin
from openode.search.state_manager import SearchState
from openode.skins.loaders import get_template
from openode.utils import functions, url_utils
from openode.utils.html import bleach_html
from openode.utils.http import render_forbidden
from openode.utils.http import get_request_info
from openode.utils.slug import slugify
# from openode.views import context as view_context

################################################################################


def owner_or_moderator_required(f):
    @functools.wraps(f)
    def wrapped_func(request, profile_owner, context):
        if profile_owner == request.user:
            pass
        elif request.user.is_authenticated() and request.user.can_moderate_user(profile_owner):
            pass
        else:
            next_url = request.path + '?' + urllib.urlencode(request.REQUEST)
            params = '?next=%s' % urllib.quote(next_url)
            return HttpResponseRedirect(url_utils.get_login_url() + params)
        return f(request, profile_owner, context)
    return wrapped_func


@login_required
def show_perm_table(request):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    rules = RULES.keys()
    # members_rules = MEMBERS_RULES.keys()
    # print members_rules

    permissions = sorted(set(
        RULES["node_visibility_public"].keys() + MEMBERS_RULES[const.NODE_USER_ROLE_MANAGER].keys()
    ))

    _map = [
        ('node_visibility_public', RULES),
        ('node_visibility_registered_users', RULES),
        ('user_loggedin', RULES),
        ('node_visibility_private', RULES),
        ('node_visibility_semiprivate', RULES),
        ('thread_external_access', RULES),
        ('member', MEMBERS_RULES),
        ('document-manager', MEMBERS_RULES),
        ('readonly', MEMBERS_RULES),
        ('manager', MEMBERS_RULES),
        ('thread_is_closed', RULES),
        ('node_qa_is_readonly', RULES),
        ('node_forum_is_readonly', RULES),
        ('node_library_is_readonly', RULES),
        ('node_is_closed', RULES),
        ('node_is_deleted', RULES),
    ]

    rules = []
    for rule, data in _map:
        rules.append([rule, data[rule]])

    to_tmpl = {
        "rules": rules,
        "permissions": permissions,
    }
    return django_render(request, 'admin/show_perm_table.html', to_tmpl)


def show_users(request):
    """Users view, including listing of users by organization"""
    if not request.user.is_authenticated():
        return render_forbidden(request)

    users = models.User.objects.filter(is_active=True, is_hidden=False).exclude(status='b')
    organization = None
    logo_form = None
    sortby = request.GET.get('sort', 'last_name')

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    search_query = request.REQUEST.get('query',  "")
    if search_query == "":
        if sortby == "newest":
            order_by_parameter = ('-date_joined',)
        elif sortby == "last":
            order_by_parameter = ('date_joined',)
        elif sortby == "last_name":
            order_by_parameter = ('last_name', 'first_name')
        else:
            # default
            order_by_parameter = ('last_name', 'first_name')

        objects_list = Paginator(
                            users.order_by(*order_by_parameter),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?sort=%s&amp;' % sortby
    else:
        sortby = "last_name"
        matching_users = models.get_users_by_text_query(search_query, users)
        objects_list = Paginator(
                            matching_users.order_by(*('last_name', 'first_name')),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?name=%s&amp;sort=%s&amp;' % (search_query, sortby)

    try:
        users_page = objects_list.page(page)
    except (EmptyPage, InvalidPage):
        users_page = objects_list.page(objects_list.num_pages)

    paginator_data = {
        'is_paginated': bool(objects_list.count > const.USERS_PAGE_SIZE),
        'pages': objects_list.num_pages,
        'page': page,
        'has_previous': users_page.has_previous(),
        'has_next': users_page.has_next(),
        'previous': users_page.previous_page_number(),
        'next': users_page.next_page_number(),
        'base_url': base_url
    }
    paginator_context = functions.setup_paginator(paginator_data)

    data = {
        'active_tab': 'users',
        'page_class': 'users-page',
        'users': users_page,
        'organization': organization,
        'search_query': search_query,
        'tab_id': sortby,
        'paginator_context': paginator_context,
        "logo_form": logo_form,
    }

    return render_into_skin('user_list.html', data, request)


def organization_detail(request, organization_id, organization_slug):
    if not request.user.is_authenticated():
        return render_forbidden(request)

    user_acceptance_level = 'closed'
    user_membership_level = 'none'
    try:
        organization = models.Organization.objects.get(id=organization_id)
        user_acceptance_level = organization.get_openness_level_for_user(
                                                                    request.user
                                                                )
    except models.Organization.DoesNotExist:
        raise Http404

    ################################################################
    # upload organization logo

    logo_form = OrganizationLogoForm(instance=organization)
    if request.method == "POST":
        logo_form = OrganizationLogoForm(request.POST, request.FILES, instance=organization)
        if logo_form.is_valid():
            logo_form.save()
            return HttpResponseRedirect(request.path)

    ################################################################

    if organization_slug == slugify(organization.title):
        users = models.User.objects.exclude(status='b')
        #filter users by full organization memberships
        #todo: refactor as Organization.get_full_members()
        full_level = models.OrganizationMembership.FULL
        memberships = models.OrganizationMembership.objects.filter(
                                        organization=organization, level=full_level
                                    )
        user_ids = memberships.values_list('user__id', flat=True)
        users = users.filter(id__in=user_ids)
        if request.user.is_authenticated():
            membership = request.user.get_organization_membership(organization)
            if membership:
                user_membership_level = membership.get_level_display()

    else:
        organization_page_url = reverse(
                            'organization_detail',
                            kwargs={
                                'organization_id': organization.id,
                                'organization_slug': slugify(organization.title)
                            }
                        )
        return HttpResponseRedirect(organization_page_url)

    sortby = request.GET.get('sort', 'last_name')

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    search_query = request.REQUEST.get('query',  "")
    if search_query == "":
        if sortby == "newest":
            order_by_parameter = ('-date_joined',)
        elif sortby == "last":
            order_by_parameter = ('date_joined',)
        elif sortby == "user":
            order_by_parameter = ('last_name', 'first_name')
        else:
            # default
            order_by_parameter = ('last_name', 'first_name')

        objects_list = Paginator(
                            users.order_by(*order_by_parameter),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?sort=%s&amp;' % sortby
    else:
        sortby = "last_name"
        matching_users = models.get_users_by_text_query(search_query, users)
        objects_list = Paginator(
                            matching_users.order_by(*('last_name', 'first_name')),
                            const.USERS_PAGE_SIZE
                        )
        base_url = request.path + '?name=%s&amp;sort=%s&amp;' % (search_query, sortby)

    try:
        users_page = objects_list.page(page)
    except (EmptyPage, InvalidPage):
        users_page = objects_list.page(objects_list.num_pages)

    paginator_data = {
        'is_paginated': bool(objects_list.count > const.USERS_PAGE_SIZE),
        'pages': objects_list.num_pages,
        'page': page,
        'has_previous': users_page.has_previous(),
        'has_next': users_page.has_next(),
        'previous': users_page.previous_page_number(),
        'next': users_page.next_page_number(),
        'base_url': base_url
    }
    paginator_context = functions.setup_paginator(paginator_data)

    #todo: cleanup this branched code after organizations are migrated to auth_organization
    user_organizations = get_organizations().all()
    if len(user_organizations) <= 1:
        user_organizations = None
    organization_openness_choices = models.Organization().get_openness_choices()

    data = {
        'active_tab': 'users',
        'page_class': 'users-page',
        'users': users_page,
        'organization': organization,
        'search_query': search_query,
        'tab_id': sortby,
        'paginator_context': paginator_context,
        'user_acceptance_level': user_acceptance_level,
        'user_membership_level': user_membership_level,
        'user_organizations': user_organizations,
        'organization_openness_choices': organization_openness_choices,
        "logo_form": logo_form,
    }

    return render_into_skin('organization_detail.html', data, request)


#non-view function
def set_new_email(user, new_email, nomessage=False):
    if new_email != user.email:
        user.email = new_email
        user.email_isvalid = False
        user.save()
        #if openode_settings.EMAIL_VALIDATION == True:
        #    send_new_email_key(user,nomessage=nomessage)


@login_required
@csrf.csrf_protect
def edit_user(request, id):
    """View that allows to edit user profile.
    This view is accessible to profile owners or site administrators
    """
    user = get_object_or_404(models.User, id=id)
    if not(request.user == user or request.user.is_superuser):
        raise Http404
    if request.method == "POST":
        form = EditUserForm(user, request.POST)
        if form.is_valid():
            # new_email = bleach_html(form.cleaned_data['email'])

            # set_new_email(user, new_email)

            user.first_name = bleach_html(form.cleaned_data['first_name'])
            user.last_name = bleach_html(form.cleaned_data['last_name'])
            user.display_name = bleach_html(form.cleaned_data['display_name'])
            user.privacy_email_form = form.cleaned_data['privacy_email_form']
            user.privacy_show_followed = form.cleaned_data['privacy_show_followed']
            user.save()

            description = form.cleaned_data['user_description']

            if user.description:
                request.user.edit_post(user.description, body_text=description)
            else:
                request.user.post_object_description(user, body_text=description)

            # send user updated signal if full fields have been updated
            request.user.message_set.create(message=_('Profile has been succesfully saved.'))
            return HttpResponseRedirect(user.get_profile_url())
    else:
        form = EditUserForm(user)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-edit-page',
        'form': form,
        'marked_tags_setting': openode_settings.MARKED_TAGS_ARE_PUBLIC_WHEN,
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'view_user': user,
    }
    return render_into_skin('user_profile/user_edit.html', data, request)


def user_overview(request, user, context):
    question_filter = {}

    #
    # Questions
    #
    questions = user.posts.get_questions(
        user=request.user
    ).filter(
        **question_filter
    ).order_by(
        '-points', '-thread__last_activity_at'
    ).select_related(
        'thread', 'thread__last_activity_by'
    )[:100]

    #added this if to avoid another query if questions is less than 100
    if len(questions) < 100:
        question_count = len(questions)
    else:
        question_count = user.posts.get_questions().filter(**question_filter).count()

    #
    # Top answers
    #
    top_answers = user.posts.get_answers(
        request.user
    ).filter(
        deleted=False,
        thread__posts__deleted=False,
        thread__posts__post_type='question',
    ).select_related(
        'thread'
    ).order_by(
        '-points', '-added_at'
    )[:100]

    top_answer_count = len(top_answers)
    #
    # Votes
    #
    up_votes = models.Vote.objects.get_up_vote_count_from_user(user)
    down_votes = models.Vote.objects.get_down_vote_count_from_user(user)
    votes_today = models.Vote.objects.get_votes_count_today_from_user(user)
    votes_total = openode_settings.MAX_VOTES_PER_USER_PER_DAY

    #
    # Tags
    #
    # INFO: There's bug in Django that makes the following query kind of broken (GROUP BY clause is problematic):
    #       http://stackoverflow.com/questions/7973461/django-aggregation-does-excessive-organization-by-clauses
    #       Fortunately it looks like it returns correct results for the test data
    user_tags = models.Tag.objects.filter(
        threads__posts__author=user
    ).distinct().annotate(
        user_tag_usage_count=Count('threads')
    ).order_by(
        '-user_tag_usage_count'
    )[:const.USER_VIEW_DATA_SIZE]
    user_tags = list(user_tags)  # evaluate

    when = openode_settings.MARKED_TAGS_ARE_PUBLIC_WHEN
    if when == 'always' or \
        (when == 'when-user-wants' and user.show_marked_tags == True):
        #refactor into: user.get_marked_tag_names('good'/'bad'/'subscribed')
        interesting_tag_names = user.get_marked_tag_names('good')
        ignored_tag_names = user.get_marked_tag_names('bad')
        subscribed_tag_names = user.get_marked_tag_names('subscribed')
    else:
        interesting_tag_names = None
        ignored_tag_names = None
        subscribed_tag_names = None

#    tags = models.Post.objects.filter(author=user).values('id', 'thread', 'thread__tags')
#    post_ids = set()
#    thread_ids = set()
#    tag_ids = set()
#    for t in tags:
#        post_ids.add(t['id'])
#        thread_ids.add(t['thread'])
#        tag_ids.add(t['thread__tags'])
#        if t['thread__tags'] == 11:
#            print t['thread'], t['id']
#    import ipdb; ipdb.set_trace()

    #
    #
    # post_type = ContentType.objects.get_for_model(models.Post)

    if request.user != user and request.user.is_authenticated() and user.privacy_email_form:
        if request.method == 'POST':
            email_form = UserEmailForm(request.POST)
            if email_form.is_valid():
                subject = email_form.cleaned_data['subject']
                text = email_form.cleaned_data['text']
                url = urlparse(openode_settings.APP_URL)
                data = {
                    'from_user_url': url.scheme + '://' + url.netloc + reverse('user_profile', args=[request.user.pk]),
                    'from_user_screen_name': request.user.screen_name,
                    'text': text,
                    "request": request
                }
                template = get_template('email/user_profile_email.html')
                message = template.render(data)

                send_mail(subject_line=subject,
                    body_text=message,
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                )

                request.user.log(user, const.LOG_ACTION_SEND_EMAIL_TO_USER)
                request.user.message_set.create(message=_('Email has been succesfully sent.'))
                email_form = UserEmailForm()
        else:
            email_form = UserEmailForm()
    else:
        email_form = None

    # if request.user.is_authenticated():
    #     managed_nodes = user.nodes.filter(node_users__role=const.NODE_USER_ROLE_MANAGER)
    # else:
    #     managed_nodes = None

    # TODO not all variables are necessary
    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'support_custom_avatars': ('avatar' in django_settings.INSTALLED_APPS),
        'tab_description': _('user profile'),
        'page_title': _('user profile overview'),
        'user_status_for_display': user.get_status_display(soft=True),
        'questions': questions,
        'question_count': question_count,

        'top_answers': top_answers,
        'top_answer_count': top_answer_count,

        'up_votes': up_votes,
        'down_votes': down_votes,
        'total_votes': up_votes + down_votes,
        'votes_today_left': votes_total - votes_today,
        'votes_total_per_day': votes_total,

        # 'managed_nodes': managed_nodes,
        'user_tags': user_tags,
        'interesting_tag_names': interesting_tag_names,
        'ignored_tag_names': ignored_tag_names,
        'subscribed_tag_names': subscribed_tag_names,
        'email_form': email_form
    }
    context.update(data)

    view_user = context.get('view_user')
    if view_user is not None and not view_user.is_active:
        return render_into_skin('user_profile/user_overview_disabled.html', context, request)

    return render_into_skin('user_profile/user_overview.html', context, request)


# def user_activity(request, user, context):

#     def get_type_name(type_id):
#         for item in const.TYPE_ACTIVITY:
#             if type_id in item:
#                 return item[1]

#     class Event(object):

#         def __init__(self, time, type, title, summary, answer, question):
#             self.time = time
#             self.type = get_type_name(type)
#             self.type_id = type
#             self.title = title
#             self.summary = summary
#             node = question.thread.node
#             self.title_link = question.thread.get_absolute_url()
#             if answer:
#                 self.title_link += '#%s' % answer.id

#     activities = []

#     # TODO: Don't process all activities here for the user, only a subset ([:const.USER_VIEW_DATA_SIZE])
#     for activity in models.Activity.objects.filter(user=user):

#         # TODO: multi-if means that we have here a construct for which a design pattern should be used

#         # ask questions
#         if activity.activity_type == const.TYPE_ACTIVITY_ASK_QUESTION:
#             q = activity.content_object
#             if not q.deleted:
#                 activities.append(Event(
#                     time=activity.active_at,
#                     type=activity.activity_type,
#                     title=q.thread.title,
#                     summary='',  # q.summary,  # TODO: was set to '' before, but that was probably wrong
#                     answer=None,
#                     question=q,
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_ANSWER:
#             ans = activity.content_object
#             question = ans.thread._main_post()
#             if not ans.deleted and not question.deleted:
#                 activities.append(Event(
#                     time=activity.active_at,
#                     type=activity.activity_type,
#                     title=ans.thread.title,
#                     summary=question.summary,
#                     answer=ans,
#                     question=question
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_COMMENT_QUESTION:
#             cm = activity.content_object
#             q = cm.parent
#             assert q.is_question()
#             if not q.deleted:
#                 activities.append(Event(
#                     time=cm.added_at,
#                     type=activity.activity_type,
#                     title=q.thread.title,
#                     summary='',
#                     answer=None,
#                     question=q
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_COMMENT_ANSWER:
#             cm = activity.content_object
#             ans = cm.parent
#             assert ans.is_answer()
#             question = ans.thread._main_post()
#             if not ans.deleted and not question.deleted:
#                 activities.append(Event(
#                     time=cm.added_at,
#                     type=activity.activity_type,
#                     title=ans.thread.title,
#                     summary='',
#                     answer=ans,
#                     question=question
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_UPDATE_QUESTION:
#             q = activity.content_object
#             if not q.deleted:
#                 activities.append(Event(
#                     time=activity.active_at,
#                     type=activity.activity_type,
#                     title=q.thread.title,
#                     summary=q.summary,
#                     answer=None,
#                     question=q
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_UPDATE_ANSWER:
#             ans = activity.content_object
#             question = ans.thread._main_post()
#             if not ans.deleted and not question.deleted:
#                 activities.append(Event(
#                     time=activity.active_at,
#                     type=activity.activity_type,
#                     title=ans.thread.title,
#                     summary=ans.summary,
#                     answer=ans,
#                     question=question
#                 ))

#         elif activity.activity_type == const.TYPE_ACTIVITY_MARK_ANSWER:
#             ans = activity.content_object
#             question = ans.thread._main_post()
#             if not ans.deleted and not question.deleted:
#                 activities.append(Event(
#                     time=activity.active_at,
#                     type=activity.activity_type,
#                     title=ans.thread.title,
#                     summary='',
#                     answer=None,
#                     question=question
#                 ))

#     activities.sort(key=operator.attrgetter('time'), reverse=True)

#     data = {
#         'active_tab': 'users',
#         'page_class': 'user-profile-page',
#         'tab_name': 'activity',
#         'tab_description': _('recent user activity'),
#         'page_title': _('profile - recent activity'),
#         'activities': activities[:const.USER_VIEW_DATA_SIZE]
#     }
#     context.update(data)
#     return render_into_skin('user_profile/user_activity.html', context, request)

#not a view - no direct url route here, called by `user_responses`
@csrf.csrf_protect
def user_organization_join_requests(request, user, context):
    """show Unresolved Organization join requests"""
    if request.user.is_admin('openode.resolve_organization_joining') is False:
        raise Http404

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('organization joining requests'),
        'page_title': _('profile - organization joins')
    }
    context.update(data)
    return render_into_skin('user_profile/organization_pending_memberships.html', context, request)


#not a view - no direct url route here, called by `user_responses`
@csrf.csrf_protect
def user_node_join_requests(request, user, context):
    """show Unresolved Node join requests"""

    user_has_perm_resolve_node_joining = models.NodeUser.objects.filter(
        user=user,
        role=const.NODE_USER_ROLE_MANAGER
    ).exists()

    if not user_has_perm_resolve_node_joining:
        raise Http404

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('node joining requests'),
        'page_title': _('profile - node joins')
    }
    context.update(data)
    return render_into_skin('user_profile/node_join_requests.html', context, request)


#not a view - no direct url route here, called by `user_responses`
@csrf.csrf_protect
def user_node_create_requests(request, user, context):
    """show Unresolved Node create requests"""

    # user has perm resolve node creating
    if not (user.is_staff and user.has_perm('openode.add_node')):
        raise Http404

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('requests to create nodes'),
        'page_title': _('profile - node requests')
    }
    context.update(data)
    return render_into_skin('user_profile/node_create_requests.html', context, request)


#not a view - no direct url route here, called by `user_responses`
@csrf.csrf_protect
def organization_requests(request, user, context):
    """show Unresolved Node join requests"""
    if not request.user.is_admin('openode.add_organization'):
        raise Http404

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('Organization requests'),
        'page_title': _('profile - organization requests')
    }
    context.update(data)
    return render_into_skin('user_profile/organization_requests.html', context, request)


@owner_or_moderator_required
def user_offensive_flags_reports(request, user, context):
    """
    We list answers for question, comments, and
    answer accepted by others for this user.
    as well as mentions of the user

    user - the profile owner

    the view has two sub-views - "forum" - i.e. responses
    and "flags" - moderation items for mods only
    """

    if not openode_settings.ENABLE_MARK_OFFENSIVE_FLAGS or not request.user.is_admin('openode.resolve_flag_offensive'):
        raise Http404

    activity_types = (const.TYPE_ACTIVITY_MARK_OFFENSIVE,)

    #2) load the activity notifications according to activity types
    #todo: insert pagination code here
    memo_set = request.user.get_notifications(activity_types)
    memo_set = memo_set.select_related(
                    'activity',
                    'activity__content_type',
                    'activity__question__thread',
                    'activity__user',
                    'activity__user__gravatar',
                ).order_by(
                    '-activity__active_at'
                )[:const.USER_VIEW_DATA_SIZE]

    #3) "package" data for the output
    response_list = list()
    for memo in memo_set:
        if memo.activity.content_object is None:
            continue  # a temp plug due to bug in the comment deletion
        response = {
            'id': memo.id,
            'timestamp': memo.activity.active_at,
            'user': memo.activity.user,
            'is_new': memo.is_new(),
            'response_url': memo.activity.get_absolute_url(),
            'response_snippet': memo.activity.get_snippet(),
            'response_title': memo.activity.question.thread.title,
            'response_type': memo.activity.get_activity_type_display(),
            'response_id': memo.activity.question.id,
            'nested_responses': [],
            'response_content': memo.activity.content_object.html,
        }
        response_list.append(response)

    #4) sort by response id
    response_list.sort(lambda x, y: cmp(y['response_id'], x['response_id']))

    #5) organization responses by thread (response_id is really the question post id)
    last_response_id = None  # flag to know if the response id is different
    filtered_response_list = list()
    for i, response in enumerate(response_list):
        #todo: organization responses by the user as well
        if response['response_id'] == last_response_id:
            original_response = dict.copy(filtered_response_list[len(filtered_response_list) - 1])
            original_response['nested_responses'].append(response)
            filtered_response_list[len(filtered_response_list) - 1] = original_response
        else:
            filtered_response_list.append(response)
            last_response_id = response['response_id']

    #6) sort responses by time
    filtered_response_list.sort(lambda x, y: cmp(y['timestamp'], x['timestamp']))

    reject_reasons = models.PostFlagReason.objects.all().order_by('title')
    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('comments and answers to others questions'),
        'page_title': _('profile - responses'),
        'post_reject_reasons': reject_reasons,
        'responses': filtered_response_list,
    }
    context.update(data)
    return render_into_skin('user_profile/responses_and_flags.html', context, request)


def user_logs(request, user, context):
    if request.user != user and not request.user.has_perm('openode.view_other_user_log'):
        return render_forbidden(request)

    data = {
        'logs': user.logs.all().order_by('-action_time')[:50]
    }
    context.update(data)
    return render_into_skin('user_profile/user_logs.html', context, request)


@owner_or_moderator_required
def user_votes(request, user, context):
    all_votes = list(models.Vote.objects.filter(user=user))
    votes = []
    for vote in all_votes:
        post = vote.voted_post
        if post.is_question():
            vote.main_post = post
            vote.answer = None
            votes.append(vote)
        elif post.is_answer():
            vote.main_post = post.thread._main_post()
            vote.answer = post
            votes.append(vote)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('user vote record'),
        'page_title': _('profile - votes'),
        'votes': votes[:const.USER_VIEW_DATA_SIZE]
    }
    context.update(data)
    return render_into_skin('user_profile/user_votes.html', context, request)


def user_followed_questions(request, user, context):
    if not request.user.has_user_perm('can_see_followed_threads', user):
        return render_forbidden(request)

    user.user_followed_threads.values_list('thread', flat=True)
    questions = models.Post.objects.filter(
        post_type='question',
        thread__in=user.user_followed_threads.values_list('thread', flat=True)  # followed_threads
    ).select_related(
        'thread',
        'thread__last_activity_by'
    ).order_by(
        '-points',
        '-thread__last_activity_at'
    )[:const.USER_VIEW_DATA_SIZE]

    context.update({
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('users followed questions'),
        'page_title': _('profile - followed questions'),
        'questions': questions,
        'view_user': user
    })
    return render_into_skin('user_profile/user_followed_questions.html', context, request)


def user_followed_discussions(request, user, context):
    if not request.user.has_user_perm('can_see_followed_threads', user):
        return render_forbidden(request)
    followed_threads = user.user_followed_threads.values_list('thread', flat=True)
    discussions = models.Post.objects.filter(post_type='discussion', thread__in=followed_threads)\
                    .select_related('thread', 'thread__last_activity_by')\
                    .order_by('-points', '-thread__last_activity_at')[:const.USER_VIEW_DATA_SIZE]

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('users followed discussions'),
        'page_title': _('profile - followed discussions'),
        'discussions': discussions,
        'view_user': user
    }
    context.update(data)
    return render_into_skin('user_profile/user_followed_discussions.html', context, request)


def user_followed_nodes(request, user, context):
    if not request.user.has_user_perm('can_see_followed_nodes', user):
        return render_forbidden(request)
    followed_nodes = user.user_followed_nodes.all()

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('users followed nodes'),
        'page_title': _('profile - followed nodes'),
        'followed_nodes': followed_nodes,
        'view_user': user
    }
    context.update(data)
    return render_into_skin('user_profile/user_followed_nodes.html', context, request)


def user_managed_nodes(request, user, context):

    if not request.user.has_user_perm('can_see_followed_nodes', user):
        return render_forbidden(request)

    managed_nodes = user.nodes.filter(node_users__role=const.NODE_USER_ROLE_MANAGER)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('users managed nodes'),
        'page_title': _('profile - managed nodes'),
        'managed_nodes': managed_nodes,
    }
    context.update(data)
    return render_into_skin('user_profile/user_managed_nodes.html', context, request)


@owner_or_moderator_required
@csrf.csrf_protect
def user_email_subscriptions(request, user, context):

    logging.debug(get_request_info(request))
    if request.method == 'POST':
        action_status = None
        email_feeds_form = forms.EditUserEmailFeedsForm(request.POST)
        tag_filter_form = forms.TagFilterSelectionForm(request.POST, instance=user)
        if email_feeds_form.is_valid() and tag_filter_form.is_valid():

            tag_filter_saved = tag_filter_form.save()
            if tag_filter_saved:
                action_status = _('changes saved')
            if 'save' in request.POST:
                feeds_saved = email_feeds_form.save(user)
                if feeds_saved:
                    action_status = _('changes saved')
            elif 'stop_email' in request.POST:
                email_stopped = email_feeds_form.reset().save(user)
                initial_values = forms.EditUserEmailFeedsForm.NO_EMAIL_INITIAL
                email_feeds_form = forms.EditUserEmailFeedsForm(initial=initial_values)
                if email_stopped:
                    action_status = _('email updates canceled')
    else:
        #user may have been created by some app that does not know
        #about the email subscriptions, in that case the call below
        #will add any subscription settings that are missing
        #using the default frequencies
        user.add_missing_openode_subscriptions()

        #initialize the form
        email_feeds_form = forms.EditUserEmailFeedsForm()
        email_feeds_form.set_initial_values(user)
        tag_filter_form = forms.TagFilterSelectionForm(instance=user)
        action_status = None

    if action_status:
        request.user.message_set.create(message=action_status)

    data = {
        'active_tab': 'users',
        'page_class': 'user-profile-page',
        'tab_description': _('email subscription settings'),
        'page_title': _('profile - email subscriptions'),
        'email_feeds_form': email_feeds_form,
        'tag_filter_selection_form': tag_filter_form,
    }
    context.update(data)
    return render_into_skin(
        'user_profile/user_email_subscriptions.html',
        context,
        request
    )

################################################################################


def question_flow_new(request, profile_owner, context):
    if not request.user.has_perm('can_solve_question_flow', None):
        return render_forbidden(request)

    if request.method == "POST":
        # raw_node = request.GET.get(node)
        # if raw_node and str(raw_node).isdigit():

        question_pk = request.POST.get("question")
        if question_pk and question_pk.isdigit():
            question = get_object_or_404(Thread, pk=int(question_pk))

        form = QuestionFlowNodeResponsibleUsersForm(request.POST, question=question)

        if form.is_valid():
            question.question_flow_interviewee_user = form.cleaned_data[form.get_responsible_users_field_name()]
            question.question_flow_responsible_user = request.user
            question.question_flow_state = const.QUESTION_FLOW_STATE_SUBMITTED
            question.save()
            return HttpResponseRedirect(request.path)

    context.update({
        'view_user': request.user,
        "get_qf_form": lambda question: QuestionFlowNodeResponsibleUsersForm(question=question),
        "page_title": _("question flow new"),
    })
    return render_into_skin('user_profile/question_flow_new.html', context, request)


def question_flow_to_answer(request, profile_owner, context):
    if not request.user.has_perm('can_answer_in_question_flow', None):
        return render_forbidden(request)

    context.update({
        'view_user': request.user,
        "page_title": _("question flow new"),
    })
    return render_into_skin('user_profile/question_flow_to_answer.html', context, request)


def question_flow_to_publish(request, profile_owner, context):
    if not request.user.has_perm('can_solve_question_flow', None):
        return render_forbidden(request)

    context.update({
        'view_user': request.user,
        "page_title": _("question flow new"),
    })
    return render_into_skin('user_profile/question_flow_to_check.html', context, request)

################################################################################


USER_VIEW_CALL_TABLE = {
    '': user_overview,
    # 'activity': user_activity,
    # 'inbox': user_inbox,
    'followed_questions': user_followed_questions,
    'followed_discussions': user_followed_discussions,

    'followed_nodes': user_followed_nodes,
    'managed_nodes': user_managed_nodes,

    'node_joins': user_node_join_requests,
    'node_create': user_node_create_requests,
    'offensive_flags': user_offensive_flags_reports,
    'organization_joins': user_organization_join_requests,
    'organization_requests': organization_requests,
    'votes': user_votes,
    'email_subscriptions': user_email_subscriptions,
    'logs': user_logs,

    "question_flow_new": question_flow_new,
    "question_flow_to_answer": question_flow_to_answer,
    "question_flow_to_publish": question_flow_to_publish,
}


def user_profile(request, id, tab_name=None):
    """Main user view function that works as a switchboard

    id - id of the profile owner

    todo: decide what to do with slug - it is not used
    in the code in any way
    """

    profile_owner = get_object_or_404(models.User, id=id)
    user_view_func = USER_VIEW_CALL_TABLE.get(tab_name, user_overview)

    search_state = SearchState(  # Non-default SearchState with user data set
        scope=None, sort=None, tags=None, author=profile_owner.id, page=None,
        user_logged_in=profile_owner.is_authenticated(), node=None, module='qa'
    )

    context = {
        'view_user': profile_owner,
        'search_state': search_state,
        'user_follow_feature_on': ('followit' in django_settings.INSTALLED_APPS),
        'tab_name': tab_name,
    }
    # context.update(view_context.get_for_user_profile(request))
    return user_view_func(request, profile_owner, context)


@csrf.csrf_exempt
def update_has_custom_avatar(request):
    """updates current avatar type data for the user
    """
    if request.is_ajax() and request.user.is_authenticated():
        if request.user.avatar_type in ('n', 'g'):
            request.user.update_avatar_type()
            request.session['avatar_data_updated_at'] = datetime.datetime.now()
            return HttpResponse(simplejson.dumps({'status': 'ok'}), mimetype='application/json')
    return HttpResponseForbidden()


def organization_list(request, id=None, slug=None):
    """output organizations page
    """

    #6 lines of input cleaning code
    if request.user.is_authenticated():
        scope = request.GET.get('sort', 'all-organizations')
        if scope not in ('all-organizations', 'my-organizations'):
            scope = 'all-organizations'
    else:
        scope = 'all-organizations'

    if scope == 'all-organizations':
        organizations = models.Organization.objects.all()
    else:
        organizations = request.user.organizations.all()

    organizations = organizations.filter(approved=True)
    organizations = organizations.annotate(users_count=Count('users'))

    user_can_add_organizations = request.user.is_admin('openode.add_organization')

    organizations_membership_info = collections.defaultdict()
    if request.user.is_authenticated():
        #collect organization memberhship information
        organizations_membership_info = request.user.get_organizations_membership_info(organizations)

    data = {
        'organizations': organizations,
        'organizations_membership_info': organizations_membership_info,
        'user_can_add_organizations': user_can_add_organizations,
        'active_tab': 'organizations',  # todo vars active_tab and tab_name are too similar
        'tab_name': scope,
        'page_class': 'organizations-page'
    }
    return render_into_skin('organization_list.html', data, request)


def organization_membership(request, organization_id, organization_slug):
    user_acceptance_level = 'closed'
    user_membership_level = 'none'
    try:
        organization = models.Organization.objects.get(id=organization_id)
        user_acceptance_level = organization.get_openness_level_for_user(
            request.user
        )
    except models.Organization.DoesNotExist:
        raise Http404

    if request.user.is_authenticated():
        membership = request.user.get_organization_membership(organization)
        if membership:
            user_membership_level = membership.get_level_display()

    action = request.GET.get('request', '')

    if action == 'join' and user_membership_level == 'none':

        if user_acceptance_level == 'open':
            request.user.log(organization, const.LOG_ACTION_JOIN_GROUP)
            membership, created = models.OrganizationMembership.objects.get_or_create(user=request.user, organization=organization)
            membership.level = models.OrganizationMembership.FULL
            membership.save()
        elif user_acceptance_level == 'moderated':
            request.user.log(organization, const.LOG_ACTION_ASK_TO_JOIN_GROUP)
            membership, created = models.OrganizationMembership.objects.get_or_create(user=request.user, organization=organization)
            membership.level = models.OrganizationMembership.PENDING
            membership.save()
    elif action == 'leave' and user_membership_level == 'full':
        request.user.log(organization, const.LOG_ACTION_LEAVE_GROUP)
        membership.delete()
    elif action == 'cancel' and user_membership_level == 'pending':
        request.user.log(organization, const.LOG_ACTION_CANCEL_ASK_TO_JOIN_GROUP)
        membership.delete()

    return HttpResponseRedirect(reverse('organization_detail', kwargs={'organization_id': organization_id, 'organization_slug': organization_slug}))
