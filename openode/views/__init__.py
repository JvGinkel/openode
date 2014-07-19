"""
:synopsis: django view functions for the openode project
"""

from openode.views import node
from openode.views import tag
from openode.views import thread
from openode.views import readers
from openode.views import http
from openode.views import writers
from openode.views import commands
from openode.views import users
from openode.views import meta
from openode.views import download
from openode.views import upload
from openode.views import live

from django.conf import settings

if 'avatar' in settings.INSTALLED_APPS:
    from openode.views import avatar_views
