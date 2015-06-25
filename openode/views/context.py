"""functions, preparing parts of context for
the templates in the various views"""

# from django.contrib.contenttypes.models import ContentType
from django.utils import simplejson
from django.utils.translation import ugettext as _
from openode.conf import settings as openode_settings
from openode import const  # , models
from openode.const import message_keys as msg
# from openode.models import OrganizationMembership


def get_for_tag_editor():
    #data for the tag editor
    data = {
        'tag_regex': const.TAG_REGEX,
        'max_tags_per_post': openode_settings.MAX_TAGS_PER_POST,
        'max_tag_length': openode_settings.MAX_TAG_LENGTH,
        'force_lowercase_tags': openode_settings.FORCE_LOWERCASE_TAGS,
        'messages': {
            'wrong_chars': _(msg.TAG_WRONG_CHARS_MESSAGE)
        }
    }
    return {'tag_editor_settings': simplejson.dumps(data)}


# def get_for_user_profile(request):
#     """adds response counts of various types"""

#     user = request.user
#     if user.is_anonymous():
#         return {}

#     # get flags count
#     flags_count = 0
#     if openode_settings.ENABLE_MARK_OFFENSIVE_FLAGS:
#         flag_activity_types = (const.TYPE_ACTIVITY_MARK_OFFENSIVE,)
#         flags_count = user.get_notifications(flag_activity_types).count()

#     # get organization_pending_memberships_count
#     # TODO this condition does not corespond with other resolve_organization_joining conditions in templates
#     organization_pending_memberships_count = 0
#     organization_pending_memberships = None
#     if user.has_perm('openode.resolve_organization_joining'):
#         organization_pending_memberships = OrganizationMembership.objects.filter(
#                 # organization__in=user.get_organizations(),
#                 level=OrganizationMembership.PENDING
#             )
#         organization_pending_memberships_count = organization_pending_memberships.count()

#     # search nodes that I'm manager in

#     node_content_type = ContentType.objects.get_for_model(models.Node)
#     node_ids = set(models.NodeUser.objects.filter(user=user, role=const.NODE_USER_ROLE_MANAGER).values_list('node_id', flat=True))
#     node_join_requests = None
#     user_has_perm_resolve_node_joining = False
#     # do not show requests for other Nodes
#     # if user.has_perm('openode.resolve_node_joining'):
#     #     node_join_requests = models.Activity.objects.filter(
#     #                     activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE,
#     #                     content_type=node_content_type
#     #     ).order_by('-active_at')
#     #     user_has_perm_resolve_node_joining = True
#     # elif any(node_ids):
#     if any(node_ids):
#         node_join_requests = models.Activity.objects.filter(
#                 activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE,
#                 content_type=node_content_type,
#                 object_id__in=node_ids
#             ).order_by(
#                 '-active_at'
#             )
#         user_has_perm_resolve_node_joining = True

#     node_join_requests_count = 0
#     if user_has_perm_resolve_node_joining:
#         node_join_requests_count = node_join_requests.count()

#     node_create_requests = models.Activity.objects.filter(
#             activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_NODE,
#         ).order_by(
#             '-active_at'
#         )

#     organization_requests = models.Activity.objects.filter(
#             activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_ORG,
#         ).order_by(
#             '-active_at'
#         )

#     user_has_perm_resolve_node_creating = user.is_staff and user.has_perm('openode.add_node')
#     node_create_requests_count = node_create_requests.count()
#     organization_requests_count = organization_requests.count()

#     return {
#         're_count': user.new_response_count + user.seen_response_count,
#         'flags_count': flags_count,
#         'organization_pending_memberships_count': organization_pending_memberships_count,
#         'organization_pending_memberships': organization_pending_memberships,
#         'user_has_perm_resolve_node_joining': user_has_perm_resolve_node_joining,
#         'node_join_requests_count': node_join_requests_count,
#         'node_join_requests': node_join_requests,
#         'user_has_perm_resolve_node_creating': user_has_perm_resolve_node_creating,
#         'node_create_requests_count': node_create_requests_count,
#         'node_create_requests': node_create_requests,
#         'organization_requests': organization_requests,
#         'organization_requests_count': organization_requests_count,
#     }
