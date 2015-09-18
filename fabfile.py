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
            local("python manage.py runserver 0.0.0.0:8000")


################################################################################

@task
def dump_db():
    ctx = env
    ctx['timestamp'] = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    ctx['tar_name'] = '%(user)s_db_dump_%(timestamp)s.tar' % ctx

    with cd("~/dumps"):
        run('pg_dump -U %(user)s -Ox -Ft -f %(tar_name)s %(user)s' % ctx)
        run('gzip %(tar_name)s' % ctx)

    return ctx

@task
def update_locale_db():
    """
    Create databaze dump on production server and restore on development (local) machine
    """

    ctx = env
    ctx.update(dump_db())
    ctx['gz_name'] = '%(tar_name)s.gz' % ctx

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

################################################################################


@task
def deploy():
    """
        TODO: add all related commands
    """
    if confirm('Create tag for this release?', default=False):
        create_tag()

    if confirm('Backup DB?', default=False):
        dump_db()

    if confirm("Start deploying to remote server?"):
        with cd("cgi-bin"):
            run("git pull")

            alter_sql_path = "alter.sql"

            if confirm('Show alter.sql file?', default=False):
                print 40 * "-"
                run("cat %s" % alter_sql_path)
                print 40 * "-"

            if confirm('Execute alter.sql file?', default=False):
                run("psql -f %s" % alter_sql_path)

            with virtualenv(env.virtualenv_path):

                run("compilemessages.sh")
                run("./reload_webserver.py")
