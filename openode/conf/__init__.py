#import these to compile code and install values
import openode
import openode.conf.vote_rules
import openode.conf.email
import openode.conf.forum_data_rules
import openode.conf.flatpages
import openode.conf.site_settings
#import openode.conf.license # DEPRECATED - use custom templates /templates/custom_templates/footer/footer_content_[lang].html
import openode.conf.external_keys
import openode.conf.skin_general_settings
import openode.conf.sidebar_main
import openode.conf.sidebar_question
import openode.conf.sidebar_profile
import openode.conf.leading_sidebar
import openode.conf.spam_and_moderation
import openode.conf.user_settings
import openode.conf.social_sharing
import openode.conf.login_providers
import openode.conf.access_control
# import openode.conf.site_modes # DEPRECATED

#import main settings object
from openode.conf.settings_wrapper import settings
# from django.conf import settings as django_settings


def get_tag_display_filter_strategy_choices():
    from openode import const
    from openode.conf import settings as openode_settings
    if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
        return const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES
    else:
        return const.TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES
