"""
:synopsis: remaining "secondary" views for openode

This module contains a collection of views displaying all sorts of secondary and mostly static content.
"""
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.template import RequestContext, Template
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.views import static
from django.views.decorators import csrf
from django.db.models import Max, Count
from openode import skins
from openode.conf import settings as openode_settings
from openode.forms import FeedbackForm
from openode.utils.url_utils import get_login_url
from openode.utils.forms import get_next_url
from openode.mail import mail_moderators
from openode.models import User, Tag
from openode.skins.loaders import get_template, render_into_skin, render_text_into_skin
from openode.utils.decorators import admins_only
from openode.utils.forms import get_next_url
from openode.utils import functions

def generic_view(request, template = None, page_class = None):
    """this may be not necessary, since it is just a rewrite of render_into_skin"""
    if request is None:  # a plug for strange import errors in django startup
        return render_to_response('django_error.html')
    return render_into_skin(template, {'page_class': page_class}, request)

def config_variable(request, variable_name = None, mimetype = None):
    """Print value from the configuration settings
    as response content. All parameters are required.
    """
    #todo add http header-based caching here!!!
    output = getattr(openode_settings, variable_name, '')
    return HttpResponse(output, mimetype = mimetype)

# def about(request, template='about.html'):
#     title = _('About %(site)s') % {'site': openode_settings.APP_SHORT_NAME}
#     data = {
#         'title': title,
#         'page_class': 'meta',
#         'content': openode_settings.FORUM_ABOUT
#     }
#     return render_into_skin('static_page.html', data, request)

def page_not_found(request, template='404.html'):
    return generic_view(request, template)

def server_error(request, template='500.html'):
    return generic_view(request, template)

# def help(request):
#     data = {
#         'app_name': openode_settings.APP_SHORT_NAME,
#         'page_class': 'meta'
#     }
#     return render_into_skin('help.html', data, request)

@csrf.csrf_protect
def feedback(request):
    data = {'page_class': 'meta'}
    form = None

    if openode_settings.ALLOW_ANONYMOUS_FEEDBACK is False:
        if request.user.is_anonymous():
            message = _('Please sign in or register to send your feedback')
            request.user.message_set.create(message=message)
            redirect_url = get_login_url() + '?next=' + request.path
            return HttpResponseRedirect(redirect_url)

    if request.method == "POST":
        form = FeedbackForm(
            is_auth=request.user.is_authenticated(),
            data=request.POST
        )
        if form.is_valid():
            if not request.user.is_authenticated():
                data['email'] = form.cleaned_data.get('email',None)
            data['message'] = form.cleaned_data['message']
            data['name'] = form.cleaned_data.get('name',None)
            template = get_template('email/feedback_email.txt', request)
            message = template.render(RequestContext(request, data))
            mail_moderators(_('Q&A forum feedback'), message)
            msg = _('Thanks for the feedback!')
            request.user.message_set.create(message=msg)
            return HttpResponseRedirect(get_next_url(request))
    else:
        form = FeedbackForm(is_auth = request.user.is_authenticated(),
                            initial={'next':get_next_url(request)})

    data['form'] = form
    return render_into_skin('feedback.html', data, request)
feedback.CANCEL_MESSAGE=_('We look forward to hearing your feedback! Please, give it next time :)')

# def privacy(request):
#     data = {
#         'title': _('Privacy policy'),
#         'page_class': 'meta',
#         'content': openode_settings.FORUM_PRIVACY
#     }
#     return render_into_skin('static_page.html', data, request)


@admins_only
def list_suggested_tags(request):
    """moderators and administrators can list tags that are
    in the moderation queue, apply suggested tag to questions
    or cancel the moderation reuest."""
    if openode_settings.ENABLE_TAG_MODERATION == False:
        raise Http404
    tags = Tag.objects.filter(status = Tag.STATUS_SUGGESTED)
    tags = tags.order_by('-used_count', 'name')
    #paginate moderated tags
    paginator = Paginator(tags, 20)

    page_no = request.GET.get('page', '1')

    try:
        page = paginator.page(page_no)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)

    paginator_context = functions.setup_paginator({
        'is_paginated' : True,
        'pages': paginator.num_pages,
        'page': page_no,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'previous': page.previous_page_number(),
        'next': page.next_page_number(),
        'base_url' : request.path
    })

    data = {
        'tags': page.object_list,
        'active_tab': 'tags',
        'tab_id': 'suggested',
        'page_class': 'moderate-tags-page',
        'page_title': _('Suggested tags'),
        'paginator_context' : paginator_context,
    }
    return render_into_skin('list_suggested_tags.html', data, request)
