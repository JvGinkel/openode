# -*- coding: utf-8 -*-

from django.core.management.base import NoArgsCommand
from openode.models.thread import Thread


class Command(NoArgsCommand):
    help = """Call method recount_unread_posts for all Threads"""

    def handle(self, *args, **options):
        i = 0
        for thread in Thread.objects.iterator():
            thread.recount_unread_posts()
            i += 1
        print "Recounted %s threads\n" % i
