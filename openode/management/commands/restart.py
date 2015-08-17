# -*- coding: utf-8 -*-

import os
import psi
import psi.process
import signal

from django.core.management.base import NoArgsCommand


class Command(NoArgsCommand):
    help = "Reloads project with HUP signal."

    requires_model_validation = False

    def handle_noargs(self, **options):
        def hup():
            processes = psi.process.ProcessTable().values()
            user_processes = [p for p in processes if p.euid == os.geteuid()]
            user_processes_pids = [p.pid for p in user_processes]

            parent_pids = {}
            pid_names = {}

            for p in user_processes:

                if (("gunicorn_django" in p.command) or ("celeryd" in p.command)) and p.ppid in user_processes_pids:
                    if not p.ppid in parent_pids:
                        parent_pids[p.ppid] = []
                    parent_pids[p.ppid] += [p]
                    pid_names[p] = p.command

            if parent_pids:
                print "GOING TO RELOAD SUPERVISORD WORKERS..."

                for pid in parent_pids:
                    print u"RELOADING PARENT PID: %s %s" % (pid, pid_names[pid])
                    try:
                        os.kill(pid, signal.SIGHUP)
                    except OSError, e:
                        print u"RELOAD FAILED FOR PARENT PID: %s %s FAILED: %s %s" (pid, pid_names[pid], type(e), e)
                print "TODO: CHECK EVERYTHING IS RUNNING OK"

            else:
                print "NO PARENT PIDS FOUND"

        hup()
