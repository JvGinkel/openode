# -*- coding: utf-8 -*-

import datetime
import pytz
import re
import time
import unicodedata
import urllib

from coffin import template as coffin_template
from django.core import exceptions as django_exceptions
from django.core.urlresolvers import reverse
from django.contrib.humanize.templatetags import humanize
from django.template import defaultfilters
from django.utils.html import strip_tags
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django_countries import countries
from django_countries import settings as countries_settings
from haystack.utils import Highlighter
from sorl.thumbnail.shortcuts import get_thumbnail

from openode import exceptions as openode_exceptions
from openode.conf import settings as openode_settings
from openode.forms import clean_login_url as forms_clean_login_url
from openode.utils import humanize_datetime as _internal_humanize_datetime
from openode.utils import functions, url_utils
from openode.utils.html import absolutize_urls
from openode.utils.slug import slugify
from openode.skins import utils as skin_utils
from openode.models.post import Post

from django.conf import settings as django_settings

################################################################################

register = coffin_template.Library()

################################################################################


class CompleteHighlighter(Highlighter):
    """
        Overwrite of standart haystack Highlighter class.
        This Highlighter render complete text, NOT only chunk with highlighted words.
    """
    # css_class = 'highlight'
    css_class = ''
    html_tag = 'strong'
    max_length = 400
    text_block = ''

    # def to_ascii(self, text):
    #     print text
    #     print unicode(unicodedata.normalize('NFKD', text).encode("ascii", "replace"))
    #     return unicode(unicodedata.normalize('NFKD', text).encode("ascii", "ignore"))
    #     ret = ""
    #     for ch in text:
    #         _ch = unicode(unicodedata.normalize('NFKD', ch).encode("ascii", "ignore"))
    #         if ch and not _ch:
    #             ret += ch
    #         else:
    #             ret += _ch
    #     return ret

    # def find_highlightable_words(self):
    #     # Use a set so we only do this once per unique word.
    #     word_positions = {}
    #     # Pre-compute the length.
    #     end_offset = len(self.text_block)
    #     lower_text_block = self.text_block.lower()

    #     # diacritics free hightlighting only for short texts
    #     highlight_all = True if (end_offset < 5000) else False

    #     if highlight_all:
    #         lower_text_block = self.to_ascii(lower_text_block)

    #     for word in self.query_words:

    #         if highlight_all:
    #             word = self.to_ascii(word)

    #         if not word in word_positions:
    #             word_positions[word] = []

    #         start_offset = 0

    #         while start_offset < end_offset:
    #             next_offset = lower_text_block.find(word, start_offset, end_offset)
    #             # If we get a -1 out of find, it wasn't found. Bomb out and
    #             # start the next word.
    #             if next_offset == -1:
    #                 break

    #             word_positions[word].append(next_offset)
    #             start_offset = next_offset + len(word)

    #     ret = {}
    #     for k, v in word_positions.items():
    #         ret[k] = list(set(v))
    #     print ret
    #     return ret

    # def render_html(self, highlight_locations=None, start_offset=None, end_offset=None):

    #     # Start by chopping the block down to the proper window.
    #     text = self.text_block[start_offset:end_offset]

    #     # Invert highlight_locations to a location -> term list
    #     term_list = []

    #     for term, locations in highlight_locations.items():
    #         term_list += [(loc - start_offset, term) for loc in locations]

    #     loc_to_term = sorted(term_list)

    #     # Prepare the highlight template
    #     if self.css_class:
    #         hl_start = '<%s class="%s">' % (self.html_tag, self.css_class)
    #     else:
    #         hl_start = '<%s>' % (self.html_tag)

    #     hl_end = '</%s>' % self.html_tag

    #     # Copy the part from the start of the string to the first match,
    #     # and there replace the match with a highlighted version.
    #     highlighted_chunk = ""
    #     matched_so_far = 0
    #     prev = 0
    #     prev_str = ""

    #     for cur, cur_str in loc_to_term:
    #         # This can be in a different case than cur_str
    #         actual_term = text[cur:cur + len(cur_str)]

    #         # Handle incorrect highlight_locations by first checking for the term
    #         # if actual_term.lower() == cur_str:
    #         if cur < prev + len(prev_str):
    #             continue
    #         highlighted_chunk += text[prev + len(prev_str):cur] + hl_start + actual_term + hl_end
    #         prev = cur
    #         prev_str = cur_str
    #         # Keep track of how far we've copied so far, for the last step
    #         matched_so_far = cur + len(actual_term)

    #     # Don't forget the chunk after the last term
    #     highlighted_chunk += text[matched_so_far:]

    #     if start_offset > 0:
    #         highlighted_chunk = '...%s' % highlighted_chunk

    #     if end_offset < len(self.text_block):
    #         highlighted_chunk = '%s...' % highlighted_chunk

    #     return highlighted_chunk

    def highlight(self, text_block):
        self.text_block = strip_tags(text_block)
        highlight_locations = self.find_highlightable_words()
        start_offset, end_offset = self.find_window(highlight_locations)

        start_offset = max([0, min([start_offset, start_offset - 10])])

        # self.css_class = ""
        # self.html_tag = ""

        # start_offset = 0
        # end_offset = len(self.text_block)

        return self.render_html(highlight_locations, start_offset, end_offset)

