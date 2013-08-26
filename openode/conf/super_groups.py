from django.utils.translation import ugettext as _
from openode.deps.livesettings import SuperGroup
from openode.deps.livesettings import config_register_super_group

VOTES_AND_FLAGS = SuperGroup(_('Votes & Flags'))
CONTENT_AND_UI = SuperGroup(_('Static Content, URLS & UI'))
DATA_AND_FORMATTING = SuperGroup(_('Data rules & Formatting'))
EXTERNAL_SERVICES = SuperGroup(_('External Services'))
LOGIN_USERS_COMMUNICATION = SuperGroup(_('Login, Users & Communication'))
config_register_super_group(VOTES_AND_FLAGS)
config_register_super_group(LOGIN_USERS_COMMUNICATION)
config_register_super_group(DATA_AND_FORMATTING)
config_register_super_group(EXTERNAL_SERVICES)
config_register_super_group(CONTENT_AND_UI)
