# -*- coding: utf-8 -*-

from django.core.management.base import NoArgsCommand
from openode.document.helpers import get_invalid_documents_qs
from nagios import send_warning, send_ok


class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        stuck_documents_count = get_invalid_documents_qs().count()
        if stuck_documents_count > 0:
            send_warning('Stuck documents: %d' % stuck_documents_count)
        else:
            send_ok('Stuck documents: %d' % stuck_documents_count)
