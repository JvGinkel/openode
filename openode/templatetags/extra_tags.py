# -*- coding: utf-8 -*-

import math
from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse

from openode.utils import functions
from openode.utils.slug import slugify
from openode.skins.loaders import get_template
from openode.conf import settings as openode_settings


register = template.Library()

GRAVATAR_TEMPLATE = (
     '<a style="text-decoration:none" '
     'href="%(user_profile_url)s"><img class="gravatar" '
     'width="%(size)s" height="%(size)s" '
     'src="https://www.gravatar.com/avatar/%(gravatar_hash)s'
     '?s=%(size)s&amp;d=%(gravatar_type)s&amp;r=PG" '
     'title="%(username)s" '
     'alt="%(alt_text)s" /></a>'
     )


@register.simple_tag
def gravatar(user, size):
    """
    Creates an ``<img>`` for a user's Gravatar with a given size.

    This tag can accept a User object, or a dict containing the
    appropriate values.
    """
    #todo: rewrite using get_from_dict_or_object
    user_id = functions.get_from_dict_or_object(user, 'id')
    slug = slugify(user.username)
    user_profile_url = reverse(
                        'user_profile',
                        kwargs={'id': user_id, 'slug': slug}
                    )
    #safe_username = template.defaultfilters.urlencode(username)
    return mark_safe(GRAVATAR_TEMPLATE % {
        'user_profile_url': user_profile_url,
        'size': size,
        'gravatar_hash': functions.get_from_dict_or_object(user, 'gravatar'),
        'gravatar_type': openode_settings.GRAVATAR_TYPE,
        'alt_text': _('%(username)s gravatar image') % {'username': user.username},
        'username': functions.get_from_dict_or_object(user, 'username'),
    })


@register.filter
def key_value(dict, key):
    if dict is None:
        return ""
    return dict.get(key)

@register.filter
def trans_perm_var(var):
    return _("perm-%s" % var)

@register.filter
def yes_no_none_human(val):
    if val is True:
        return "Yes"
    elif val is False:
        return "No"
    else:
        return "-"


@register.simple_tag
def get_tag_font_size(tags):
    max_tag = 0
    for tag in tags:
        if tag.used_count > max_tag:
            max_tag = tag.used_count

    min_tag = max_tag
    for tag in tags:
        if tag.used_count < min_tag:
            min_tag = tag.used_count

    font_size = {}
    for tag in tags:
        font_size[tag.name] = tag_font_size(max_tag, min_tag, tag.used_count)

    return font_size


@register.simple_tag
def tag_font_size(max_size, min_size, current_size):
    """
    do a logarithmic mapping calcuation for a proper size for tagging cloud
    Algorithm from http://blogs.dekoh.com/dev/2007/10/29/choosing-a-good-
    font-size-variation-algorithm-for-your-tag-cloud/
    """
    MAX_FONTSIZE = 10
    MIN_FONTSIZE = 1

    #avoid invalid calculation
    if current_size == 0:
        current_size = 1
    try:
        weight = (math.log10(current_size) - math.log10(min_size)) / (math.log10(max_size) - math.log10(min_size))
    except Exception:
        weight = 0

    return int(MIN_FONTSIZE + round((MAX_FONTSIZE - MIN_FONTSIZE) * weight))


def test(context, test):
    return test + "asdasdasd as das d"
register.simple_tag(takes_context=True)(test)

class IncludeJinja(template.Node):
    """http://www.mellowmorning.com/2010/08/24/"""
    def __init__(self, filename, request_var):
        self.filename = filename
        self.request_var = template.Variable(request_var)

    def render(self, context):
        request = self.request_var.resolve(context)
        jinja_template = get_template(self.filename, request)
        return jinja_template.render(context)


@register.tag
def include_jinja(parser, token):
    bits = token.contents.split()

    #Check if a filename was given
    if len(bits) != 3:
        error_message = '%r tag requires the name of the ' + \
                        'template and the request variable'
        raise template.TemplateSyntaxError(error_message % bits[0])
    filename = bits[1]
    request_var = bits[2]

    #Remove quotes or raise error
    if filename[0] in ('"', "'") and filename[-1] == filename[0]:
        filename = filename[1:-1]
    else:
        raise template.TemplateSyntaxError('file name must be quoted')

    return IncludeJinja(filename, request_var)
