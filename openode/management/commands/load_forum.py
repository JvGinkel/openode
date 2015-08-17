from django.core import management
from django.db.models import signals
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from openode import models

class Command(BaseCommand):
    args = '<data file>'
    help = 'Loads openode forum data from the dump file obtained with command "dump_forum"'
    def handle(self, *args, **options):
        #need to remove badge data b/c they are aslo in the dump
        models.BadgeData.objects.all().delete()
        ContentType.objects.all().delete()
        #turn off the post_save signal so than Activity can be copied
        signals.post_save.receivers = []
        management.call_command('loaddata', args[0])
