# -*- coding: utf-8 -*-

from datetime import datetime
import sys

from fabric.api import env, run, local, task, cd, get
from fabric.contrib.console import confirm
from fabric.context_managers import lcd
from fabtools.python import virtualenv

import fab_settings

################################################################################
################################################################################

env.virtualenv_path = 'env'
env.user = fab_settings.USER
env.output_prefix = False
env.forward_agent = True
env.roledefs = fab_settings.ROLEDEFS
env.local_dumps_dir = fab_settings.DUMPS_DIR

################################################################################
################################################################################


@task
def start():
    """
    Run application
    """
    with virtualenv(env.virtualenv_path, local=True):
        with lcd("./openode/"):
            local("python manage.py runserver")


################################################################################


@task
def update_locale_db():
    """
    Create databaze dump on production server and restore on development (local) machine
    """

    ctx = env
    ctx['timestamp'] = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    ctx['tar_name'] = '%(user)s_db_dump_%(timestamp)s.tar' % ctx
    ctx['gz_name'] = '%(tar_name)s.gz' % ctx

    with cd("~/dumps"):
        run('pg_dump -U %(user)s -Ox -Ft -f %(tar_name)s %(user)s' % ctx)
        run('gzip %(tar_name)s' % ctx)

    local("mkdir -p %(local_dumps_dir)s" % env)
    get("~/dumps/%(gz_name)s" % ctx, local_path=env.local_dumps_dir)
    local("gzip -d %(local_dumps_dir)s/%(gz_name)s" % ctx)
    local('psql -d openode -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"')
    local("pg_restore -O -d openode %(local_dumps_dir)s/%(tar_name)s" % ctx)


################################################################################


@task
def create_tag():
    sys.stdout.write("Current tags:\n")
    local('git tag -l')

    version = raw_input("Enter name of new tag: ")
    local('git tag -a "%s"' % version)
    if confirm("Call git push --tags "
               "and send information to remote server?", default=False):
        local('git push --tags')
