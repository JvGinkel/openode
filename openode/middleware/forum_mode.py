"""
contains :class:`ForumModeMiddleware`, which is
enabling support of closed forum mode
"""
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.conf import settings
from django.core.urlresolvers import resolve
from openode.shims.django_shims import ResolverMatch
from openode.conf import settings as openode_settings

PROTECTED_VIEW_MODULES = (
    'openode.views',
    'django.contrib.syndication.views',
)
ALLOWED_VIEWS = (
    'openode.views.meta.media',
)

def is_view_protected(view_func):
    """True if view belongs to one of the
    protected view modules
    """
    for protected_module in PROTECTED_VIEW_MODULES:
        if view_func.__module__.startswith(protected_module):
            return True
    return False

def is_view_allowed(func):
    """True, if view is allowed to access
    by the special rule
    """
    view_path = func.__module__ + '.' + func.__name__
    return view_path in ALLOWED_VIEWS

class ForumModeMiddleware(object):
    """protects forum views is the closed forum mode"""

    def process_request(self, request):
        """when openode is in the closed mode
        it will let through only authenticated users.
        All others will be redirected to the login url.
        """
        if (openode_settings.OPENODE_CLOSED_FORUM_MODE
                and request.user.is_anonymous()):
            resolver_match = ResolverMatch(resolve(request.path))

            internal_ips = getattr(settings, 'OPENODE_INTERNAL_IPS', None)
            if internal_ips and request.META['REMOTE_ADDR'] in internal_ips:
                return None

            if is_view_allowed(resolver_match.func):
                return

            if is_view_protected(resolver_match.func):
                request.user.message_set.create(
                    _('Please log in to use %s') % \
                    openode_settings.APP_SHORT_NAME
                )
                return HttpResponseRedirect(settings.LOGIN_URL)
        return None
