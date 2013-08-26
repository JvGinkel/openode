# -*- coding: utf-8 -*-

from openode.skins.loaders import render_into_skin


def server_error(request):
    return render_into_skin("500.jinja.html", {}, request, status_code=500)


def not_found(request):
    return render_into_skin("404.jinja.html", {}, request, status_code=404)
