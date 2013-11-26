This manual page is obsolete!

.. _install-localhost:

Install localhost
=================

version draft 9, Mar 2013

*by Jan Češpivo (jan.cespivo@coex.cz) and Ing. Václav Chalupníček (vasek.chalupnicek@coex.cz)*

This installation manual will help you to install developer’s environment of Pluto project (source code including all dependencies) for learning and contributing purposes. This manual is written for Ubuntu 12.04, but may still be valid for other Linux distributions.

Prerequisities are standard open source developers tools and skills. Including git, virtualenv, python, pip, PostgreSQL.

Pluto is Askbot’s fork (https://github.com/ASKBOT/askbot-devel). It’s an application, that follows Q&A principles. Pluto adds Club structure, new Permissions and Document module to it.
Document may be represented by either wiki Posts or uploaded files with ordinary office content (doc, pptx, odt, pdf, ...) that are automatically converted using Mayan EDMS (including OCR, JPEG preview and fulltext indexing features).


Requirements
------------

Follow the “Pluto: :ref:`install-server`. instructions” manual to find all required dependencies, including Elastic Search

Installation commands
---------------------

create database in postgresql
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    sudo su - postgres
    psql
    postgres# create database pluto;
    manage access to db according to your security policy
    postgres# \q
    # exit

get source code - Pluto
^^^^^^^^^^^^^^^^^^^^^^^
::

    mkdir <your-pluto-dev-dir>
    git clone git@git.coex.cz:pluto.git

start virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^
::

    virtualenv env --no-site-packages
    source env/bin/activate

start develop setup (this installs all dependencies)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    cd pluto
    # be sure to have installed pip==1.3.1
    (env)# python setup.py develop
    cd pluto

database structure
^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    cp settings_local.default.py settings_local.py
    # edit and fill in settings_local.py. Be sure to override DATABASE settings and DOMAIN_NAME.

    # when prompted, fill-in both username and email with your email address, to keep things consitent.
    (env)# ./manage.py syncdb

test it!
^^^^^^^^
::

    (env)# ./manage.py runserver
    open browser on http://localhost:8000


Standard project start commands
-------------------------------
::

    # cd pluto-project
    # source env/bin/activate
    (env)# ./manage.py runserver
    #open browser on http://localhost:8000

Celery
^^^^^^
::

    ./manage.py celeryd

    # or
    ./manage.py celeryd -E
    # for monitoring queue ans tasks with
    ./manage.py celeryev


This run only one worker and requests do DocumentAPI will be in FIFO queue.
For celery is required django-kombu in version 0.9.4 (0.9.2 contain bug)

SASS - CSS compilator
^^^^^^^^^^^^^^^^^^^^^

If you want to change Pluto’s CSS, you need to write them in SASS located at ``pluto/pluto/media/style``

install developer’s tools::

    sudo apt-get install ruby1.9.1
    sudo gem install sass
    sudo gem install compass
    sudo gem install zurb-foundation

start on-the-fly compilator::

    cd pluto/pluto/media/style
    compass watch

Sphinx documentation
^^^^^^^^^^^^^^^^^^^^
::

    # install necessary tools
    aptitude install sphinx-common
    # enter documents directory
    cd docs
    # edit doc files i.e. index.rst
    # build new doc
    make html

Managing translations
^^^^^^^^^^^^^^^^^^^^^

**Make messages (if source code has changed)**
Whenever you change a translation string or create new, you need to step in the instance directory, in the virtualenv and run::

    cd ../pluto/pluto
    ../../pluto-project/manage.py jinja2_makemessages -a
    cd deps/livesettings
    ../../../../pluto-project/manage.py jinja2_makemessages -a

where ``../pluto/pluto`` is relative path to your source codes

**Translate**

After this, you can translate new translation strings in rosetta, or elsewhere.

**Compile**

To see things changed you need to compile messages running::

    cd ../pluto/pluto
    ../../pluto-project/manage.py compilemessages
    cd deps/livesettings/
    ../../../../pluto-project/manage.py compilemessages

You need to restart your server after each messages recompilation since they are loaded at server start (this is/should be automatic in production environment).

Updating source code
^^^^^^^^^^^^^^^^^^^^
Please follow instructions howto update running instance.
