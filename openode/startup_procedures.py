"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of openode

question: why not run these from openode/__init__.py?

the main function is run_startup_tests
"""
import sys
import os
import re
import urllib
import openode
from django.db import transaction  # , connection
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from openode.utils.loading import load_module
from openode.utils.functions import enumerate_string_list
from openode.utils.url_utils import urls_equal
from urlparse import urlparse

RUN_STARTUP_TESTS_HEADER = """\n*** Openode start up self-test START ***"""

RUN_STARTUP_TESTS_FOOTER = """*** Openode start up self-test OK ***\n"""

FOOTER = """\n
If necessary, quit the server with CONTROL-C.
"""


class OpenodeConfigError(ImproperlyConfigured):
    """Prints an error with possibly a footer"""
    def __init__(self, error_message):
        msg = error_message
        if sys.__stdin__.isatty():
            #print footer only when openode is run from the shell
            msg += FOOTER
            super(OpenodeConfigError, self).__init__(msg)


def openode_warning(line):
    """prints a warning with the nice header, but does not quit"""
    print >> sys.stderr, line + FOOTER


def print_errors(error_messages, header=None, footer=None):
    """if there is one or more error messages,
    raise ``class:OpenodeConfigError`` with the human readable
    contents of the message
    * ``header`` - text to show above messages
    * ``footer`` - text to show below messages
    """
    if len(error_messages) == 0:
        return
    if len(error_messages) > 1:
        error_messages = enumerate_string_list(error_messages)

    message = ''
    if header:
        message += header + '\n'
    message += 'Please attend to the following:\n\n'
    message += '\n\n'.join(error_messages)
    if footer:
        message += '\n\n' + footer
    raise OpenodeConfigError(message)


def format_as_text_tuple_entries(items):
    """prints out as entries or tuple containing strings
    ready for copy-pasting into say django settings file"""
    return "    '%s'," % "',\n    '".join(items)


#todo:
#
# *validate emails in settings.py
def test_openode_url():
    """Tests the OPENODE_URL setting for the
    well-formedness and raises the :class:`OpenodeConfigError`
    exception, if the setting is not good.
    """
    url = django_settings.OPENODE_URL
    if url != '':

        if isinstance(url, str) or isinstance(url, unicode):
            pass
        else:
            msg = 'setting OPENODE_URL must be of string or unicode type'
            raise OpenodeConfigError(msg)

        if url == '/':
            msg = 'value "/" for OPENODE_URL is invalid. ' + \
                'Please, either make OPENODE_URL an empty string ' + \
                'or a non-empty path, ending with "/" but not ' + \
                'starting with "/", for example: "forum/"'
            raise OpenodeConfigError(msg)
        else:
            try:
                assert(url.endswith('/'))
            except AssertionError:
                msg = 'if OPENODE_URL setting is not empty, ' + \
                        'it must end with /'
                raise OpenodeConfigError(msg)
            try:
                assert(not url.startswith('/'))
            except AssertionError:
                msg = 'if OPENODE_URL setting is not empty, ' + \
                        'it must not start with /'


def test_middleware():
    """Checks that all required middleware classes are
    installed in the django settings.py file. If that is not the
    case - raises an OpenodeConfigError exception.
    """
    required_middleware = [
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'openode.middleware.anon_user.ConnectToSessionMessagesMiddleware',
        'openode.middleware.forum_mode.ForumModeMiddleware',
        'openode.middleware.cancel.CancelActionMiddleware',
        'django.middleware.transaction.TransactionMiddleware',
    ]
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        required_middleware.append(
            'debug_toolbar.middleware.DebugToolbarMiddleware',
        )
    required_middleware.extend([
        'openode.middleware.view_log.ViewLogMiddleware',
        'openode.middleware.spaceless.SpacelessMiddleware',
    ])
    found_middleware = [x for x in django_settings.MIDDLEWARE_CLASSES
                            if x in required_middleware]
    if found_middleware != required_middleware:
        # either middleware is out of order or it's missing an item
        missing_middleware_set = set(required_middleware) - set(found_middleware)
        middleware_text = ''
        if missing_middleware_set:
            error_message = """\n\nPlease add the following middleware (listed after this message)
