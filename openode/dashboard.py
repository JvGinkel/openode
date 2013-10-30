"""
This file was generated with the customdashboard management command, it
contains the two classes for the main dashboard and app index dashboard.
You can customize these classes as you want.

To activate your index dashboard add the following to your settings.py::
    ADMIN_TOOLS_INDEX_DASHBOARD = 'openode-project.dashboard.CustomIndexDashboard'

And to activate the app index dashboard::
    ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'openode-project.dashboard.CustomAppIndexDashboard'
"""

from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from admin_tools.dashboard import modules, Dashboard, AppIndexDashboard
from admin_tools.utils import get_admin_site_name

from django.utils.text import capfirst


class CustomIndexDashboard(Dashboard):
    """
    Custom index dashboard for openode-project.
    """

    title = _('Openode low level administration')

    def init_with_context(self, context):
        site_name = get_admin_site_name(context)

        request = context['request']
        if request.user.is_superuser:
            self.children.append(modules.ModelList(
                capfirst(_('all')),
                models=('*'),
            ))
            return # do not proceed when superuser is logged

        # dash board settings for admin users

        self.children.append(modules.ModelList(
            capfirst(_('users')),
            models=('openode.models.ProxyUser', 'openode.models.ProxyUserManagerStatus', 'openode.models.user.Organization', 'django.contrib.auth.models.User', 'django.contrib.auth.models.Group'),
        ))

        self.children.append(modules.ModelList(
            capfirst(_('content')),
            models=('openode.models.cms.MenuItem', 'openode.models.actuality.Actuality', 'openode.models.cms.StaticPage'),
        ))

        self.children.append(modules.ModelList(
            capfirst(_('nodes')),
            models=(
                'openode.models.node.Node',
                'openode.models.node.FollowedNode',
                'openode.models.node.SubscribedNode',
                'openode.models.thread.FollowedThread',
                'openode.models.thread.SubscribedThread',
                'openode.models.tag.Tag',
            ),
        ))

        self.children.append(modules.RecentActions(_('Recent Actions'), 5))


class CustomAppIndexDashboard(AppIndexDashboard):
    """
    Custom app index dashboard for openode-project.
    """

    # we disable title because its redundant with the model list module
    title = ''

    def __init__(self, *args, **kwargs):
        AppIndexDashboard.__init__(self, *args, **kwargs)

    def init_with_context(self, context):
        """
        Use this method if you need to access the request context.
        """
        return super(CustomAppIndexDashboard, self).init_with_context(context)
