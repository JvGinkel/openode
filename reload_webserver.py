#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
import psi
import psi.process
import signal

HUP_PARENT_LIST = ["gunicorn_django"]
KILL_PARENT_LIST = ["celeryd"]


def reload_project():
    processes = psi.process.ProcessTable().values()
    user_processes = [p for p in processes if p.euid == os.geteuid()]
    user_processes_pids = [p.pid for p in user_processes]

    pids_to_hup = []
    pids_to_kill = []
    pid_names = {}

    for user_process in user_processes:
        for process_name in HUP_PARENT_LIST + KILL_PARENT_LIST:
            parent_pid = user_process.ppid
            if process_name in user_process.command and parent_pid in user_processes_pids:
                if process_name in HUP_PARENT_LIST:
                    if parent_pid not in pids_to_hup:
                        pids_to_hup.append(parent_pid)
                elif process_name in KILL_PARENT_LIST:
                    if parent_pid not in pids_to_kill:
                        pids_to_kill.append(parent_pid)
                pid_names[parent_pid] = user_process.command

    if pids_to_hup:
        for pid in pids_to_hup:
            print u"(HUP) RELOADING PARENT PID : %s %s" % (pid, pid_names[pid])
            try:
                os.kill(pid, signal.SIGHUP)
                time.sleep(1)
            except OSError, e:
                print u"(HUP) RELOAD FAILED FOR PARENT PID: %s %s FAILED: %s %s" (pid, pid_names[pid], type(e), e)
    else:
        print "(HUP) NO PIDS FOUND"

    if pids_to_kill:
        for pid in pids_to_kill:
            print u"(KILL) RELOADING PID : %s %s" % (pid, pid_names[pid])
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
            except OSError, e:
                print u"(KILL) RELOAD FAILED FOR PID: %s %s FAILED: %s %s" (pid, pid_names[pid], type(e), e)
    else:
        print "(KILL) NO PIDS FOUND"

if __name__ == '__main__':
    reload_project()