to the MIDDLEWARE_CLASSES variable in your site settings.py file.
The order the middleware records is important, please take a look at the example in
https://github.com/OPENODE/openode-devel/blob/master/openode/setup_templates/settings.py:\n\n"""
            middleware_text = format_as_text_tuple_entries(missing_middleware_set)
        else:
            # middleware is out of order
            error_message = """\n\nPlease check the order of middleware closely.
The order the middleware records is important, please take a look at the example in
https://github.com/OPENODE/openode-devel/blob/master/openode/setup_templates/settings.py
for the correct order.\n\n"""
        raise OpenodeConfigError(error_message + middleware_text)

    #middleware that was used in the past an now removed
    canceled_middleware = [
        'openode.deps.recaptcha_django.middleware.ReCaptchaMiddleware'
    ]

    invalid_middleware = [x for x in canceled_middleware
                            if x in django_settings.MIDDLEWARE_CLASSES]
    if invalid_middleware:
        error_message = """\n\nPlease remove the following middleware entries from
the list of MIDDLEWARE_CLASSES in your settings.py - these are not used any more:\n\n"""
        middleware_text = format_as_text_tuple_entries(invalid_middleware)
        raise OpenodeConfigError(error_message + middleware_text)


def try_import(module_name, pypi_package_name, short_message=False):
    """tries importing a module and advises to install
    A corresponding Python package in the case import fails"""
    try:
        load_module(module_name)
    except ImportError, error:
        message = 'Error: ' + unicode(error)
        message += '\n\nPlease run: >pip install %s' % pypi_package_name
        if short_message == False:
            message += '\n\nTo install all the dependencies at once, type:'
            message += '\npip install -r openode_requirements.txt'
        message += '\n\nType ^C to quit.'
        raise OpenodeConfigError(message)


def test_modules():
    """tests presence of required modules"""
    from openode import REQUIREMENTS
    for module_name, pip_path in REQUIREMENTS.items():
        try_import(module_name, pip_path)


def test_postgres():
    """Checks for the postgres buggy driver, version 2.4.2"""
    if 'postgresql_psycopg2' in openode.get_database_engine_name():
        import psycopg2
        version = psycopg2.__version__.split(' ')[0].split('.')
        if version == ['2', '4', '2']:
            raise OpenodeConfigError(
                'Please install psycopg2 version 2.4.1,\n version 2.4.2 has a bug'
            )
        elif version > ['2', '4', '2']:
            pass  # don't know what to do
        else:
            pass  # everythin is ok


def test_encoding():
    """prints warning if encoding error is not UTF-8"""
    if hasattr(sys.stdout, 'encoding'):
        if sys.stdout.encoding != 'UTF-8':
            openode_warning(
                'Your output encoding is not UTF-8, there may be '
                'issues with the software when anything is printed '
                'to the terminal or log files'
            )


def test_template_loader():
    """Sends a warning if you have an old style template
    loader that used to send a warning"""
    old_template_loader = 'openode.skins.loaders.load_template_source'
    if old_template_loader in django_settings.TEMPLATE_LOADERS:
        raise OpenodeConfigError(
                "\nPlease change: \n"
                "'openode.skins.loaders.load_template_source', to\n"
                "'openode.skins.loaders.filesystem_load_template_source',\n"
                "in the TEMPLATE_LOADERS of your settings.py file"
        )


# def test_celery():
#     """Tests celery settings
#     todo: we are testing two things here
#     that correct name is used for the setting
#     and that a valid value is chosen
#     """
#     broker_backend = getattr(django_settings, 'BROKER_BACKEND', None)
#     broker_transport = getattr(django_settings, 'BROKER_TRANSPORT', None)
#     delay_time = getattr(django_settings, 'NOTIFICATION_DELAY_TIME', None)
#     delay_setting_info = 'The delay is in seconds - used to throttle ' + \
#                     'instant notifications note that this delay will work only if ' + \
#                     'celery daemon is running Please search about ' + \
#                     '"celery daemon setup" for details'

#     if delay_time is None:
#         raise OpenodeConfigError(
#             '\nPlease add to your settings.py\n' + \
#             'NOTIFICATION_DELAY_TIME = 60*15\n' + \
#             delay_setting_info
#         )
#     else:
#         if not isinstance(delay_time, int):
#             raise OpenodeConfigError(
#                 '\nNOTIFICATION_DELAY_TIME setting must have a numeric value\n' + \
#                 delay_setting_info
#             )

