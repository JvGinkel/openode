"""
Q&A website settings - title, desctiption, basic urls
keywords
"""
from openode.conf.settings_wrapper import settings
from openode.conf.super_groups import CONTENT_AND_UI
from openode.deps import livesettings
from django.utils.translation import ugettext as _

QA_SITE_SETTINGS = livesettings.ConfigurationGroup(
                    'QA_SITE_SETTINGS',
                    _('URLS, keywords & greetings'),
                    super_group = CONTENT_AND_UI
                )

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_TITLE',
        default=u'OPENODE',
        description=_('Site title for the Q&A instance')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_SUBTITLE',
        default=u'smarter knowledge',
        description=_('Site sub-title for the instance')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_KEYWORDS',
        default=u'Openode,Askbot,CNPROG,forum,community',
        description=_('Comma separated list of instance keywords')
    )
)

# settings.register(
#     livesettings.StringValue(
#         QA_SITE_SETTINGS,
#         'APP_COPYRIGHT',
#         default='Copyleft COEX 2013.',
#         description=_('Copyright message to show in the footer')
#     )
# )

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_DESCRIPTION',
        default='Openode,Askbot,CNPROG,forum,community',
        description=_('Site description for the search engines')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_SHORT_NAME',
        default='Openode',
        description=_('Short name for your installation')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_URL',
        description=_(
                'Base URL for your installation, must start with '
                'http or https'
            ),
    )
)

settings.register(
    livesettings.BooleanValue(
        QA_SITE_SETTINGS,
        'ENABLE_GREETING_FOR_ANON_USER',
        default = True,
        description = _('Check to enable greeting for anonymous user')
   )
)

# TODO DEPRECATED
# settings.register(
#     livesettings.StringValue(
#         QA_SITE_SETTINGS,
#         'GREETING_FOR_ANONYMOUS_USER',
#         default='First time here? Check out the FAQ!',
#         hidden=False,
#         description=_(
#                 'Text shown in the greeting message '
#                 'shown to the anonymous user'
#             ),
#         help_text=_(
#                 'Use HTML to format the message '
#             )
#     )
# )

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'FEEDBACK_SITE_URL',
        description=_('Feedback site URL'),
        help_text=_(
                'If left empty, a simple internal feedback form '
                'will be used instead'
            )
    )
)