#######################################


@register.filter
def highlight_search_result(text, query, min_highlighted_len=3):
    query = " ".join([
        w
        for w in query.split(" ")
        if len(w) >= min_highlighted_len
    ])

    highlight = CompleteHighlighter(query)
    return highlight.highlight(text)


################################################################################

absolutize_urls = register.filter(absolutize_urls)

TIMEZONE_STR = pytz.timezone(
        django_settings.TIME_ZONE
    ).localize(
        datetime.datetime.now()
    ).strftime('%z')


@register.filter
def add_tz_offset(datetime_object):
    return str(datetime_object) + ' ' + TIMEZONE_STR


@register.filter
def safe_urlquote(text, quote_plus=False):
    if quote_plus:
        return urllib.quote_plus(text.encode('utf8'))
    else:
        return urllib.quote(text.encode('utf8'))


@register.filter
def strip_path(url):
    """removes path part of the url"""
    return url_utils.strip_path(url)


@register.filter
def clean_login_url(url):
    return forms_clean_login_url(url)


@register.filter
def clean_url(url):
    """pass through and quote dangerous characters - clean_url may be used in next parameter"""
    return urllib.quote(url.encode("utf-8"))


@register.filter
def transurl(url):
    """translate url, when appropriate and percent-
    escape it, that's important, othervise it won't match
    the urlconf"""
    try:
        url.decode('ascii')
    except UnicodeError:
        raise ValueError(
            u'string %s is not good for url - must be ascii' % url
        )
    if getattr(django_settings, 'OPENODE_TRANSLATE_URL', False):
        return urllib.quote(_(url).encode('utf-8'))
    return url


@register.filter
def country_display_name(country_code):
    country_dict = dict(countries.COUNTRIES)
    return country_dict[country_code]


@register.filter
def country_flag_url(country_code):
    return countries_settings.FLAG_URL % country_code


@register.filter
def collapse(input):
    input = unicode(input)
    return ' '.join(input.split())


@register.filter
def split(string, separator):
    return string.split(separator)


@register.filter
def get_age(birthday):
    current_time = datetime.datetime(*time.localtime()[0:6])
    year = birthday.year
    month = birthday.month
    day = birthday.day
    diff = current_time - datetime.datetime(year, month, day, 0, 0, 0)
    return diff.days / 365


@register.filter
def media(url):
    """media filter - same as media tag, but
    to be used as a filter in jinja templates
    like so {{'/some/url.gif'|media}}
    """
    if url:
        return skin_utils.get_media_url(url)
    else:
        return ''


@register.filter
def fullmedia(url):
    domain = openode_settings.APP_URL
    #protocol = getattr(settings, "PROTOCOL", "http")
    path = media(url)
    return "%s%s" % (domain, path)

diff_date = register.filter(functions.diff_date)

setup_paginator = register.filter(functions.setup_paginator)

slugify = register.filter(slugify)

register.filter(
            name='intcomma',
            filter_func=humanize.intcomma,
            jinja2_only=True
        )

register.filter(
            name='urlencode',
            filter_func=defaultfilters.urlencode,
            jinja2_only=True
        )

register.filter(
            name='linebreaks',
            filter_func=defaultfilters.linebreaks,
            jinja2_only=True
        )

register.filter(
            name='default_if_none',
            filter_func=defaultfilters.default_if_none,
            jinja2_only=True
        )


def make_template_filter_from_permission_assertion(
                                assertion_name=None,
                                filter_name=None,
                                allowed_exception=None
                            ):
    """a decorator-like function that will create a True/False test from
    permission assertion
    """
    def filter_function(user, post):

        if openode_settings.ALWAYS_SHOW_ALL_UI_FUNCTIONS:
            return True

        if user.is_anonymous():
            return False

        assertion = getattr(user, assertion_name)
        if allowed_exception:
            try:
                assertion(post)
                return True
            except allowed_exception:
                return True
            except django_exceptions.PermissionDenied:
                return False
        else:
            try:
                assertion(post)
                return True
            except django_exceptions.PermissionDenied:
                return False

    register.filter(filter_name, filter_function)
    return filter_function


@register.filter
def can_moderate_user(user, other_user):
    if user.is_authenticated() and user.can_moderate_user(other_user):
        return True
    return False

can_flag_offensive = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_flag_offensive',
                        filter_name='can_flag_offensive',
                        allowed_exception=openode_exceptions.DuplicateCommand
                    )

can_remove_flag_offensive = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_remove_flag_offensive',
                        filter_name='can_remove_flag_offensive',
                    )

can_remove_all_flags_offensive = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_remove_all_flags_offensive',
                        filter_name='can_remove_all_flags_offensive',
                    )

can_post_comment = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_post_comment',
                        filter_name='can_post_comment'
                    )

