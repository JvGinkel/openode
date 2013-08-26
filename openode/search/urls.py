# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *

from openode.search.views import SearchView, AutocompleteSearchView

urlpatterns = patterns('',
    url(r'^tags\:(?P<tags>([\d+|\+]+)?\d+)/$', SearchView(), name='search'),
    url(r'^$', SearchView(), name='search'),
    url(r'^autocomplete/$', AutocompleteSearchView(), name='autocomplete'),
    # url(r'^page/$', "openode.search.views.autocomplete_page", name='autocomplete_page'),
)
