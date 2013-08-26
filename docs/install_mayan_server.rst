
.. _mayan-server-installation-instructions:

Mayan server installation instructions
======================================
(for Debian Squeeze)

version draft 8, Feb 2013

*by Mgr. Martin Kubát (martin.kubat@coex.cz) and Ing. Václav Chalupníček (vasek.chalupnicek@coex.cz)*

This installation manual will help you to upgrade plain Debian Squeeze installation to fully functional Mayan EDMS - Free Open Source, Django based electronic document management system with integrated OCR capability.

The matter of security is not described (firewall, DB, etc.), you should follow corresponding documentation for each piece of software to fullfil at least basic security requirements.

Mayan EDMS is written in Python’s Django framework so there are more options how to deploy it on a webserver. We have chosen the nginx + gunicorn + supervisord + virtualenv method.

Note: More information about Pyro API is on “Pyro API install and settings” document (https://docs.google.com/a/coex.cz/document/d/142W9EBEzjMh32QsYj53buhfkyfA_YHuVDG-uSt65Q0I/edit#).

Set extra debian repositories and update
----------------------------------------
::

    # nano /etc/apt/sources.list
    deb http://ftp.de.debian.org/debian testing main non-free contrib
    # deb http://ppa.launchpad.net/libreoffice/ppa/ubuntu lucid main TODO?
    deb http://backports.debian.org/debian-backports squeeze-backports main

    # nano /etc/apt/apt.conf
    APT::Default-Release "stable";
    APT::Cache-Limit 50165824;

# apt-get update

Install dependencies
--------------------
::

    apt-get install nginx
    apt-get install supervisor postgresql-9.1 python-virtualenv git python-dev convertall imagemagick graphicsmagick unpaper pdftohtml libjpeg62-dev libfreetype6-dev
    apt-get install -t testing postgresql-server-dev-9.1
    apt-get install -t testing tesseract-ocr # ensure tesseract >= 3
    apt-get install -t testing tesseract-ocr-ces # tesseract support for Czech language

this install libreoffice as a dependency::

    apt-get install -t testing unoconv

Database - PostgreSQL
---------------------
::

    su postgres
    psql
    postgres=# CREATE USER mayan with password 'xxx';
    CREATE ROLE
    postgres=# CREATE DATABASE mayan;
    CREATE DATABASE
    postgres=# GRANT ALL PRIVILEGES ON DATABASE mayan to mayan;
    GRANT
    postgres=# ALTER DATABASE mayan OWNER TO mayan ;
    ALTER DATABASE
    postgres=# \c mayan
    mayan=# ALTER SCHEMA public OWNER TO mayan ;
    ALTER SCHEMA

Files - Virtualenv, Mayan, local settings
-----------------------------------------
::

    adduser --home /srv/mayan mayan
    su mayan
    cd
    mkdir www log cgi-bin
    cd cgi-bin
    # must be on /srv/mayan/cgi-bin/
    virtualenv env
    . env/bin/activate

    git clone git://github.com/rosarior/mayan.git
    pip install -r mayan/requirements/production.txt
    pip install gunicorn==0.17.2
    pip install Pyro4==4.17
    pip install psycopg2==2.4.6

    cd mayan
    nano settings_local.py  # edit DB settings
    OCR_TESSERACT_LANGUAGE = 'ces' # default language for ocr

    # nano settings.py
    #add “gunicorn” to INSTALLED_APPS

Environment - Nginx, Gunicorn, Supervisord
------------------------------------------

Supervisor
^^^^^^^^^^
file /etc/supervisor/conf.d/mayan.conf::

    [program:mayan_gunicorn]
    command=/srv/mayan/cgi-bin/env/bin/python manage.py run_gunicorn --workers=2 --timeout=300 --bind=unix:/srv/mayan/cgi-bin/mayan.sock
    directory=/srv/mayan/cgi-bin/mayan/
    user=mayan
    autostart=true
    autorestart=true
    redirect_stderr=true

    [program:pyro_api]
    command=/srv/mayan/cgi-bin/env/bin/python manage.py run_api
    directory=/srv/mayan/cgi-bin/mayan/
    autostart = true
    autorestart=true
    user=mayan

    [group:mayan]
    programs=mayan_gunicorn,pyro_api

nginx
^^^^^
file /etc/nginx/sites-enabled/mayan.conf::

    server {
        listen       80;
        server_name  mayan.hostname.tld;
        access_log /srv/mayan/log/nginx.access.log;
        error_log /srv/mayan/log/nginx.error.log;
           client_max_body_size 5M;
        location / {
               include /etc/nginx/proxy.conf;
               proxy_pass http://unix:/srv/mayan/cgi-bin/mayan.sock;
        }
        location /mayan-static/ {
               alias /srv/mayan/cgi-bin/mayan/static/;
        }
    }

Add opendocument format support (docx, xlsx, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    # nano /etc/magic, add:
    #------------------------------------------------------------------------------
    # $File: msooxml,v 1.1 2011/01/25 18:36:19 christos Exp $
    # msooxml:  file(1) magic for Microsoft Office XML
    # From: Ralf Brown <ralf.brown@gmail.com>
    # .docx, .pptx, and .xlsx are XML plus other files inside a ZIP
    #   archive.  The first member file is normally "[Content_Types].xml".
    # Since MSOOXML doesn't have anything like the uncompressed "mimetype"
    #   file of ePub or OpenDocument, we'll have to scan for a filename
    #   which can distinguish between the three types
    # start by checking for ZIP local file header signature
    0               string          PK\003\004
    # make sure the first file is correct
    >0x1E           string          [Content_Types].xml
    # skip to the second local file header
    #   since some documents include a 520-byte extra field following the file
    #   header,  we need to scan for the next header
    >>(18.l+49)     search/2000     PK\003\004
    # now skip to the *third* local file header; again, we need to scan due to a
    #   520-byte extra field following the file header
    >>>&26          search/1000     PK\003\004
    # and check the subdirectory name to determine which type of OOXML
    #   file we have
    >>>>&26         string          word/           Microsoft Word 2007+
    !:mime application/msword
    >>>>&26         string          ppt/            Microsoft PowerPoint 2007+
    !:mime application/vnd.ms-powerpoint
    >>>>&26         string          xl/             Microsoft Excel 2007+
    !:mime application/vnd.ms-excel
    >>>>&26         default         x               Microsoft OOXML
    !:strength +10

Pyro API (DocumentAPI)
^^^^^^^^^^^^^^^^^^^^^^
Pyro API for connect to document server is described in :ref:`pyro-api`

settings_local.py example:
^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    OCR_TESSERACT_LANGUAGE = "ces"  # default language for ocr
    WEB_THEME_THEME = "default"
    DOCUMENTS_PREVIEW_SIZE = "1200x1600"
    LANGUAGE_CODE = 'cs'
    CONVERTER_GRAPHICS_BACKEND = "converter.backends.imagemagick"
