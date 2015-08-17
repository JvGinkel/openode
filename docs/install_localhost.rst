.. _install-localhost:

Install localhost
===================

*by Mgr. Martin Kubát (martin.kubat@coex.cz) and Jan Češpivo (jan.cespivo@coex.cz)*

This system is based on the Askbot project - http://askbot.com/, some information may be useful, but almost everything has been changed. OPENode project is connected to Elasticsearch and Mayan EDMS project. Mayan and Elasticsearch customized instalation manuals are also included.
This instructions are for installation on Ubuntu platform, but may be valid for various other Linux distributions if you follow mentioned versions of dependencies.

Begin installation as your user with sudo rights.

Required packages
-----------------

Database engines
^^^^^^^^^^^^^^^^

Install PostgreSQL and Redis database servers
::
    sudo apt-get install postgresql-9.1 redis-server

Elasticsearch prerequisities
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install Java Development Kit
::
    sudo apt-get install openjdk-6-jre-headless


Tweak for debian based systems according to  http://elasticsearch-users.115913.n3.nabble.com/Tiny-issues-with-the-deb-package-on-Ubuntu-12-04-LTS-td3961419.html
::
    sudo ln -s /usr/lib/jvm/java-6-openjdk-amd64/ /usr/lib/jvm/java-6-openjdk

Project dependencies and libraries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install developer libraries
::
    sudo apt-get install python-virtualenv git postgresql-server-dev-9.1 python-dev libtiff4-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms1-dev libwebp-dev gettext


Mayan dependencies
^^^^^^^^^^^^^^^^^^

Install ocr software and converters, it also includes libreoffice-core
::
    sudo apt-get install unoconv
    sudo apt-get install convertall imagemagick graphicsmagick unpaper pdftohtml
    sudo apt-get install tesseract-ocr

For support another language but english install proper tesseract-oct-* package (for example czech)
::
    sudo apt-get install tesseract-ocr-ces

Environment
-----------

Database setup
^^^^^^^^^^^^^^

Change user to postgres
::
    sudo su postgres

OPENode database setup - change 'openodepass' to custom password
::
    echo "CREATE ROLE openode with password 'openodepass';CREATE DATABASE openode;GRANT ALL PRIVILEGES ON DATABASE openode TO openode;ALTER DATABASE openode OWNER TO openode;ALTER ROLE openode LOGIN;" | psql
    echo "ALTER SCHEMA public OWNER TO openode;" | psql -d openode

Mayan database setup - change 'mayanpass' to custom password
::
    echo "CREATE ROLE mayan with password 'mayanpass';CREATE DATABASE mayan;GRANT ALL PRIVILEGES ON DATABASE mayan TO mayan;ALTER DATABASE mayan OWNER TO mayan;ALTER ROLE mayan LOGIN;" | psql
    echo "ALTER SCHEMA public OWNER TO mayan;" | psql -d mayan

Become a normal user again
::
    exit


OPENode instalation
-------------------

OPENode projects directory
^^^^^^^^^^^^^^^^^^^^^^^^^

Change directory to projects
::
    cd ~/projects/

OPENode environment setup and installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Get source of project OPENode and compile&install dependencies
::
    git clone https://github.com/openode/openode.git
    cd openode
    virtualenv env
    source env/bin/activate
    
Fixed broken bdist_egg for zip_safe flag
::
    pip install django-mptt==0.5.4

Install openode
::
    python setup.py develop

Setup settings_local.py for OPENode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Setup project OPENode
::
    cd openode
    cp settings_local.default.py settings_local.py

Edit settings_local.py and customize all necessary variables. Keep an eye especially on these: DATABASE_PASSWORD, SECRET_KEY, DOCUMENT_HMAC_KEY, DOCUMENT_URI_ID

Set DEBUG mode
::
    DEBUG = True


OPENode initialization
^^^^^^^^^^^^^^^^^^^^^^

It asks you for admin username, email and password. It is recommended to set username same as email.
::
    ./manage.py syncdb

Compile translations
::
    ./manage.py compilemessages
    cd deps/livesettings/
    ../../manage.py compilemessages

Become a root again
^^^^^^^^^^^^^^^^^^^

Logout openode user
::
    exit

Elasticsearch instalation and setup
-----------------------------------

Instalation
^^^^^^^^^^^

