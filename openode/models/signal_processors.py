# -*- coding: utf-8 -*-

"""
    Set of class and tasks for realtime update Haystack (ElasticSearch) fulltext
"""

import logging

from celery.task import task

from django.contrib.auth.models import User
from django.db.models import get_model
from django.db.models import signals

from haystack import connections as haystack_connections
from haystack.exceptions import NotHandled
from haystack.signals import BaseSignalProcessor

from openode import const
from openode.document.models import Document, Page
from openode.models.post import Post
from openode.models.node import Node
from openode.models.thread import Thread
from openode.models.user import Organization

from django.conf import settings

###############################################################################
# HELPERS
###############################################################################


def get_fulltext_instance(app_label, model_name, instance_pk, post_type, logger):
    """
        helpers for finding best django (proxy) model
        @return instance, sender
    """
    from openode.search_indexes import (
        AnswerProxy,
        DiscussionPostProxy,
        QuestionProxy
    )

    instance = None
    sender = get_model(app_label, model_name)

    # translate special models for proxymodel
    if issubclass(sender, Thread):
        sender = QuestionProxy
    elif issubclass(sender, Post):
        if post_type == const.POST_TYPE_THREAD_POST:
            sender = AnswerProxy
        elif post_type == const.POST_TYPE_DISCUSSION:
            sender = DiscussionPostProxy
        else:
            sender = None

    if not sender:
        return None, None

    try:
        instance = sender.objects.get(pk=instance_pk)

        # if thread is not question, return None
        if isinstance(instance, Thread) and not instance.is_question():
            return None, None

    except sender.DoesNotExist:
        logger.error("Fulltext | object not found: %s" % repr({
            "sender": str(sender),
            "app_label": app_label,
            "model_name": model_name,
            "pk": instance_pk
        }))

    return instance, sender

###############################################################################
# tasks
###############################################################################


@task
def task_update_fulltext(using, app_label, model_name, instance_pk, post_type):
    """
        update fulltext index
    """
    logger = task_update_fulltext.get_logger(logfile=settings.CELERY_LOG_FILE, loglevel=logging.INFO)

    instance, sender = get_fulltext_instance(app_label, model_name, instance_pk, post_type, logger)
    if not(instance and sender):
        return

    try:
        index = haystack_connections[using].get_unified_index().get_index(sender)

        if hasattr(instance, "is_deleted") and instance.is_deleted:
            # SOFT DELETE
            index.remove_object(instance, using=using)
            logger.info("Fulltext | remove (soft) success: %s" % repr({
                "type": type(instance),
                "pk": instance_pk
            }))
        else:
            # UPDATE
            index.update_object(instance, using=using)
            logger.info("Fulltext | update success: %s" % repr({
                "type": type(instance),
                "pk": instance_pk
            }))

    except NotHandled, e:
        logger.error("Fulltext | update error: %s" % repr({
            "type": type(instance),
            "pk": instance_pk,
            "error": str(e),
        }))


@task
def task_remove_from_fulltext(using, app_label, model_name, instance_pk, post_type):

    logger = task_remove_from_fulltext.get_logger(logfile=settings.CELERY_LOG_FILE, loglevel=logging.INFO)

    instance, sender = get_fulltext_instance(app_label, model_name, instance_pk, post_type, logger)
    if not(instance and sender):
        return

    try:
        index = haystack_connections[using].get_unified_index().get_index(sender)
        index.remove_object(instance, using=using)

        logger.info("Fulltext | remove success: %s" % repr({
            "sender": sender,
            "instance_pk": instance.pk
        }))
    except NotHandled, e:
        logger.error("Fulltext | remove error: %s" % repr({
            "sender": sender,
            "instance_pk": instance.pk,
            "error": e,
            "error_type": type(e),
        }))

################################################################################
# Signal processor
###############################################################################


class QueueSignalProcessor(BaseSignalProcessor):
    """
        Class for providing relatime (as task in Celery) indexing objects for Haystack.
        In settings you must add this class like
            HAYSTACK_SIGNAL_PROCESSOR = 'openode.models.FulltextSignalProcessor'
        end Haystack connect this signals for update index.
    """

    RELATED_MODELS = [
        Node,
        Organization,
        Post,
        Thread,
        User,
        Document,
        Page
    ]

    ###################################

    def get_related_models(self):
        return self.RELATED_MODELS

    ###################################

    def translate_models(self, sender, instance):

        post_type = None
        if isinstance(instance, Post):

            try:
                thread = instance.thread
            except Thread.DoesNotExist:
                return None, None, None

            if not thread:
                return sender, instance, None

            if thread.is_discussion():
                # >> DiscussionPostProxy
                post_type = const.POST_TYPE_DISCUSSION

            elif thread.is_question():

                if instance.is_comment():
                    # question or answer
                    instance = instance.parent

                if instance.is_answer():
                    # >> AnswerProxy
                    post_type = const.POST_TYPE_THREAD_POST
                else:
                    # every else >> QuestionProxy
                    instance = thread
                    sender = Thread

        return sender, instance, post_type

    ###################################

    def handle_save(self, sender, instance, **kwargs):
        """
            create celery tasks for store fulltext after save related models
        """
        sender, instance, post_type = self.translate_models(sender, instance)

        if not(sender and instance):
            return

        for using in self.connection_router.for_write(instance=instance):
            task_update_fulltext.apply_async(
                args=[
                    using,
                    sender._meta.app_label,
                    sender._meta.module_name,
                    instance.pk,
                    post_type
                ],
                countdown=5,
            )

            # if is saved Node, all QUESTIONS will be reindexed
            if isinstance(instance, Node):
                for thread in instance.threads.filter(thread_type=const.THREAD_TYPE_QUESTION).iterator():
                    task_update_fulltext.apply_async(
                        args=[
                            using,
                            Thread._meta.app_label,
                            Thread._meta.module_name,
                            thread.pk,
                            None
                        ],
                        countdown=5
                    )

    ###################################

    def handle_delete(self, sender, instance, **kwargs):
        """
            create celery tasks for remove from fulltext after delete related models
        """
        sender, instance, post_type = self.translate_models(sender, instance)

        if not(sender and instance):
            return

        # TODO: remove post before remove thread

        for using in self.connection_router.for_write(instance=instance):
            task_remove_from_fulltext.apply_async(
                args=[
                    using,
                    sender._meta.app_label,
                    sender._meta.module_name,
                    instance.pk,
                    None
                ],
                countdown=5
            )

    ###################################
    ###################################

    def setup(self):
        for Model in self.get_related_models():
            signals.post_save.connect(self.handle_save, sender=Model)
            # TODO: change to pre_save
            signals.post_delete.connect(self.handle_delete, sender=Model)

    def teardown(self):
        for Model in self.get_related_models():
            signals.post_save.disconnect(self.handle_save, sender=Model)
            # TODO: change to pre_save
            signals.post_delete.disconnect(self.handle_delete, sender=Model)
