"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'openode-project.menu.CustomMenu'
"""

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from admin_tools.menu import items, Menu
from django.utils.text import capfirst


class CustomMenu(Menu):
    """
    Custom Menu for openode-project admin site.
    """

    def init_with_context(self, context):
        """
        Use this method if you need to access the request context.
        """

        request = context['request']

        self.children.append(
            items.MenuItem(_('Dashboard'), reverse('admin:index'))
        )

        self.children.append(items.ModelList(
            capfirst(_('users')),
            models=('openode.models.ProxyUser', 'openode.models.ProxyUserManagerStatus', 'openode.models.user.Organization', 'django.contrib.auth.models.User', 'django.contrib.auth.models.Group'),
        ))

        # append an app list module for "Administration"
        self.children.append(items.ModelList(
            capfirst(_('content')),
            models=('openode.models.cms.MenuItem', 'openode.models.actuality.Actuality', 'openode.models.cms.StaticPage'),
        ))

        self.children.append(items.ModelList(
            capfirst(_('nodes')),
            models=(
                'openode.models.node.Node',
                'openode.models.thread.Thread',
                'openode.models.node.FollowedNode',
                'openode.models.node.SubscribedNode',
                'openode.models.thread.FollowedThread',
                'openode.models.thread.SubscribedThread',
                'openode.models.tag.Tag',
            ),
        ))

        if request.user.has_perm('livesettings.change_setting'):
            self.children.append(items.MenuItem(_('Settings'), reverse('site_settings')))

        if request.user.is_superuser or request.user.groups.filter(name="translators").exists():
            self.children.append(items.MenuItem('Rosetta', reverse('rosetta-home')))

        self.children.append(
            items.MenuItem(_('Frontend'), reverse('index'))
        )

        self.children.append(
            items.MenuItem(_('Document processing'), reverse('admin:document_state'))
        )

        self.children.append(
            items.MenuItem(_('Perms'), reverse('show_perm_table'))
        )

        return super(CustomMenu, self).init_with_context(context)
