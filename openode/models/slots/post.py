# -*- coding: utf-8 -*-


def recount_unread_posts(sender, **kwargs):
    """
        call when new Post was created
    """
    post = kwargs["instance"]
    if post.thread:
        post.thread.recount_unread_posts()
