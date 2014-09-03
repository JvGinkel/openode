# -*- coding: utf-8 -*-
## Django settings for OPENODE enabled project.
import os.path
# import logging
import site

import imp
OPENODE_SOURCE_PATH = imp.find_module('openode')[1]
OPENODE_ROOT = os.path.abspath(OPENODE_SOURCE_PATH)

#import openode
#OPENODE_ROOT = os.path.abspath(os.path.dirname(openode.__file__))

# this line is added so that we can import pre-packaged openode dependencies
site.addsitedir(os.path.join(OPENODE_ROOT, 'deps'))

# prefer openode translations to the django translations
LOCALE_PATHS = (
    os.path.join(os.path.dirname(__file__), 'locale/'),
    os.path.join(OPENODE_ROOT, 'locale/'),
)


DEBUG = True  # set to True to enable debugging
TEMPLATE_DEBUG = False  # keep false when debugging jinja2 templates
DEBUG_SEND_EMAIL_NOTIFICATIONS = True
INTERNAL_IPS = ('127.0.0.1',)

ADMINS = (
    ('Your Name', 'your_email@domain.com'),
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

MANAGERS = ADMINS

# DATABASE SETTINGS
DATABASE_ENGINE = 'postgresql_psycopg2'  # only postgres (>8.3) and mysql are supported so far others have not been tested yet
DATABASE_NAME = ''             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Your domain name
DOMAIN_NAME = ''

# EMAIL SETTINGS
SERVER_EMAIL = 'your_email@domain.com'
DEFAULT_FROM_EMAIL = 'your_email@domain.com'
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_SUBJECT_PREFIX = "[OPENode] "
EMAIL_HOST = 'localhost'
EMAIL_PORT = ''
EMAIL_USE_TLS = False
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

#incoming mail settings
#after filling out these settings - please
#go to the site's live settings and enable the feature
#"Email settings" -> "allow asking by email"
#
#   WARNING: command post_emailed_questions DELETES all
#            emails from the mailbox each time
#            do not use your personal mail box here!!!
#
IMAP_HOST = ''
IMAP_HOST_USER = ''
IMAP_HOST_PASSWORD = ''
IMAP_PORT = ''
IMAP_USE_TLS = False

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Prague'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = 'cs'

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'upfiles')
MEDIA_URL = '/upfiles/'  # url to uploaded media

DOCUMENT_ROOT = os.path.join(MEDIA_ROOT, 'documents/')
DOCUMENT_URL = '%sdocuments/' % MEDIA_URL

WYSIWYG_NODE_ROOT = os.path.join(MEDIA_ROOT, 'wysiwyg_node/')
WYSIWYG_NODE_URL = '%swysiwyg_node/' % MEDIA_URL

WYSIWYG_THREAD_ROOT = os.path.join(MEDIA_ROOT, 'wysiwyg_thread/')
WYSIWYG_THREAD_URL = '%swysiwyg_thread/' % MEDIA_URL

ORGANIZATION_LOGO_ROOT = os.path.join(MEDIA_ROOT, 'organization_logos/')
ORGANIZATION_LOGO_URL = '%sorganization_logos/' % MEDIA_URL

STATIC_URL = '/m/'  # url to project static files
STATIC_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, 'static'))  # path to files collected by collectstatic

STATICFILES_DIRS = (
    ('default/media', os.path.join(OPENODE_ROOT, 'media')),
)

FORCE_STATIC_SERVE_WITH_DJANGO = False

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'  # must be this value

# Make up some unique string, and don't share it with anybody.
SECRET_KEY = '3#&ds&r_!m2bz+f&$37nlfb4t81t@^&ql6au4rolas(of0dq&s'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    #below is openode stuff for this tuple
    #'openode.skins.loaders.load_template_source', #changed due to bug 97
    # 'openode.skins.loaders.filesystem_load_template_source',
    #'django.template.loaders.eggs.load_template_source',
)


MIDDLEWARE_CLASSES = (
    #'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'openode.middleware.locale.LocaleMiddleware',
    #'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.cache.FetchFromCacheMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    #'django.middleware.sqlprint.SqlPrintingMiddleware',

    #below is openode stuff for this tuple
    'openode.middleware.anon_user.ConnectToSessionMessagesMiddleware',
    'openode.middleware.forum_mode.ForumModeMiddleware',
    'openode.middleware.cancel.CancelActionMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'openode.middleware.view_log.ViewLogMiddleware',
    'openode.middleware.spaceless.SpacelessMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
)

SPACELESS_HTML = False

ROOT_URLCONF = os.path.basename(os.path.dirname(__file__)) + '.urls'


#UPLOAD SETTINGS
FILE_UPLOAD_TEMP_DIR = "/tmp"
# FILE_UPLOAD_TEMP_DIR = os.path.join(
#                                 os.path.dirname(__file__),
#                                 'tmp'
#                             ).replace('\\', '/')