#     if broker_backend is None:
#         if broker_transport is None:
#             raise OpenodeConfigError(
#                 "\nPlease add\n"
#                 'BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"\n'
#                 "or other valid value to your settings.py file"
#             )
#         else:
#             #todo: check that broker transport setting is valid
#             return

#     if broker_backend != broker_transport:
#         raise OpenodeConfigError(
#             "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
#             "in your settings.py file\n"
#             "If you have both in your settings.py - then\n"
#             "delete the BROKER_BACKEND setting and leave the BROKER_TRANSPORT"
#         )

#     if hasattr(django_settings, 'BROKER_BACKEND') and not hasattr(django_settings, 'BROKER_TRANSPORT'):
#         raise OpenodeConfigError(
#             "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
#             "in your settings.py file"
#         )


def test_media_url():
    """makes sure that setting `MEDIA_URL`
    has leading slash"""
    media_url = django_settings.MEDIA_URL
    #todo: add proper url validation to MEDIA_URL setting
    if not (media_url.startswith('/') or media_url.startswith('http')):
        raise OpenodeConfigError(
            "\nMEDIA_URL parameter must be a unique url on the site\n"
            "and must start with a slash - e.g. /media/ or http(s)://"
        )


class SettingsTester(object):
    """class to test contents of the settings.py file"""

    def __init__(self, requirements=None):
        """loads the settings module and inits some variables
        parameter `requirements` is a dictionary with keys
        as setting names and values - another dictionary, which
        has keys (optional, if noted and required otherwise)::

        * required_value (optional)
        * error_message
        """
        self.settings = load_module(os.environ['DJANGO_SETTINGS_MODULE'])
        self.messages = list()
        self.requirements = requirements

    def test_setting(self, name,
            value=None, message=None,
            test_for_absence=False,
            replace_hint=None
        ):
        """if setting does is not present or if the value != required_value,
        adds an error message
        """
        if test_for_absence:
            if hasattr(self.settings, name):
                if replace_hint:
                    value = getattr(self.settings, name)
                    message += replace_hint % value
                self.messages.append(message)
        else:
            if not hasattr(self.settings, name):
                self.messages.append(message)
            elif value and getattr(self.settings, name) != value:
                self.messages.append(message)

    def run(self):
        for setting_name in self.requirements:
            self.test_setting(
                setting_name,
                **self.requirements[setting_name]
            )
        if len(self.messages) != 0:
            raise OpenodeConfigError(
                '\n\nTime to do some maintenance of your settings.py:\n\n* ' +
                '\n\n* '.join(self.messages)
            )


def test_new_skins():
    """tests that there are no directories in the `openode/skins`
    because we've moved skin files a few levels up"""
    openode_root = openode.get_install_directory()
    for item in os.listdir(os.path.join(openode_root, 'skins')):
        item_path = os.path.join(openode_root, 'skins', item)
        if os.path.isdir(item_path):
            raise OpenodeConfigError(
                ('Time to move skin files from %s.\n'
                'Now we have `openode/templates` and `openode/media`') % item_path
            )


