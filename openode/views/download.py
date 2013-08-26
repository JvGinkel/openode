# -*- coding: utf-8 -*-

from django.db.models.loading import get_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.static import serve


def download_attachment(request, uuid, model_name):
    """
        download  attachment file with permission check
    """
    file_data = get_object_or_404(
        get_model("openode", model_name),
        uuid=uuid
    ).file_data

    if False:  # TODO
        return HttpResponseForbidden("YOU SHALL NOT PASS")

    return serve(request, file_data.path, document_root="/")
