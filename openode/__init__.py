# -*- coding: utf-8 -*-

"""
:synopsis: the Django Q&A forum application

Functions in the openode module perform various
basic actions on behalf of the forum application
"""

import os
import platform

# from django.conf import settings

VERSION = (1, 0, 4)

#keys are module names used by python imports,
#values - the package qualifier to use for pip
#ATTENTION - only importable modlules may be listed, due to automatic testing, i.e. ipython cannot be imported, so violates tests
REQUIREMENTS = {
    'akismet': 'akismet==0.2.0',
    'django': 'Django==1.3.7',
    'jinja2': 'Jinja2==2.6',
    'coffin': 'Coffin==0.3.7',
    'oauth2': 'oauth2==1.5.211',
    'markdown2': 'markdown2==2.1.0',
    'html5lib': 'html5lib==0.95',
    'keyedcache': 'django-keyedcache==1.4-6',
    # 'threaded_multihost': 'django-threaded-multihost',
    #'robots': 'django-robots==0.9.1',
    'unidecode': 'Unidecode==0.04.10',
    'django_countries': 'django-countries==1.0.5',

    'djcelery': 'django-celery==3.0.17',
    # 'celery_with_redis': 'celery-with-redis==3.0',
    'redis': "redis==2.7.4",

    # 'djkombu': 'django-kombu==0.9.4',
    # 'followit': 'django-followit==0.0.3', # following user is not available in Openode anymore
    'recaptcha_works': 'django-recaptcha-works==0.3.4',
    'openid': 'python-openid==2.2.5',
    # 'pystache': 'pystache==0.3.1',
    'pytz': 'pytz==2012j',
    # 'longerusername': 'longerusername==0.4',
    'bs4': 'beautifulsoup4==4.1.3',
    'mptt': 'django-mptt==0.5.4',
    'Pyro4': 'Pyro4==4.17',
    'gunicorn': 'gunicorn==0.17.2',
    'rosetta': 'django-rosetta==0.7.1',
    'admin_tools': 'django-admin-tools==0.4.1',
    'bleach': 'bleach==1.2.1',
    "magic": "python-magic==0.4.3",
    "sorl.thumbnail": "sorl-thumbnail==11.12",
    "PIL": "Pillow==2.0.0",
    "psycopg2": "psycopg2==2.5",
    "haystack": "django-haystack==2.0.0",
    "pyelasticsearch": "pyelasticsearch==0.5",
    "psi": "PSI==0.3b2",

}

# TODO remove feature Ask/Answer by email
if platform.system() != 'Windows':
    REQUIREMENTS['lamson'] = 'lamson==1.1'

#necessary for interoperability of django and coffin
try:
    from openode import patches
    from openode.deployment.assertions import assert_package_compatibility
    assert_package_compatibility()
    patches.patch_django()
    patches.patch_coffin()  # must go after django
except ImportError:
    pass


def get_install_directory():
    """returns path to directory
    where code of the openode django application
    is installed
    """
    return os.path.dirname(__file__)


def get_path_to(relative_path):
    """returns absolute path to a file
    relative to ``openode`` directory
    ``relative_path`` must use only forward slashes
    and must not start with a slash
    """
    root_dir = get_install_directory()
    assert(relative_path[0] != 0)
    path_bits = relative_path.split('/')
    return os.path.join(root_dir, *path_bits)


def get_version():
    """returns version of the openode app
    this version is meaningful for pypi only
    """
    return '.'.join([str(subversion) for subversion in VERSION])


def get_database_engine_name():
    """returns name of the database engine,
    independently of the version of django
    - for django >=1.2 looks into ``settings.DATABASES['default']``,
    (i.e. assumes that openode uses database named 'default')
    , and for django 1.1 and below returns settings.DATABASE_ENGINE
    """
    import django
    from django.conf import settings as django_settings
    major_version = django.VERSION[0]
    minor_version = django.VERSION[1]
    if major_version == 1:
        if minor_version > 1:
            return django_settings.DATABASES['default']['ENGINE']
        else:
            return django_settings.DATABASE_ENGINE