def test_staticfiles():
    """tests configuration of the staticfiles app"""
    errors = list()
    import django
    django_version = django.VERSION
    if django_version[0] == 1 and django_version[1] < 3:
        staticfiles_app_name = 'staticfiles'
        wrong_staticfiles_app_name = 'django.contrib.staticfiles'
        try_import('staticfiles', 'django-staticfiles')
        import staticfiles
        if staticfiles.__version__[0] != 1:
            raise OpenodeConfigError(
                'Please use the newest available version of '
                'django-staticfiles app, type\n'
                'pip install --upgrade django-staticfiles'
            )
        if not hasattr(django_settings, 'STATICFILES_STORAGE'):
            raise OpenodeConfigError(
                'Configure STATICFILES_STORAGE setting as desired, '
                'a reasonable default is\n'
                "STATICFILES_STORAGE = 'staticfiles.storage.StaticFilesStorage'"
            )
    else:
        staticfiles_app_name = 'django.contrib.staticfiles'
        wrong_staticfiles_app_name = 'staticfiles'

    if staticfiles_app_name not in django_settings.INSTALLED_APPS:
        errors.append(
            'Add to the INSTALLED_APPS section of your settings.py:\n'
            "    '%s'," % staticfiles_app_name
        )
    if wrong_staticfiles_app_name in django_settings.INSTALLED_APPS:
        errors.append(
            'Remove from the INSTALLED_APPS section of your settings.py:\n'
            "    '%s'," % wrong_staticfiles_app_name
        )
    static_url = django_settings.STATIC_URL or ''
    if static_url is None or str(static_url).strip() == '':
        errors.append(
            'Add STATIC_URL setting to your settings.py file. '
            'The setting must be a url at which static files '
            'are accessible.'
        )
    url = urlparse(static_url).path
    if not (url.startswith('/') and url.endswith('/')):
        #a simple check for the url
        errors.append(
            'Path in the STATIC_URL must start and end with the /.'
        )
    if django_settings.ADMIN_MEDIA_PREFIX != static_url + 'admin/':
        errors.append(
            'Set ADMIN_MEDIA_PREFIX as: \n'
            "    ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'"
        )

    # django_settings.STATICFILES_DIRS can have strings or tuples
    staticfiles_dirs = [d[1] if isinstance(d, tuple) else d
                        for d in django_settings.STATICFILES_DIRS]

    default_skin_tuple = None
    openode_root = openode.get_install_directory()
    old_default_skin_dir = os.path.abspath(os.path.join(openode_root, 'skins'))
    for dir_entry in django_settings.STATICFILES_DIRS:
        if isinstance(dir_entry, tuple):
            if dir_entry[0] == 'default/media':
                default_skin_tuple = dir_entry
        elif isinstance(dir_entry, str):
            if os.path.abspath(dir_entry) == old_default_skin_dir:
                errors.append(
                    'Remove from STATICFILES_DIRS in your settings.py file:\n' + dir_entry
                )

    openode_root = os.path.dirname(openode.__file__)
    default_skin_media_dir = os.path.abspath(os.path.join(openode_root, 'media'))
    if default_skin_tuple:
        media_dir = default_skin_tuple[1]
        if default_skin_media_dir != os.path.abspath(media_dir):
            errors.append(
                'Add to STATICFILES_DIRS the following entry: '
                "('default/media', os.path.join(OPENODE_ROOT, 'media')),"
            )

    extra_skins_dir = getattr(django_settings, 'OPENODE_EXTRA_SKINS_DIR', None)
    if extra_skins_dir is not None:
        if not os.path.isdir(extra_skins_dir):
            errors.append(
                'Directory specified with settning OPENODE_EXTRA_SKINS_DIR '
                'must exist and contain your custom skins for openode.'
            )
        if extra_skins_dir not in staticfiles_dirs:
            errors.append(
                'Add OPENODE_EXTRA_SKINS_DIR to STATICFILES_DIRS entry in '
                'your settings.py file.\n'
                'NOTE: it might be necessary to move the line with '
                'OPENODE_EXTRA_SKINS_DIR just above STATICFILES_DIRS.'
            )

    if django_settings.STATICFILES_STORAGE == \
        'django.contrib.staticfiles.storage.StaticFilesStorage':
        if os.path.dirname(django_settings.STATIC_ROOT) == '':
            #static root is needed only for local storoge of
            #the static files
            raise OpenodeConfigError(
                'Specify the static files directory '
                'with setting STATIC_ROOT'
            )

    if errors:
        errors.append(
            'Run command (after fixing the above errors)\n'
            '    python manage.py collectstatic\n'
        )

    print_errors(errors)
    if django_settings.STATICFILES_STORAGE == \
        'django.contrib.staticfiles.storage.StaticFilesStorage':

        if not os.path.isdir(django_settings.STATIC_ROOT):
            openode_warning(
                'Please run command\n\n'
                '    python manage.py collectstatic'

            )


