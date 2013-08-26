from django.core.management.base import NoArgsCommand
from django.db.models import Count
from django.db import transaction
from openode.models import User
from openode import forms

class Command(NoArgsCommand):
    @transaction.commit_manually
    def handle_noargs(self, **options):
        for user in User.objects.all():
            user.add_missing_openode_subscriptions()
            transaction.commit()
