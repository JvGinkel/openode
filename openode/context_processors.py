# -*- coding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType

from openode.deps.django_authopenid.forms import LoginForm
from openode.forms import clean_login_url

from openode.models.cms import MenuItem, MENU_UPPER, MENU_FOOTER
from openode.const import NODE_MODULE_ANNOTATION, NODE_MODULE_QA, NODE_MODULE_FORUM, NODE_MODULE_LIBRARY
# from openode.views.context import get_for_user_profile
from openode.conf import settings as openode_settings
from openode import const, models
from openode.models import Node, OrganizationMembership, Thread


def menu_items(request):
    """
    add menu items to context
    """
    return {
        "menu_items_upper": MenuItem.objects.filter(menu=MENU_UPPER, language=request.LANGUAGE_CODE),
        "menu_items_footer": MenuItem.objects.filter(menu=MENU_FOOTER, language=request.LANGUAGE_CODE)
    }


def node_modules(request):
    """
    add node module names constants to context
    """
    return {
        "NODE_MODULE_ANNOTATION": NODE_MODULE_ANNOTATION,
        "NODE_MODULE_QA": NODE_MODULE_QA,
        "NODE_MODULE_FORUM": NODE_MODULE_FORUM,
        "NODE_MODULE_LIBRARY": NODE_MODULE_LIBRARY
    }


def login_form(request):
    """
    login form
    """
    if not request.user.is_authenticated():

        next = clean_login_url(request.get_full_path())

        header_login_form = LoginForm(initial={
            'login_provider_name': 'local',
            'password_action': 'login',
            'next': next
        })
        return {
            "header_login_form": header_login_form
        }
    else:
        return {}


def user_profile(request):
    # return get_for_user_profile(request)
    """adds response counts of various types"""

    context = {}
    user = request.user

    if user.is_anonymous():
        return context

    # get flags count
    flags_count = 0
    if openode_settings.ENABLE_MARK_OFFENSIVE_FLAGS:
        flag_activity_types = (const.TYPE_ACTIVITY_MARK_OFFENSIVE,)
        flags_count = user.get_notifications(flag_activity_types).count()

    # get organization_pending_memberships_count
    # TODO this condition does not corespond with other resolve_organization_joining conditions in templates
    organization_pending_memberships_count = 0
    organization_pending_memberships = None
    if user.has_perm('openode.resolve_organization_joining'):
        organization_pending_memberships = OrganizationMembership.objects.filter(
                # organization__in=user.get_organizations(),
                level=OrganizationMembership.PENDING
            )
        organization_pending_memberships_count = organization_pending_memberships.count()

    # search nodes that I'm manager in

    node_content_type = ContentType.objects.get_for_model(models.Node)
    node_ids = set(models.NodeUser.objects.filter(user=user, role=const.NODE_USER_ROLE_MANAGER).values_list('node_id', flat=True))
    node_join_requests = None
    user_has_perm_resolve_node_joining = False
    # do not show requests for other Nodes
    # if user.has_perm('openode.resolve_node_joining'):
    #     node_join_requests = models.Activity.objects.filter(
    #                     activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE,
    #                     content_type=node_content_type
    #     ).order_by('-active_at')
    #     user_has_perm_resolve_node_joining = True
    # elif any(node_ids):
    if any(node_ids):
        node_join_requests = models.Activity.objects.filter(
                activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE,
                content_type=node_content_type,
                object_id__in=node_ids
            ).order_by(
                '-active_at'
            )
        user_has_perm_resolve_node_joining = True

    node_create_requests = models.Activity.objects.filter(
            activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_NODE,
        ).order_by(
            '-active_at'
        )

    organization_requests = models.Activity.objects.filter(
            activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_ORG,
        ).order_by(
            '-active_at'
        )

    node_join_requests_count = node_join_requests.count() if user_has_perm_resolve_node_joining else 0

    context.update({
        "user_has_perm_resolve_node_creating": user.is_staff and user.has_perm('openode.add_node'),
        "organization_requests_count": organization_requests.count(),
        "node_create_requests_count": node_create_requests.count(),
        'organization_requests': organization_requests,
        'node_create_requests': node_create_requests,
        'node_join_requests': node_join_requests,
        're_count': user.new_response_count + user.seen_response_count,
        'flags_count': flags_count,
        'organization_pending_memberships_count': organization_pending_memberships_count,
        'organization_pending_memberships': organization_pending_memberships,
        'user_has_perm_resolve_node_joining': user_has_perm_resolve_node_joining,
        'node_join_requests_count': node_join_requests_count,
    })

    # question flow - notification part

    user_responsible_nodes = Node.objects.filter(
        is_question_flow_enabled=True,
        node_users__user=user,
        node_users__is_responsible=True
    )
    questions = Thread.objects.get_questions().filter(
        node__in=user_responsible_nodes
        )

    context.update({
        "question_flow_to_taken": questions.filter(
            question_flow_state=const.QUESTION_FLOW_STATE_NEW
            ),

        "question_flow_to_submit_or_answer": questions.filter(
            question_flow_state=const.QUESTION_FLOW_STATE_TAKEN,
            question_flow_responsible_user=request.user,
            ),

        "question_flow_to_answer": questions.filter(
            question_flow_state=const.QUESTION_FLOW_STATE_SUBMITTED,
            question_flow_interviewee_user=request.user,
            ),

        "question_flow_to_check_answer_and_publish": questions.filter(
            question_flow_state=const.QUESTION_FLOW_STATE_ANSWERED,
            question_flow_responsible_user=request.user,
            ),
    })

    # question_flow_new_count =

    return context
