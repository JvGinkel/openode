"""
Settings for openode data display and entry
"""
from openode.conf.settings_wrapper import settings
from openode.deps import livesettings
from openode import const
from openode.conf.super_groups import DATA_AND_FORMATTING
from django.utils.translation import ugettext as _

FORUM_DATA_RULES = livesettings.ConfigurationGroup(
                        'FORUM_DATA_RULES',
                        _('Data entry and display rules'),
                        super_group=DATA_AND_FORMATTING
                    )

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_TAG_LENGTH',
        default=20,
        description=_('Maximum length of tag (number of characters)')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_TITLE_LENGTH',
        default=3,
        description=_('Minimum length of title (number of characters)')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_QUESTION_BODY_LENGTH',
        default=10,
        description=_(
            'Minimum length of question body (number of characters)'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_ANSWER_BODY_LENGTH',
        default=10,
        description=_(
            'Minimum length of answer body (number of characters)'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'LIMIT_ONE_ANSWER_PER_USER',
        default=True,
        description=_(
            'Limit one answer per question per user'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'ENABLE_TAG_MODERATION',
        default=False,
        description=_('Enable tag moderation'),
        help_text=_(
            'If enabled, any new tags will not be applied '
            'to the questions, but emailed to the moderators. '
            'To use this feature, tags must be optional.'
        )
    )
)


settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'FORCE_LOWERCASE_TAGS',
        default=False,
        description=_('Force lowercase the tags'),
        help_text=_(
            'Attention: after checking this, please back up the database, '
            'and run a management command: '
            '<code>python manage.py fix_question_tags</code> to globally '
            'rename the tags'
         )
    )
)

settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'TAG_LIST_FORMAT',
        default='list',
        choices=const.TAG_LIST_FORMAT_CHOICES,
        description=_('Format of tag list'),
        help_text=_(
                        'Select the format to show tags in, '
                        'either as a simple list, or as a '
                        'tag cloud'
                     )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'USE_WILDCARD_TAGS',
        default=False,
        description=_('Use wildcard tags'),
        help_text=_(
                        'Wildcard tags can be used to follow or ignore '
                        'many tags at once, a valid wildcard tag has a single '
                        'wildcard at the very end'
                    )
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'SUBSCRIBED_TAG_SELECTOR_ENABLED',
        default=False,
        description=_('Use separate set for subscribed tags'),
        help_text=_(
            'If enabled, users will have a third set of tag selections '
            '- "subscribed" (by email) in additon to "interesting" '
            'and "ignored"'
        )
    )
)

MARKED_TAG_DISPLAY_CHOICES = (
    ('always', _('Always, for all users')),
    ('never', _('Never, for all users')),
    ('when-user-wants', _('Let users decide'))
)
settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'MARKED_TAGS_ARE_PUBLIC_WHEN',
        default='always',
        choices=MARKED_TAG_DISPLAY_CHOICES,
        description=_('Publicly show user tag selections')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_COMMENTS_TO_SHOW',
        default=5,
        description=_(
            'Default max number of comments to display under posts'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_COMMENT_LENGTH',
        default=300,
        description=_(
                'Maximum comment length, must be < %(max_len)s'
            ) % {'max_len': const.COMMENT_HARD_MAX_LENGTH}
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'USE_TIME_LIMIT_TO_EDIT_COMMENT',
        default=True,
        description=_('Limit time to edit comments'),
        help_text=_(
                        'If unchecked, there will be no time '
                        'limit to edit the comments'
                    )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MINUTES_TO_EDIT_COMMENT',
        default=10,
        description=_('Minutes allowed to edit a comment'),
        help_text=_('To enable this setting, check the previous one')
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'SAVE_COMMENT_ON_ENTER',
        default=True,
        description=_('Save comment by pressing <Enter> key')
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MIN_SEARCH_WORD_LENGTH',
        default=4,
        description=_('Minimum length of search term for Ajax search'),
        help_text=_('Must match the corresponding database backend setting'),
    )
)

settings.register(
    livesettings.BooleanValue(
        FORUM_DATA_RULES,
        'DECOUPLE_TEXT_QUERY_FROM_SEARCH_STATE',
        default=False,
        description=_('Do not make text query sticky in search'),
        help_text=_(
            'Check to disable the "sticky" behavior of the search query. '
            'This may be useful if you want to move the search bar away '
            'from the default position or do not like the default '
            'sticky behavior of the text search query.'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        FORUM_DATA_RULES,
        'MAX_TAGS_PER_POST',
        default=5,
        description=_('Maximum number of tags per question')
    )
)

#todo: looks like there is a bug in openode.deps.livesettings
#that does not allow Integer values with defaults and choices
settings.register(
    livesettings.StringValue(
        FORUM_DATA_RULES,
        'DEFAULT_QUESTIONS_PAGE_SIZE',
        choices=const.PAGE_SIZE_CHOICES,
        default='30',
        description=_('Number of questions to list by default')
    )
)