FILE_UPLOAD_HANDLERS = (
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
)

OPENODE_ALLOWED_UPLOAD_IMG_TYPES = ('.jpg', '.jpeg', '.gif', '.bmp', '.png', '.tiff')
OPENODE_ALLOWED_UPLOAD_DOCS_TYPES = (".doc", ".odt", ".rtf", ".pdf", ".xls", ".docx", ".xlsx", ".ppt", ".pptx", ".txt",)
OPENODE_ALLOWED_UPLOAD_FILE_TYPES = OPENODE_ALLOWED_UPLOAD_IMG_TYPES + OPENODE_ALLOWED_UPLOAD_DOCS_TYPES

OPENODE_MAX_UPLOAD_FILE_SIZE = 1024 * 1024  # result in bytes
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


#TEMPLATE_DIRS = (,) #template have no effect in openode, use the variable below
#OPENODE_EXTRA_SKINS_DIR = #path to your private skin collection
#take a look here http://openode.org/en/question/207/

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'openode.context.application_settings',
    #'django.core.context_processors.i18n',
    'openode.user_messages.context_processors.user_messages',  # must be before auth
    'django.core.context_processors.auth',  # this is required for admin
    'django.core.context_processors.csrf',  # necessary for csrf protection
    'openode.context_processors.menu_items',  # CMS menu items upper and lower
    'openode.context_processors.node_modules',  # constants for node module names
    'openode.context_processors.login_form',
    'openode.context_processors.user_profile',
)


INSTALLED_APPS = (
    #'longerusername',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    # 'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # admin tools
    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',

    'haystack',


    #all of these are needed for the openode
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    #'debug_toolbar',
    #'haystack',
    'openode',
    'openode.deps.django_authopenid',
    #'openode.importers.stackexchange', #se loader
    'openode.deps.livesettings',
    'keyedcache',
    # 'robots',
    'django_countries',
    'djcelery',
    # 'djkombu',
    # 'followit', # following user is not available in Openode anymore
    'mptt',
    'django_select2',
    'gunicorn',

    'sorl.thumbnail',

    # "django-celery",

    #'avatar',#experimental use git clone git://github.com/ericflo/django-avatar.git$
    'openode.document',
    'rosetta',
)

try:
    from settings_local import EXTRA_INSTALLED_APPS
    INSTALLED_APPS += EXTRA_INSTALLED_APPS
except ImportError:
    pass

LANGUAGES = (
    ('cs', 'Czech'),
    ('en', 'English'),
    # ('de', 'Deutsch'),
)

#setup memcached for production use!
#see http://docs.djangoproject.com/en/1.1/topics/cache/ for details
CACHE_BACKEND = 'locmem://'
#needed for django-keyedcache
CACHE_TIMEOUT = 6000
#sets a special timeout for livesettings if you want to make them different
LIVESETTINGS_CACHE_TIMEOUT = CACHE_TIMEOUT
CACHE_PREFIX = 'openode'  # make this unique
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True
#If you use memcache you may want to uncomment the following line to enable memcached based sessions
#SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'openode.deps.django_authopenid.backends.AuthBackend',
)

MAX_USERNAME_LENGTH = 255

################################################################################

MPTT_ADMIN_LEVEL_INDENT = 25

RUN_STARTUP_TEST = True

################################################################################
# WYSIWGS settings
################################################################################

WYSIWYG_SETTING_FULL = """
    [
        ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo'],
        ['Blockquote', '-', 'Table', '-', 'SpecialChar'],
        ['Image', '-', 'Link', 'Unlink'],
        ['Source', '-', 'Maximize'],
        "/",
        ['Bold', 'Italic', 'Underline', 'Strike', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
        ['JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
        ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent'],
        ['Format', 'FontSize', '-', 'TextColor','BGColor']
    ]
"""

WYSIWYG_SETTING_SIMPLE = """
    [
        ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo'],
        ['Blockquote', '-', 'Table', '-', 'SpecialChar'],
        ['Link', 'Unlink'],
        ['Source', '-', 'Maximize'],
        "/",
        ['Bold', 'Italic', 'Underline', 'Strike', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
        ['JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
        ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent'],
        ['FontSize', '-', 'TextColor','BGColor']
    ]
"""

WYSIWYG_SETTING_COMMENT = """
    [
        ['Bold', 'Italic', 'Underline', 'Strike'],
        ['Blockquote', '-', 'Link', 'Unlink', '-', 'SpecialChar']
    ]
"""

HTML_CLEANER_ATTRS = {
    '*': [
        'style',
    ],
    "a": [
        "href",
        "target",
    ],
    "img": [
        "alt",
        "src",
        "style",
        "height",
        "width",
    ],
    'span': [
        'style',
    ],
    "table": [
        "border",
        "cellpadding",
        "cellspacing",
        "style",
    ]
}

