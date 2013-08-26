# -*- coding: utf-8 -*-

import logging

from celery.task import task
from Pyro4.errors import CommunicationError

from models import DocumentRevision, Page

from django.conf import settings


@task
def process_document_revision(uuid, document_pk=None):
    logger = process_document_revision.get_logger(logfile=settings.CELERY_LOG_FILE, loglevel=logging.INFO)

    try:
        dr = DocumentRevision.objects.get(uuid=uuid)
    except DocumentRevision.DoesNotExist:
        logger.error("DocumentRevision.DoesNotExist uuid=%s" % uuid)
        return

    try:
        dr.api_process_document(logger=logger)
    except CommunicationError, e:
        logger.info("Retry task: process_document_revision. DocumentRevision uuid=%s" % uuid)
        process_document_revision.retry(exc=e)


@task
def process_page(pk):
    logger = process_page.get_logger(logfile=settings.CELERY_LOG_FILE, loglevel=logging.INFO)

    try:
        page = Page.objects.get(pk=pk)
    except Page.DoesNotExist:
        logger.error("Page.DoesNotExist pk=%s" % pk)
        return

    page.api_get_plaintext(update=True, logger=logger)
