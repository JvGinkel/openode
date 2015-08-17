# -*- coding: utf-8 -*-

from django.db.models import Q

from openode import const
from openode.models.thread import Thread
from openode.skins.loaders import render_into_skin

#######################################

PER_PAGE = 10
check_perm = lambda thread, user: user.has_openode_perm('%s_read' % thread.thread_type, thread)

################################################################################


def get_live_data(user=None, start=0, end=PER_PAGE, node=None):
    threads = Thread.objects.public()

    if node:
        threads = threads.filter(node__in=node.get_descendants(include_self=True))

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

    threads = threads.order_by("-dt_changed")[start:end]
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
