# -*- coding: utf-8 -*-

from django.views.decorators import csrf
from django.http import HttpResponse
from openode.models.thread import AttachmentFileNode  # , AttachmentFileThread
from django.shortcuts import get_object_or_404
from openode.models.node import Node

# TODO: clean


@csrf.csrf_exempt
def upload_attachment_node(request, node_id):

    node = get_object_or_404(Node, pk=node_id)

    upload = request.FILES['upload']
    af = AttachmentFileNode.objects.create(
        file_data=upload,
        node=node,
    )
    url = af.file_data.url

    return HttpResponse("""
        <script type='text/javascript'>
            window.parent.CKEDITOR.tools.callFunction(%s, '%s');
        </script>
    """ % (
        request.GET['CKEditorFuncNum'],
        url
        )
    )


# @csrf.csrf_exempt
# def upload_attachment_thread(request, thread_id):

#     upload = request.FILES['upload']
#     af = AttachmentFileThread.objects.create(
#         file_data=upload
#     )
#     url = af.file_data.url

#     return HttpResponse("""
#         <script type='text/javascript'>
#             window.parent.CKEDITOR.tools.callFunction(%s, '%s');
#         </script>
#     """ % (
#         request.GET['CKEditorFuncNum'],
#         url
#         )
#     )
