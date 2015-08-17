# -*- coding: utf-8 -*-

"""Definitions of Celery tasks in Openode
in this module there are two types of functions:

* those wrapped with a @task decorator and a ``_celery_task`` suffix - celery tasks
* those with the same base name, but without the decorator and the name suffix
  the actual work units run by the task

Celery tasks are special functions in a way that they require all the parameters
be serializable - so instead of ORM objects we pass object id's and
instead of query sets - lists of ORM object id's.

That is the reason for having two types of methods here:

* the base methods (those without the decorator and the
  ``_celery_task`` in the end of the name
  are work units that are called from the celery tasks.
* celery tasks - shells that reconstitute the necessary ORM
  objects and call the base methods
"""
import sys
import traceback
# import logging
# import uuid

from django.contrib.contenttypes.models import ContentType
from django.template import Context
from django.utils.translation import ugettext as _
from celery.decorators import task
from openode.conf import settings as openode_settings
from openode import const
from openode import mail
from openode.models import User, ReplyAddress

# from openode.models import get_reply_to_addresses, format_instant_notification_email
# from openode import exceptions as openode_exceptions

# TODO: Make exceptions raised inside record_post_update_celery_task() ...
#       ... propagate upwards to test runner, if only CELERY_ALWAYS_EAGER = True
#       (i.e. if Celery tasks are not deferred but executed straight away)


# DEPRECATED
# @task(ignore_result=True)
# def record_post_update_celery_task(
#         post_id,
#         post_content_type_id,
#         newly_mentioned_user_id_list=None,
#         updated_by_id=None,
#         timestamp=None,
#         created=False,
#         diff=None,
#     ):
#     #reconstitute objects from the database
#     updated_by = User.objects.get(id=updated_by_id)
#     post_content_type = ContentType.objects.get(id=post_content_type_id)
#     post = post_content_type.get_object_for_this_type(id=post_id)
#     newly_mentioned_users = User.objects.filter(
#                                 id__in=newly_mentioned_user_id_list
#                             )
#     try:
#         notify_sets = post.get_notify_sets(
#                                 mentioned_users=newly_mentioned_users,
#                                 exclude_list=[updated_by]
#                             )
#         #todo: take into account created == True case
#         #update_object is not used
#         (activity_type, update_object) = post.get_updated_activity_data(created)

#         post.issue_update_notifications(
#             updated_by=updated_by,
#             notify_sets=notify_sets,
#             activity_type=activity_type,
#             timestamp=timestamp,
#             diff=diff
#         )

#     except Exception:
#         # HACK: exceptions from Celery job don't propagate upwards
#         # to the Django test runner
#         # so at least let's print tracebacks
#         print >>sys.stderr, traceback.format_exc()
#         raise


@task(ignore_result=True)
def record_thread_visit(thread=None, user=None, update_view_count=False):
    """
        celery task which records question visit by a person
        updates view counter, if necessary
    """

    #1) maybe update the view count
    #question_post = Post.objects.filter(
    #    id = question_post_id
    #).select_related('thread')[0]

    if update_view_count:
        thread.increase_view_count()

    # if user.is_anonymous():
    #     return

    # DEPRECATED
    # #2) question view count per user and clear response displays
    # #user = User.objects.get(id = user_id)
    # if user.is_authenticated():
    #     #get response notifications
    #     user.visit_thread(thread)