HTML_CLEANER_TAGS = [
    'a',
    "br",
    'blockquote',
    'em',
    'img',
    'li',
    'ol',
    'p',
    'span',
    'strike',
    'strong',
    'sub',
    'sup',
    'table',
    'tbody',
    'td',
    'tfoot',
    'th',
    'thead',
    'tr',
    'u',
    'ul'
]

HTML_CLEANER_STYLES = [
    'border',
    'color',
    'background-color',
    'float',
    'font-size',
    'height',
    'width',
    'text-align',
]
################################################################################
# LOGGING SETTINGS
################################################################################

try:
    from settings_local import LOG_DIR
except ImportError:
    LOG_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "log"))
finally:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

MAIN_LOG = os.path.join(LOG_DIR, 'system.log')
CELERY_LOG_FILE = os.path.join(LOG_DIR, 'celery.log')


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '%(levelname)s:[%(asctime)s] <%(name)s|%(filename)s:%(lineno)s> %(message)s'
        },
    },

    'handlers': {
        'file_debug': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': MAIN_LOG,
            'formatter': 'verbose',
        },
    },

    'loggers': {
        "": {
            'handlers': ['file_debug'],
            'level': 'INFO',
        },
    },
}

################################################################################
# document api - Mayan Pyro API
################################################################################

# keep this information in secret!
# replace in settings local
DOCUMENT_HMAC_KEY = ""  # uuid
DOCUMENT_URI_ID = ""  # uuid
DOCUMENT_SERVER_IP = "127.0.0.1"
DOCUMENT_URI_PORT = 33333

################################################################################

HAYSTACK_CONNECTIONS = {
    'default': {
        # 'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'ENGINE': 'openode.search.backends.ConfigurableElasticSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'openode',
        "TIMEOUT": 100,  # 10

        # "SILENTLY_FAIL": False

        # 'INCLUDE_SPELLING': True,

        # 'ENGINE': 'haystack.backends.solr_backend.SolrEngine',
        # 'URL': 'http://127.0.0.1:8983/solr'
        # ...or for multicore...
        # 'URL': 'http://127.0.0.1:8983/solr/mysite',
    },
}

HAYSTACK_SIGNAL_PROCESSOR = 'openode.models.signal_processors.QueueSignalProcessor'

################################################################################
# SORL THUMBNAIL settings
################################################################################

THUMBNAIL_FORMAT = "PNG"

################################################################################

#
#   this will allow running your forum with url like http://site.com/forum
#
#   OPENODE_URL = 'forum/'
#
OPENODE_URL = ''  # no leading slash, default = '' empty string
OPENODE_TRANSLATE_URL = True  # translate specific URLs
# _ = lambda v: v  # fake translation function for the login url
# LOGIN_URL = '/%s%s%s' % (OPENODE_URL, _('account/'), _('signin/'))
LOGIN_URL = '/%s%s%s' % (OPENODE_URL, 'account/', 'signin/')
LOGIN_REDIRECT_URL = OPENODE_URL  # adjust if needed
#note - it is important that upload dir url is NOT translated!!!
#also, this url must not have the leading slash
ALLOW_UNICODE_SLUGS = False

################################################################################
# Celery Settings
################################################################################

# BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"
BROKER_URL = 'redis://localhost:6379/0'

# set to False on production server with running celery in extra process
# if True, all tasks will be called in django process
# if False tasks is processed in celery process
CELERY_ALWAYS_EAGER = True

import djcelery
djcelery.setup_loader()

################################################################################


CSRF_COOKIE_NAME = 'cc_csrf'
#enter domain name here - e.g. example.com
#CSRF_COOKIE_DOMAIN = ''

RECAPTCHA_USE_SSL = True

#HAYSTACK_SETTINGS
# ENABLE_HAYSTACK_SEARCH = False
# HAYSTACK_SITECONF = 'openode.search.haystack'
# #more information
# #http://django-haystack.readthedocs.org/en/v1.2.7/settings.html
# HAYSTACK_SEARCH_ENGINE = 'simple'

#delayed notifications, time in seconds, 15 mins by default
NOTIFICATION_DELAY_TIME = 60 * 15

JINJA2_EXTENSIONS = (
    'openode.templatetags.mptt_tags.RecurseTreeExtension',
)

HUMANIZE_DATETIME_LIMIT = 86400


ADMIN_TOOLS_INDEX_DASHBOARD = 'openode.dashboard.CustomIndexDashboard'
ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'openode.dashboard.CustomAppIndexDashboard'
ADMIN_TOOLS_MENU = 'openode.menu.CustomMenu'

try:
    from settings_local import *
except ImportError:
    pass
