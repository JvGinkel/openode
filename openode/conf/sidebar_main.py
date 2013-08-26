"""
Sidebar settings
"""
from openode.conf.settings_wrapper import settings
from openode.deps.livesettings import ConfigurationGroup
from openode.deps.livesettings import values
from django.utils.translation import ugettext as _
from openode.conf.super_groups import CONTENT_AND_UI

SIDEBAR_MAIN = ConfigurationGroup(
                    'SIDEBAR_MAIN',
                    _('Main page sidebar'),
                    super_group=CONTENT_AND_UI
                )


settings.register(
    values.IntegerValue(
        SIDEBAR_MAIN,
        'SIDEBAR_MAIN_AVATAR_LIMIT',
        description=_('Limit how many avatars will be displayed on the sidebar'),
        default=16
    )
)
