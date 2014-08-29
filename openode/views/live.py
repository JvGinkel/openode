# -*- coding: utf-8 -*-
"""
:synopsis: views "read-only" for main textual content

By main textual content is meant - text of Questions, Answers and Comments.
The "read-only" requirement here is not 100% strict, as for example "question" view does
allow adding new comments via Ajax form post.
"""

# import datetime
# import operator
# import os

# from django.conf import settings
# from django.views.decorators import csrf
# from django.core.exceptions import ObjectDoesNotExist
# from django.core.paginator import Paginator, EmptyPage
# from django.core.urlresolvers import reverse
# from django.contrib.humanize.templatetags import humanize
# from django.contrib.auth.models import User
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    Http404,
    HttpResponseNotAllowed,
    QueryDict,
    )
from django.db.models import Q
# from django.shortcuts import get_object_or_404
# from django.template import Context
# from django.utils import simplejson, translation
# from django.utils.html import escape
from django.utils.translation import ugettext as _, ungettext
# from jinja2 import Environment, FileSystemLoader

from openode import conf, const, models, schedules
# from openode.conf import settings as openode_settings
# from openode.document.forms import DownloadZipForm
# from openode.models import StaticPage
# from openode.models.actuality import Actuality
# from openode.models.node import Node
# from openode.models.post import Post
# from openode.models.tag import Tag
from openode.models.thread import ThreadCategory, Thread
# from openode.utils import JsonResponse
# from openode.utils import functions
# from openode.utils.decorators import anonymous_forbidden, ajax_only, get_only
# from openode.utils.diff import textDiff as htmldiff
# from openode.utils.html import bleach_html
# from openode.utils.http import render_forbidden
# from openode.views.node import node_ask_to_join
# from openode.search.state_manager import SearchState
from openode.skins.loaders import render_into_skin, get_template  # jinja2 template loading enviroment
# from openode.templatetags import extra_tags
# from openode.views.thread import thread as thread_detail_view

#######################################

PER_PAGE = 10
check_perm = lambda thread, user: user.has_openode_perm('%s_read' % thread.thread_type, thread)

################################################################################


def get_live_data(user=None, start=0, end=PER_PAGE, node=None):
    threads = Thread.objects.all()

    if node:
        threads = threads.filter(node=node)

    if user.is_authenticated():
        threads = threads.filter(
            Q(node__visibility__in=[
                const.NODE_VISIBILITY_PUBLIC,
                const.NODE_VISIBILITY_REGISTRED_USERS
            ])
            | Q(
                node__in=user.nodes.all(),
                node__visibility__in=[
                    const.NODE_VISIBILITY_SEMIPRIVATE,
                    const.NODE_VISIBILITY_PRIVATE
                ]
            )
        )

    else:
        threads = threads.filter(node__visibility=const.NODE_VISIBILITY_PUBLIC)

    threads = threads.order_by("-dt_created")[start:end]
    return threads

################################################################################


def live(request):
    """
        live stream view
    """

    try:
        page_no = int(request.GET.get("page", 1))
    except ValueError:
        page_no = 1

    end = PER_PAGE * page_no
    start = end - PER_PAGE

    threads = get_live_data(request.user, start, end)

    context_dict = {
        "threads": threads,
        "check_perm": check_perm,
        "page": page_no
    }
    return render_into_skin('live/live.html', context_dict, request)