def test_csrf_cookie_domain():
    """makes sure that csrf cookie domain setting is acceptable"""
    #todo: maybe use the same steps to clean domain name
    csrf_cookie_domain = django_settings.CSRF_COOKIE_DOMAIN
    if csrf_cookie_domain is None or str(csrf_cookie_domain.strip()) == '':
        raise OpenodeConfigError(
            'Please add settings CSRF_COOKIE_DOMAN and CSRF_COOKIE_NAME '
            'settings - both are required. '
            'CSRF_COOKIE_DOMAIN must match the domain name of yor site, '
            'without the http(s):// prefix and without the port number.\n'
            'Examples: \n'
            "    CSRF_COOKIE_DOMAIN = '127.0.0.1'\n"
            "    CSRF_COOKIE_DOMAIN = 'example.com'\n"
        )
    if csrf_cookie_domain == 'localhost':
        raise OpenodeConfigError(
            'Please do not use value "localhost" for the setting '
            'CSRF_COOKIE_DOMAIN\n'
            'instead use 127.0.0.1, a real IP '
            'address or domain name.'
            '\nThe value must match the network location you type in the '
            'web browser to reach your site.'
        )
    if re.match(r'https?://', csrf_cookie_domain):
        raise OpenodeConfigError(
            'please remove http(s):// prefix in the CSRF_COOKIE_DOMAIN '
            'setting'
        )
    if ':' in csrf_cookie_domain:
        raise OpenodeConfigError(
            'Please do not use port number in the CSRF_COOKIE_DOMAIN '
            'setting'
        )


def test_settings_for_test_runner():
    """makes sure that debug toolbar is disabled when running tests"""
    errors = list()
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        errors.append(
            'When testing - remove debug_toolbar from INSTALLED_APPS'
        )
    if 'debug_toolbar.middleware.DebugToolbarMiddleware' in \
        django_settings.MIDDLEWARE_CLASSES:
        errors.append(
            'When testing - remove debug_toolbar.middleware.DebugToolbarMiddleware '
            'from MIDDLEWARE_CLASSES'
        )
    print_errors(errors)


def test_avatar():
    """if "avatar" is in the installed apps,
    checks that the module is actually installed"""
    if 'avatar' in django_settings.INSTALLED_APPS:
        try_import('Image', 'PIL', short_message=True)
        try_import(
            'avatar',
            '-e git+git://github.com/ericflo/django-avatar.git#egg=avatar',
            short_message=True
        )


# def test_haystack():
#     if 'haystack' in django_settings.INSTALLED_APPS:
#         try_import('haystack', 'django-haystack', short_message=True)
#         if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):
#             errors = list()
#             if not hasattr(django_settings, 'HAYSTACK_SEARCH_ENGINE'):
#                 message = "Please HAYSTACK_SEARCH_ENGINE to an appropriate value, value 'simple' can be used for basic testing"
#                 errors.append(message)
#             if not hasattr(django_settings, 'HAYSTACK_SITECONF'):
#                 message = 'Please add HAYSTACK_SITECONF = "openode.search.haystack"'
#                 errors.append(message)
#             footer = 'Please refer to haystack documentation at http://django-haystack.readthedocs.org/en/v1.2.7/settings.html#haystack-search-engine'
#             print_errors(errors, footer=footer)


# def test_longerusername():
#     """tests proper installation of the "longerusername" app
#     """
#     errors = list()
#     if 'longerusername' not in django_settings.INSTALLED_APPS:
#         errors.append(
#             "add 'longerusername', as the first item in the INSTALLED_APPS"
#         )
#     else:
#         index = django_settings.INSTALLED_APPS.index('longerusername')
#         if index != 0:
#             message = "move 'longerusername', to the beginning of INSTALLED_APPS"
#             raise OpenodeConfigError(message)
#     if errors:
#         errors.append('run "python manage.py migrate longerusername"')
#         print_errors(errors)


# def test_settings_among_template():
#     from openode.setup_templates import settings as settings_template
#     import settings as project_settings
#     ignore_changed_keys = (
#         'ROOT_URLCONF',
#         'DOCUMENT_ROOT',
#         'WYSIWYG_NODE_ROOT',
#         'WYSIWYG_THREAD_ROOT',
#         'ORGANIZATION_LOGO_ROOT',
#         'ORGANIZATION_LOGO_URL',
#         'FILE_UPLOAD_TEMP_DIR',
#         'CSRF_COOKIE_NAME',
#         'PROJECT_ROOT',
#         'MEDIA_ROOT',
#         'STATIC_ROOT',
#         'LOCALE_PATHS',
#         "OPENODE_EXTRA_SKINS_DIR",

