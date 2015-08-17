# -*- coding: utf-8 -*-

from django.db.models.signals import post_save

from openode.document.models import DocumentRevision, Page

import tasks

################################################################################


def start_process_document(sender, **kwargs):
    if kwargs["created"]:
        document_revision = kwargs["instance"]
        tasks.process_document_revision.apply_async(
            args=[document_revision.uuid],
            kwargs={"document_pk": document_revision.document_id},
            countdown=5  # wait 5 seconds for finishing all save transactions...
            )

#######################################


def start_process_page(sender, **kwargs):
    if kwargs["created"]:
        page = kwargs["instance"]
        FIX = 20  # TODO
        siblings_count = page.document_revision._pages_count or page.document_revision.pages.count()
        countdown = FIX + siblings_count
        tasks.process_page.apply_async(
            args=[page.pk],
            countdown=countdown
        )

################################################################################

post_save.connect(start_process_document, sender=DocumentRevision)
post_save.connect(start_process_page, sender=Page)
