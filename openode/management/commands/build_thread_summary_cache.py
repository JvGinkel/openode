from django.core.management.base import NoArgsCommand
from openode.models import Thread
from openode.utils.console import ProgressBar

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        message = "Rebuilding thread summary cache"
        count = Thread.objects.count()
        for thread in ProgressBar(Thread.objects.iterator(), count, message):
            thread.update_summary_html()
