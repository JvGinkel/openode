# -*- coding: utf-8 -*-

################################################################################
# IMPORTANT:
#   when you add/remove/change some permission, DON'T forget for translation
#   string on and of the this script
################################################################################

from openode.const import (
    NODE_USER_ROLE_DOCUMENT_MANAGER,
    NODE_USER_ROLE_MANAGER,
    NODE_USER_ROLE_MEMBER,
    NODE_USER_ROLE_READONLY,
    )

RULES = {
    'node_visibility_public': {
        'node_show': True,
        'node_read': True,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': True,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': True,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': True,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
    'node_visibility_registered_users': {
        'node_show': False,
        'node_read': False,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': False,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': False,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': False,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
    'user_loggedin': {
        'node_show': True,
        'node_read': True,

        'question_read': True,
        'node_qa_create': True,
        'question_update_mine': True,
        'question_delete_mine': True,
        'question_answer_vote': True,
        'question_answer_create': True,
        'question_answer_update_mine': True,
        'question_answer_comment_create': True,

        'discussion_read': True,
        'node_forum_create': True,
        'discussion_update_mine': True,
        'discussion_delete_mine': True,
        # 'discussion_post_update_mine': False,
        'discussion_post_delete_mine': True,
        'discussion_post_create': True,

        'document_read': True,
    },
    'node_visibility_private': {
        'node_show': False,
        'node_read': False,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': False,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': False,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': False,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
    'node_visibility_semiprivate': {
        # 'node_show': True, # this was bug - anonymous users should not see semiprivate nodes
        'node_read': False,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': False,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': False,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': False,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
    'thread_external_access': {
        'document_read': True,
    },

    #members

    'thread_is_closed': {

        'node_qa_create': False,
        'question_update_mine': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,

        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,

        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },

    'node_qa_is_readonly': {
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
    },

    'node_forum_is_readonly': {
        'node_forum_create': False,
        'discussion_post_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
    },

    'node_library_is_readonly': {
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },

    'node_is_closed': {
        'node_edit_annotation': False,

        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,

        'node_forum_create': False,
        'discussion_post_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,

        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },

    'node_is_deleted': {
        'node_show': False,
        'node_read': False,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': False,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': False,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': False,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
}

MEMBERS_RULES = {
    NODE_USER_ROLE_MEMBER: {
        'node_show': True,
        'node_read': True,

        'question_read': True,
        'node_qa_create': True,
        'question_update_mine': True,
        'question_answer_vote': True,
        'question_answer_create': True,
        'question_answer_update_mine': True,
        'question_answer_comment_create': True,

        'discussion_read': True,
        'node_forum_create': True,
        'discussion_update_mine': True,
        'discussion_delete_mine': True,
        # 'discussion_post_update_mine': False,
        'discussion_post_delete_mine': True,
        'discussion_post_create': True,

        'document_read': True,
    },
    NODE_USER_ROLE_DOCUMENT_MANAGER: {
        'node_show': True,
        'node_read': True,

        'question_read': True,
        'node_qa_create': True,
        'question_update_mine': True,

        'question_answer_vote': True,
        'question_answer_create': True,
        'question_answer_update_mine': True,
        'node_forum_create': True,
        'discussion_update_mine': True,
        'discussion_delete_mine': True,
        # 'discussion_post_update_mine': False,
        'discussion_post_delete_mine': True,
        'question_answer_comment_create': True,

        'discussion_read': True,
        'discussion_post_create': True,

        'document_read': True,
        'node_library_create': True,
        'document_update': True,
        'document_delete': True,
        'document_directory_create': True,
        'document_directory_update': True,
        'document_directory_delete': True,
    },
    NODE_USER_ROLE_READONLY: {

        'node_show': True,
        'node_read': True,
        'node_edit_annotation': False,
        'node_settings': False,
        'question_read': True,
        'node_qa_create': False,
        'question_update_mine': False,
        'question_close': False,
        'question_answer_accept': False,
        'question_answer_vote': False,
        'question_answer_create': False,
        'question_answer_update_mine': False,
        'discussion_post_update_mine': False,
        'discussion_post_delete_mine': False,
        'question_answer_comment_create': False,
        'question_update_any': False,
        'question_update_mine': False,
        'question_delete_any': False,
        'question_delete_mine': False,
        'question_answer_update_any': False,
        'question_answer_delete_any': False,
        'question_answer_comment_update_any': False,
        'question_answer_comment_delete_any': False,
        'discussion_read': True,
        'discussion_post_create': False,
        'node_forum_create': False,
        'discussion_update_any': False,
        'discussion_update_mine': False,
        'discussion_close': False,
        'discussion_delete_any': False,
        'discussion_delete_mine': False,
        'discussion_post_update_any': False,
        'discussion_post_delete_any': False,
        'document_read': True,
        'node_library_create': False,
        'document_update': False,
        'document_delete': False,
        'document_directory_create': False,
        'document_directory_update': False,
        'document_directory_delete': False,
    },
    NODE_USER_ROLE_MANAGER: {
        'node_show': True,
        'node_read': True,
        'node_edit_annotation': True,
        'node_settings': True,
        'question_read': True,
        'node_qa_create': True,
        'question_update_mine': True,
        'question_close': True,
        'question_answer_accept': True,
        'question_answer_vote': True,
        'question_answer_create': True,
        'question_answer_update_mine': True,
        # 'discussion_post_update_mine': False,
        'discussion_post_delete_mine': True,
        'question_answer_comment_create': True,
        'question_update_any': True,
        'question_update_mine': True,
        'question_delete_any': True,
        'question_delete_mine': True,
        'question_answer_update_any': True,
        'question_answer_delete_any': True,
        'question_answer_comment_update_any': True,
        'question_answer_comment_delete_any': True,
        'discussion_read': True,
        'node_forum_create': True,
        'discussion_update_mine': True,
        'discussion_delete_mine': True,
        'discussion_close': True,
        'discussion_update_any': True,

        'discussion_post_create': True,
        'discussion_delete_any': True,

        # 'discussion_post_update_any': True,
        'discussion_post_delete_any': True,
        'document_read': True,
        'node_library_create': True,
        'document_update': True,
        'document_delete': True,
        'document_directory_create': True,
        'document_directory_update': True,
        'document_directory_delete': True,
    }
}

################################################################################

from django.utils.translation import ugettext as _

_('perm-discussion_close')
_('perm-discussion_delete_any')
_('perm-discussion_delete_mine')
_('perm-discussion_post_create')
_('perm-discussion_post_delete_any')
_('perm-discussion_post_delete_mine')
_('perm-discussion_post_update_any')
_('perm-discussion_post_update_mine')
_('perm-discussion_read')
_('perm-discussion_update_any')
_('perm-discussion_update_mine')
_('perm-document_delete')
_('perm-document_directory_create')
_('perm-document_directory_delete')
_('perm-document_directory_update')
_('perm-document_read')
_('perm-document_update')
_('perm-node_edit_annotation')
_('perm-node_forum_create')
_('perm-node_library_create')
_('perm-node_qa_create')
_('perm-node_read')
_('perm-node_settings')
_('perm-node_show')
_('perm-question_answer_accept')
_('perm-question_answer_comment_create')
_('perm-question_answer_comment_delete_any')
_('perm-question_answer_comment_update_any')
_('perm-question_answer_create')
_('perm-question_answer_delete_any')
_('perm-question_answer_update_any')
_('perm-question_answer_update_mine')
_('perm-question_answer_vote')
_('perm-question_close')
_('perm-question_delete_any')
_('perm-question_delete_mine')
_('perm-question_read')
_('perm-question_update_any')
_('perm-question_update_mine')

_("perm-node_visibility_public")
_("perm-node_visibility_registered_users")
_("perm-user_loggedin")
_("perm-node_visibility_private")
_("perm-node_visibility_semiprivate")
_("perm-thread_external_access")
_("perm-member")
_("perm-document-manager")
_("perm-readonly")
_("perm-manager")
_("perm-thread_is_closed")
_("perm-node_qa_is_readonly")
_("perm-node_forum_is_readonly")
_("perm-node_library_is_readonly")
_("perm-node_is_closed")
_("perm-node_is_deleted")
