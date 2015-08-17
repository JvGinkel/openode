# -*- coding: utf-8 -*-

import os
import re
import signal


def restart_server(sender, **kwargs):
    request = kwargs.pop('request', {"META": {}})
    gunicorn_served = bool(re.match(r"gunicorn", request.META.get("SERVER_SOFTWARE", u"")))
    # print "IS GUNICORN SERVED %s" % gunicorn_served
    if gunicorn_served:
        print "RELOAD GUNICORN WORKERS..."
        try:
            os.kill(os.getppid(), signal.SIGHUP)
        except OSError, e:
            print "RELOAD GUNICORN WORKERS FAILED:", type(e), e