can_edit_comment = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_edit_comment',
                        filter_name='can_edit_comment'
                    )

can_close_question = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_close_question',
                        filter_name='can_close_question'
                    )

can_delete_comment = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_delete_comment',
                        filter_name='can_delete_comment'
                    )

#this works for questions, answers and comments
can_delete_post = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_delete_post',
                        filter_name='can_delete_post'
                    )

can_reopen_question = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_reopen_question',
                        filter_name='can_reopen_question'
                    )

can_edit_post = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_edit_post',
                        filter_name='can_edit_post'
                    )

can_retag_question = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_retag_question',
                        filter_name='can_retag_question'
                    )

can_accept_best_answer = make_template_filter_from_permission_assertion(
                        assertion_name='assert_can_accept_best_answer',
                        filter_name='can_accept_best_answer'
                    )


def can_see_offensive_flags(user, post):
    """Determines if a User can view offensive flag counts.
    there is no assertion like this User.assert_can...
    so all of the code is here

    user can see flags on own posts
    otherwise enough rep is required
    or being a moderator or administrator

    suspended or blocked users cannot see flags
    """
    if user.is_authenticated():
        if user == post.get_owner():
            return True
        elif user.is_administrator() or user.is_moderator():
            return True
        else:
            return False
    else:
        return False
# Manual Jinja filter registration this leaves can_see_offensive_flags() untouched (unwrapped by decorator),
# which is needed by some tests
register.filter('can_see_offensive_flags', can_see_offensive_flags)


@register.filter
def humanize_counter(number):
    if number == 0:
        return _('no')
    elif number >= 1000:
        number = number / 1000
        s = '%.1f' % number
        if s.endswith('.0'):
            return s[:-2] + 'k'
        else:
            return s + 'k'
    else:
        return str(number)


@register.filter
def absolute_value(number):
    return abs(number)


@register.filter
def get_empty_search_state(unused):
    from openode.search.state_manager import SearchState
    return SearchState.get_empty()


def _humanize_datetime(value):
    """
    For date and time values shows how many seconds, minutes or hours ago
    compared to current timestamp returns representing string.
    """
    if not value:
        return ""

    s = '%d.&nbsp;%d.&nbsp;%d&nbsp;%d:%02d' % (value.day, value.month, value.year, value.hour, value.minute)
    return mark_safe('<span class="timeago" title="%s">%s</span>' % (
        s,
        unicode(_internal_humanize_datetime(value, django_settings.HUMANIZE_DATETIME_LIMIT))
    ))


@register.filter
def humanize_datetime(value):
    return _humanize_datetime(value)


import bleach
@register.filter
def white_strip(value):
    """
    For date and time values shows how many seconds, minutes or hours ago
    compared to current timestamp returns representing string.
    """
    attrs = {
        '*': 'style',
        "img": "src",
        "a": "href",
    }
    tags = ["a", "img", 'p', 'em', 'strong', "ul", "li", "ol"]
    styles = ['color', 'font-weight']
    return bleach.clean(value, tags, attrs, styles, strip=True)


@register.object()
def jinja_thumbnail(file_, geometry_string, **options):
    """
        @return: image thumbnail object
    """
    try:
        img = get_thumbnail(file_, geometry_string, **options)
    except IOError:
        img = None
    return img


@register.filter
def parse_reply_to(html, posts_per_pages, answer, request):
    """
        @return: parse post html text and replace "reply to" meta symbol to regular link
        @param html, html content with replyto symbols
        @param posts_per_pages is dict with position answer (post) on paginator pages (key is post PK, value is page number)
    """
    patt = re.compile(r"replyto:#(?P<pk>\d+)")

    for match in patt.finditer(html):
        try:
            post = Post.objects.get(thread=answer.thread_id, deleted=False, pk=int(match.groupdict()["pk"]))

            page = posts_per_pages.get(post.pk)
            request_page = request.GET.get("page", 0)
            if isinstance(request_page, basestring) and request_page.isdigit():
                request_page = int(request_page)

            page_attr = "?page=%s" % page if (page and (page != request_page)) else ""

            datetime_str = unicode(_internal_humanize_datetime(post.dt_created, django_settings.HUMANIZE_DATETIME_LIMIT))
            author = post.author.screen_name
            link_text = _("Reply to the post by %(author)s &ndash; %(datetime_str)s") % {"datetime_str": datetime_str, "author": author}
            new_string = "<a href='%(anchor)s' class='js-post-preview' data-post_url='%(post_url)s' data-comment_pk='%(pk)s' title='%(datetime_str)s'>%(link_text)s</a>" % {
                "anchor": "%s#post-id-%s" % (page_attr, post.pk),
                "pk": post.pk,
                "post_url": reverse("discussion_answer", args=[post.pk]),
                "link_text": link_text,
                "datetime_str": datetime_str
            }
        except Post.DoesNotExist:
            new_string = _("Quoted post was deleted or does not exist in this discussion.")
        new_string = u'<div class="replyto"><span>%s</span></div>' % new_string

        html = html.replace(match.group(), new_string)

    return html
