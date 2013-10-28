# -*- coding: utf-8 -*-

from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404


from openode.conf import settings as openode_settings
from openode.models.tag import Tag
from openode.models.thread import Thread
from openode.search.state_manager import SearchState
from openode.skins.loaders import render_into_skin
from openode.templatetags import extra_tags
from openode.utils.functions import setup_paginator


DEFAULT_PAGE_SIZE = 20


def tag_list(request):  # view showing a listing of available tags - plain list

    tag_list_type = openode_settings.TAG_LIST_FORMAT

    if tag_list_type == 'list':

        stag = ""
        sortby = request.GET.get('sort', 'used')
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        stag = request.GET.get("query", "").strip()
        if stag != '':
            objects_list = Paginator(
                Tag.objects.valid_tags().filter(deleted=False, name__icontains=stag).exclude(used_count=0),
                DEFAULT_PAGE_SIZE
            )
        else:
            if sortby == "name":
                objects_list = Paginator(Tag.objects.valid_tags().filter(deleted=False).exclude(used_count=0).order_by("name"), DEFAULT_PAGE_SIZE)
            else:
                objects_list = Paginator(Tag.objects.valid_tags().filter(deleted=False).exclude(used_count=0).order_by("-used_count"), DEFAULT_PAGE_SIZE)

        try:
            tags = objects_list.page(page)
        except (EmptyPage, InvalidPage):
            tags = objects_list.page(objects_list.num_pages)

        paginator_data = {
            'is_paginated': bool(objects_list.count > DEFAULT_PAGE_SIZE),
            'pages': objects_list.num_pages,
            'page': page,
            'has_previous': tags.has_previous(),
            'has_next': tags.has_next(),
            'previous': tags.previous_page_number(),
            'next': tags.next_page_number(),
            'base_url': reverse('tags') + '?sort=%s&amp;' % sortby
        }
        paginator_context = setup_paginator(paginator_data)
        data = {
            'active_tab': 'tags',
            'page_class': 'tags-page',
            'tags': tags,
            'tag_list_type': tag_list_type,
            'stag': stag,
            'tab_id': sortby,
            'keywords': stag,
            'paginator_context': paginator_context,
        }

    else:

        stag = ""
        sortby = request.GET.get('sort', 'name')

        if request.method == "GET":
            stag = request.GET.get("query", "").strip()
            if stag != '':
                tags = Tag.objects.filter(deleted=False, name__icontains=stag).exclude(used_count=0)
            else:
                if sortby == "name":
                    tags = Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("name")
                else:
                    tags = Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("-used_count")

        font_size = extra_tags.get_tag_font_size(tags)

        data = {
            'active_tab': 'tags',
            'page_class': 'tags-page',
            'tags': tags,
            'tag_list_type': tag_list_type,
            'font_size': font_size,
            'stag': stag,
            'tab_id': sortby,
            'keywords': stag,
            'search_state': SearchState(*[None for x in range(7)])
        }

    return render_into_skin('tag_list.html', data, request)


def tag_detail(request, tag_id):
    tag = get_object_or_404(Tag, pk=tag_id)

    threads = Thread.objects.filter(tags__in=[tag])

    data = {
        'tag': tag,
        'threads': threads
    }

    return render_into_skin('tag_detail.html', data, request)
