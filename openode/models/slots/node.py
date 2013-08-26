# -*- coding: utf-8 -*-

from openode import const

################################################################################
################################################################################


def post_save_node(sender, **kwargs):
    """
        actions after save Node
    """
    node = kwargs["instance"]

    # remove all followers which are not members of this Node
    if node.visibility in [const.NODE_VISIBILITY_PRIVATE]:
        node.node_following_users.exclude(user__pk__in=node.node_users.values_list("user__pk", flat=True)).delete()
        sender.objects.filter(pk=node.pk).update(followed_count=node.followed_count)

################################################################################


def post_save_node_user(sender, **kwargs):
    """
        actions after store NodeUser
    """
    node_user = kwargs["instance"]

    # update fulltext for Node
    node_user.node.save()

    # user must follow, if has manager role
    if (node_user.role == const.NODE_USER_ROLE_MANAGER) and not node_user.user.user_followed_nodes.filter(node=node_user.node).exists():
        node_user.user.user_followed_nodes.create(node=node_user.node)
        node_user.node.update_followed_count()

################################################################################


def post_delete_node_user(sender, **kwargs):
    """
        actions after delete NodeUser
    """

    # update fulltext for Node
    kwargs["instance"].node.save()