Install Elasticsearch
::
    wget download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.20.5.deb -P /tmp/
    dpkg -i /tmp/elasticsearch-0.20.5.deb

Setup
^^^^^

Setup Elasticsearch
::
    nano /etc/elasticsearch/elasticsearch.yml

Edit/append a line to enable only local IP
::
    network.host: 127.0.0.1

Mayan instalation
-------------------

Mayan projects directory
^^^^^^^^^^^^^^^^^^^^^^^^^

Change directory to projects
::
    cd ~/projects/

Mayan environment setup and installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Get source of project Mayan and compile&install dependencies
::
    git clone git://github.com/rosarior/mayan.git
    git clone git@git.coex.cz:mayan_pyro_api.git
    ln -s ./mayan_pyro_api/pyro_api/ ./mayan/modules/
    cd mayan
    virtualenv env
    source env/bin/activate
    pip install -r mayan/requirements/production.txt
    pip install gunicorn==0.17.2
    pip install psycopg2==2.4.6
    pip install Pyro4==4.17


Setup settings_local.py for Mayan
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Edit settings_local.py
::
    nano settings_local.py


Paste into the file lines below and customize it (especially DATABASES - PASSWORD):
::
    import os

    DEBUG = True

    DOCUMENTS_DISPLAY_SIZE = "1600"
    DOCUMENTS_PRINT_SIZE = "1600"

    CONVERTER_GRAPHICS_BACKEND = "converter.backends.graphicsmagick"
    CONVERTER_GM_SETTINGS = "-limit files 1 -limit memory 2GB -limit map 2GB -density 200"

    OCR_QUEUE_PROCESSING_INTERVAL = 3
    OCR_NODE_CONCURRENT_EXECUTION = 2

    #######################################

    TIME_ZONE = 'Europe/Prague'

    #######################################

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), './'))
    LOG_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "..", "log"))

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',  # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
            'NAME': "mayan",     # Or path to database file if using sqlite3.
            'USER': 'mayan',                      # Not used with sqlite3.
            'PASSWORD': 'mayanpass',                  # Not used with sqlite3.
            'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
            'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
        }
    }


    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,

        'formatters': {
            'verbose': {
                'format': '%(levelname)s:[%(asctime)s] <%(name)s|%(filename)s:%(lineno)s> %(message)s'
            },
            'intermediate': {
                'format': '%(name)s <%(process)d> [%(levelname)s] "%(funcName)s() %(message)s"'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },

        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'intermediate'
            },
            'api_handler': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': os.path.join(LOG_ROOT, "api.log"),
                'formatter': 'verbose',
            },
        },

        'loggers': {
            'documents': {
                'handlers': ['console'],
                'propagate': True,
                'level': 'DEBUG',
            },
            "api": {
                'handlers': ['api_handler'],
                'level': 'INFO',
                'propagate': False,
            },
        }
    }

For support for another languages add line (for example czech):
::
    OCR_TESSERACT_LANGUAGE = "ces"  # default language for ocr


Enable Mayan remote API
^^^^^^^^^^^^^^^^^^^^^^^

Add app "pyro_api" to INSTALLED_APPS in Mayan's settings.py
::
    nano settings.py

Insert a line to INSTALLED_APPS
::
    INSTALLED_APPS = (
    # ...
    'pyro_api',
    # …
    )


Setup settings_local.py for Mayan remote API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Edit mayan_pyro_api/pyro_api/settings_local.py
::
    nano ../mayan_pyro_api/pyro_api/settings_local.py

Paste into the file lines below and customize it according to OPENode's settings (DOCUMENT_HMAC_KEY <-> HMAC_KEY, DOCUMENT_URI_ID <-> URI_ID, etc.):
::
    # mayan server IP
    SERVER_IP = "127.0.0.1"

    # SECRET key, random hash
    HMAC_KEY = "sd1fg86ds4f6sd8hg4sd6fg68sdf746g4"

    # SECRET id, random hash
    URI_ID = "1sadfasfg468h7j9g7j9h78gk6g54fg6f"

    # mayan port, example.
    URI_PORT = 33333

Mayan initialization
^^^^^^^^^^^^^^^^^^^^

It asks you for admin username, email and password.
::
    cd mayan
    ./manage.py syncdb
    ./manage.py migrate
