# -*- coding: utf-8 -*-
from datetime import datetime
# from functools import wraps
# import os
import sys
# import textwrap

from fabric.api import env, run, local, task, cd
from fabric.contrib.console import confirm
from fabric.context_managers import lcd
from fabtools.python import virtualenv
# from fabtools.vagrant import vagrant_settings  # required for fab commands

env.virtualenv_path = 'env'
# env.cwd = '~/cgi-bin'
env.output_prefix = False
env.forward_agent = True
# env.roledefs = {
#     'development': ['hranipex@10.0.1.5'],
#     'production': ['hranipex@10.0.1.5'],
#     'test': ['hranipex@10.0.1.6'],
# }

TARGET_LOCAL = 'local'
TARGET_REMOTE = 'remote'
CONSOLE_WIDTH = 80


@task
def start():
    """
    Run application
    """
    with virtualenv(env.virtualenv_path, local=True):
        with lcd("./openode/"):
            local("python manage.py runserver")


################################################################################

# def vagrant_task(f):
#     @wraps(f)
#     def wrapper(*args, **kwds):
#         with vagrant_settings():
#             return f(*args, **kwds)
#     return task(wrapper)


# def _console_print(string=''):
#     print textwrap.fill(string, width=CONSOLE_WIDTH, replace_whitespace=False)


# @task
# def backup_db():
#     ctx = env
#     ctx['timestamp'] = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
#     ctx['file_path'] = '~/dumps/%(user)s_db_dump_%(timestamp)s.tar' % ctx

#     run('pg_dump -U %(user)s -Ox -Ft -f %(file_path)s %(user)s' % ctx)
#     run('gzip %(file_path)s' % ctx)

@task
def update_locale_db():
    """
    Create databaze dump on production server and restore on development (local) machine
    """
    ctx = env
    ctx['timestamp'] = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    ctx['file_path'] = '~/dumps/%(user)s_db_dump_%(timestamp)s.tar' % ctx

    run('pg_dump -U %(user)s -Ox -Ft -f %(file_path)s %(user)s' % ctx)
    run('gzip %(file_path)s' % ctx)


@task
def create_tag():
    sys.stdout.write("Seznam soucasnych tagu:\n")
    local('git tag -l')

    version = raw_input("Zadejte nazev noveho tagu: ")
    local('git tag -a "%s"' % version)
    if confirm("Mohu zavolat git push --tags "
               "a odeslat informace do remote serveru?", default=False):
        local('git push --tags')


@task
def deploy():
    if confirm('Chcete vytvorit novy tag (verzi) pro soucasny release?', default=False):
        create_tag()

    # if confirm('Chcete zazalohovat DB?', default=False):
    #     backup_db()

    # if confirm("Mohu zahajit nasazeni na vzdaleny server?"):
    #     with virtualenv(env.virtualenv_path):
    #         run("git pull")
    #         run("pip install -r requirements/production.txt --no-deps")
    #         with cd("project/resources/css"):
    #             run("/var/lib/gems/1.8/bin/bundle exec compass compile")
    #         run("./compilemessages.sh")
    #         run("./collectstatic.sh")
    #         run("./reload_webserver.py")


# @task
# def rsyncd():
#     """
#     Initial project setup
#     """
#     local("vagrant rsync-auto")


# @vagrant_task
# def serverd(branch_code="cz"):
#     with virtualenv(env.virtualenv_path):
#         run("python manage.py runserver 0.0.0.0:8080 --settings=project.domains.%s.settings" % branch_code)


# @vagrant_task
# def compassd(command='watch'):
#     with cd('project/resources/css'):
#         run('/var/lib/gems/1.8/bin/bundle exec compass %s' % command)


# @vagrant_task
# def setup_vagrant():
#     with virtualenv(env.virtualenv_path):
#         run("/bin/bash compilemessages.sh")

#     with cd("project/resources/css"):
#         run("/var/lib/gems/1.8/bin/bundle exec compass compile")


