# -*- coding: utf-8 -*-

from django.conf.urls.defaults import patterns, url


urlpatterns = patterns('openode.document',
    # url(r'^document/(?P<document_id>\d+)/$', "views.document_detail", name='document_detail'),
    # url(r'^document/(?P<document_id>\d+)/edit/', "views.document_edit", name='document_edit'),
    url(r'^retry-process-document/(?P<thread_pk>\d+)/', "views.retry_process_document", name='retry_process_document'),

    url(r'^download-as-zip/', "views.download_as_zip", name='download_as_zip'),

    url(r'^category/add/', "views.category_add", name='category_add'),

    url(r'^category/reorg/', "views.category_reorg", name='category_reorg'),
    url(r'^category/move/(?P<category_id>\d+)/', "views.category_move", name='category_move'),

    url(r'^category/(?P<category_id>\d+)/edit/', "views.category_edit", name='category_edit'),
    url(r'^category/(?P<category_id>\d+)/delete/', "views.category_delete", name='category_delete'),
)