#         "IMPORT_FILES_DIR",

#         "CELERY_LOG_FILE",
#         "LOGGING",
#         "LOG_DIR",
#         "MAIN_LOG",
#         )
#     errors = []

#     project_settings_dict = project_settings.__dict__
#     settings_template_dict = settings_template.__dict__

#     for key, value in project_settings_dict.iteritems():
#         if key.startswith('_'):
#             continue

#         if key not in settings_template_dict:
#             openode_warning('WARNING: Atribute %s - excessing key in project settings comparing to openode/setup_template/settings.py' % key)
#             continue

#         if key in ignore_changed_keys:
#             continue

#         template_value = settings_template_dict[key]
#         if type(template_value) == str and template_value.startswith('{{') and template_value.endswith('}}'):
#             continue
#         if value != template_value:
#             openode_warning('WARNING: Atribute %s - detected change in project settings comparing to openode/setup_template/settings.py' % key)

#     for key, value in settings_template_dict.iteritems():
#         if key.startswith('_'):
#             continue

#         if key not in project_settings_dict:
#             errors.append('WARNING: Atribute %s - missing key in project settings comparing to openode/setup_template/settings.py' % key)
#             continue

#     if errors:
#         print_errors(errors)


def run_startup_tests(verbosity_level=0):
    """function that runs
    all startup tests, mainly checking settings config so far
    """

    if verbosity_level >= 1:
        print RUN_STARTUP_TESTS_HEADER

    #todo: refactor this when another test arrives
    # test_settings_among_template()
    test_template_loader()
    test_encoding()
    test_modules()
    test_openode_url()
    #test_postgres()
    test_middleware()
    # test_celery()
    # test_csrf_cookie_domain()
    test_staticfiles()
    test_new_skins()
    # test_longerusername()
    test_avatar()
    # test_haystack()
    settings_tester = SettingsTester({
        'CACHE_MIDDLEWARE_ANONYMOUS_ONLY': {
            'value': True,
            'message': "add line CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True"
        },
        'USE_I18N': {
            'value': True,
            'message': 'Please set USE_I18N = True and\n'
                'set the LANGUAGE_CODE parameter correctly'
        },
        'LOGIN_REDIRECT_URL': {
            'message': 'add setting LOGIN_REDIRECT_URL - an url\n'
                'where you want to send users after they log in\n'
                'a reasonable default is\n'
                'LOGIN_REDIRECT_URL = OPENODE_URL'
        },
        'OPENODE_FILE_UPLOAD_DIR': {
            'test_for_absence': True,
            'message': 'Please replace setting OPENODE_FILE_UPLOAD_DIR ',
            'replace_hint': "with MEDIA_ROOT = '%s'"
        },
        'OPENODE_UPLOADED_FILES_URL': {
            'test_for_absence': True,
            'message': 'Please replace setting OPENODE_UPLOADED_FILES_URL ',
            'replace_hint': "with MEDIA_URL = '/%s'"
        },
        'RECAPTCHA_USE_SSL': {
            'value': True,
            'message': 'Please add: RECAPTCHA_USE_SSL = True'
        },
        # 'HAYSTACK_SITECONF': {
        #     'value': 'openode.search.haystack',
        #     'message': 'Please add: HAYSTACK_SITECONF = "openode.search.haystack"'
        # }
    })
    settings_tester.run()
    test_media_url()
    if 'manage.py test' in ' '.join(sys.argv):
        test_settings_for_test_runner()

    if verbosity_level >= 1:
        print RUN_STARTUP_TESTS_FOOTER


@transaction.commit_manually
def run():
    """runs all the startup procedures"""

    # verbosity
    args = sys.argv
    verbosity_level = 1
    if "-v" in args:
        verbosity_level = int(args[args.index("-v") + 1])
    elif "--verbosity" in ' '.join(args):
        for arg in args:
            if arg.startswith("--verbosity="):
                verbosity_level = int(arg.split("=")[1])

    try:
        if django_settings.RUN_STARTUP_TEST:
            run_startup_tests(verbosity_level)
    except OpenodeConfigError, error:
        transaction.rollback()
        print error
        sys.exit(1)

    try:
        transaction.commit()
    except Exception, error:
        print error
        transaction.rollback()