# @task
# def create_language_mutation(target_branch_code, target=TARGET_LOCAL):
#     cmd = 'python manage.py create_language_mutation --settings=project.domains.%s.settings' % target_branch_code
#     if target == TARGET_LOCAL:
#         local(cmd)
#     elif target == TARGET_REMOTE:
#         with virtualenv(env.virtualenv_path):
#             run(cmd)


# @task
# def create_branch(new_branch_code, target=TARGET_LOCAL):
#     NEW_BRANCH_SETTINS_INSTRUCTIONS = '''
# V hlavnich settings.py je treba pridat pobocku do:
#     - SITE_BRANCH_CODE_TO_ID (inkrementalne podle posledni)
#     - BRANCHES
#     - DOMAIN_SETTINGS_BRANCHES
#     - CYRILLIC_WRITING (pridani mutace, pokud je v cyrilce)

# V settings.py nove zalozene pobocky je treba upravit:
#     - LANGUAGE_CODE (vychozi jazyk pobocky)
#     - LANGUAGES (dle toho adekvatne editovat locales slozku)
#     - ZOPIM_ID_LANGUAGES_MAPPING
#     - nastaveni emailu
#     - QAD_DOMAIN_ID
#     - QAD_LANGUAGE_MAPPING
#     - QAD_DEFAULT_LOCAL_CUSTOMER_LANGUAGE
#     - QAD_DEFAULT_FOREIGN_CUSTOMER_LANGUAGE
#     - GA_ACCOUNT_ID
#     - QAD_WEBSPEED_ENCODING (v pripade vyjimecneho kodovani)

#     Pro produkcni ucely pri vytvareni nove pobocky pro switch DNS
#     je dobre mit v domain settings nasledujici nastaveni:
#         SITE_DOMAIN_PREFIX = 'test'
#         SITE_DOMAIN = '%s.hranipex.lt' % SITE_DOMAIN_PREFIX
#         ALLOWED_RECIPIENTS = [email for name, email in ADMINS]
#         EMAIL_BACKEND = "project.core.email_backends.FilteredEmailBackend"

# Je potreba:
#     - dodat nove podklady pro pdf (např. hlavickovy-papir.pdf,
#                                          srovnavaci-tabulky-fr-fr.pdf, ...).
#     - nahrat do locales nove preklady.
#     - editovat kontaktni informace v contact_ks_map.html, email sablonach.
#     - pridat pobocku ve všech shell skriptech:
#         *_all.sh + skripty, kde je vycet pobocek

# Zkratka zkontrolovat celou novou domain slozku pobocky.
#     '''
#     if confirm('Chcete zalozit domains slozku pro novou pobocku?'):
#         local('pwd')
#         with lcd('project/domains'):
#             local('cp -r cz %s' % new_branch_code)
#             local('cp cz/templates/emails/cs-cz/*support.html %s/templates/emails/en-gb/' % new_branch_code)
#             with lcd(os.path.join(new_branch_code, 'locale')):
#                 local('rm -rf `ls | grep -v "^en_GB$"`')
#             with lcd(os.path.join(new_branch_code, 'templates', 'emails')):
#                 local('rm -rf `ls | grep -v "^en-gb$"`')
#         _console_print('Slozka byla zalozena.')
#         print(NEW_BRANCH_SETTINS_INSTRUCTIONS)

#     if confirm(textwrap.fill(
#         'Mate spravne nastaveny veskera nastaveni nove pobocky? '
#         'Chcete zalozit pobocku v DB?', width=CONSOLE_WIDTH
#     )):
#         cmd = 'python manage.py setup --copy-site=1 --settings=project.domains.%s.settings' % new_branch_code
#         if target == TARGET_LOCAL:
#             local(cmd)
#         elif target == TARGET_REMOTE:
#             with virtualenv(env.virtualenv_path):
#                 run(cmd)

#         _console_print('\nNezapomente v administraci nastavit delivery way.')
