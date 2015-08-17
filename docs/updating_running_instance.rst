
.. _upgrade-existing-instance:

Updating existing instance
==========================

version draft 9, Mar 2013

*by Mgr. Martin Kubát (martin.kubat@coex.cz)*

This document describes, how to update existing installation of Pluto to the latest version.

Please keep in mind, that you should always make backup of both files and database before starting an upgrade in production environment!


Prevent users from accessing the instance while upgrading
---------------------------------------------------------
TODO

Get into virtualenv
-------------------

*if not in virtualenv automatically after logging in (safe to run anyway)*::

    cd ~/cgi-bin/pluto-project
    source ./env/bin/activate

Update source code
------------------

*Login as pluto user*
::

    cd ~/cgi-bin/pluto/pluto
    git pull
    cd ~/cgi-bin/pluto-project

Manually change settings and urls
---------------------------------

*When there is something different in settings.py or urls.py move it by hand to the installed instance*::

    ~/cgi-bin/pluto-project/<settings|urls>.py

*You should always check setting values that are excluded from automatic change detection. Look up for actual version in your code in file pluto/startup_procedures.py*::

    ignore_changed_keys = (
       'TINYMCE_JS_ROOT',
       'ROOT_URLCONF',
       'DOCUMENT_ROOT',
       'WYSIWYG_CLUB_ROOT',
       'WYSIWYG_THREAD_ROOT',
       'ORGANIZATION_LOGO_ROOT',
       'ORGANIZATION_LOGO_URL',
       'FILE_UPLOAD_TEMP_DIR',
       'CSRF_COOKIE_NAME',
       'PROJECT_ROOT',
       'MEDIA_ROOT',
       'STATIC_ROOT',
       'LOCALE_PATHS',
       "LOGGING",
       "LOG_DIR",
       "MAIN_LOG",
    )

*Check that everything is all right*::

    ./manage.py runserver

Update database structure
-------------------------

If exist some new models generated in external libraries (safe to run anyway)::

    ./manage.py syncdb

If exist some changes in models (safe to run anyway)::

    ./manage.py migrate

Prepare static files
--------------------

When is some new/updated static file (safe to run anyway)::

    ./manage.py collectstatic

Translating strings
-------------------

Translations are made localy or in a testing environment using Rosetta. It's accessible through admin interface for all users that are members of the 'translators' group (please note that all letters must be small). Access control is validated using group name string matching, so group itself may be without any particular permission.

Compile translation messages
----------------------------

get into the instance directory (usually pluto-project) and run under virtualenv::

    cd ../pluto/pluto
    ../../pluto-project/manage.py compilemessages
    cd deps/livesettings/
    ../../../../pluto-project/manage.py compilemessages
    cd ../../../../pluto-project

where ``pluto-project`` is your installed instance and is in the same directory as pluto source code


Recount unread posts
--------------------
::

    ./manage.py recount_unread_posts

Reindex fulltext
----------------
::

    ./manage.py rebuild_index

Reload project
--------------

You have two options, first doesn’t require root access, but will not reflect any changes in supervisor’s settings.
With project command (it kills all pluto gunicorn and celery processes and wait for respawn)::

    ./manage.py restart

OR::

    # Login as root (an alternative is to kill gunicorn process and wait for respawn)
    supervisorctl

    # If something has changed in supervisor’s settings file
    supervisorctl> update pluto

    # Restart gunicorn and celery workers
    supervisorctl> restart pluto:
    # or
    supervisorctl> restart pluto:pluto_gunicorn
    supervisorctl> restart pluto:pluto_celery
