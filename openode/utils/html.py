"""Utilities for working with HTML."""
import html5lib
from html5lib import sanitizer, serializer, tokenizer, treebuilders, treewalkers
import bleach

import re
import htmlentitydefs
from urlparse import urlparse
from django.core.urlresolvers import reverse
# from django.utils.html import escape
from openode.conf import settings as openode_settings

from django.conf import settings


class HTMLSanitizerMixin(sanitizer.HTMLSanitizerMixin):
    acceptable_elements = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
        'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
        'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
        'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
        'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
        'tr', 'tt', 'u', 'ul', 'var', 'object', 'param')

    acceptable_attributes = ('abbr', 'align', 'alt', 'axis', 'border',
        'cellpadding', 'cellspacing', 'char', 'charoff', 'charset', 'cite',
        'cols', 'colspan', 'data', 'datetime', 'dir', 'frame', 'headers', 'height',
        'href', 'hreflang', 'hspace', 'lang', 'longdesc', 'name', 'nohref',
        'noshade', 'nowrap', 'rel', 'rev', 'rows', 'rowspan', 'rules', 'scope',
        'span', 'src', 'start', 'summary', 'title', 'type', 'valign', 'vspace',
        'width')

    allowed_elements = acceptable_elements
    allowed_attributes = acceptable_attributes
    allowed_css_properties = ()
    allowed_css_keywords = ()
    allowed_svg_properties = ()


class HTMLSanitizer(tokenizer.HTMLTokenizer, HTMLSanitizerMixin):
    def __init__(self, stream, encoding=None, parseMeta=True, useChardet=True,
                 lowercaseElementName=True, lowercaseAttrName=True, **kwargs):
        tokenizer.HTMLTokenizer.__init__(self, stream, encoding, parseMeta,
                                         useChardet, lowercaseElementName,
                                         lowercaseAttrName, **kwargs)

    def __iter__(self):
        for token in tokenizer.HTMLTokenizer.__iter__(self):
            token = self.sanitize_token(token)
            if token:
                yield token


def absolutize_urls(html):
    """turns relative urls in <img> and <a> tags to absolute,
    starting with the ``openode_settings.APP_URL``"""
    #temporal fix for bad regex with wysiwyg editor
    url_re1 = re.compile(r'(?P<prefix><img[^<]+src=)"(?P<url>/[^"]+)"', re.I)
    url_re2 = re.compile(r"(?P<prefix><img[^<]+src=)'(?P<url>/[^']+)'", re.I)
    url_re3 = re.compile(r'(?P<prefix><a[^<]+href=)"(?P<url>/[^"]+)"', re.I)
    url_re4 = re.compile(r"(?P<prefix><a[^<]+href=)'(?P<url>/[^']+)'", re.I)
    img_replacement = '\g<prefix>"%s/\g<url>" style="max-width:500px;"' % openode_settings.APP_URL
    replacement = '\g<prefix>"%s\g<url>"' % openode_settings.APP_URL
    html = url_re1.sub(img_replacement, html)
    html = url_re2.sub(img_replacement, html)
    html = url_re3.sub(replacement, html)
    #temporal fix for bad regex with wysiwyg editor
    return url_re4.sub(replacement, html).replace('%s//' % openode_settings.APP_URL,
                                                  '%s/' % openode_settings.APP_URL)


#######################################

def bleach_html(value):
    """
        selected filtering html tags
    """
    return bleach.clean(
        value,
        settings.HTML_CLEANER_TAGS,
        settings.HTML_CLEANER_ATTRS,
        settings.HTML_CLEANER_STYLES,
        strip=True
    )

# DEPRECATED
# def sanitize_html(html):

#     return bleach_html(html)

#     # """Sanitizes an HTML fragment."""
#     # p = html5lib.HTMLParser(tokenizer=HTMLSanitizer,
#     #                         tree=treebuilders.getTreeBuilder("dom"))
#     # dom_tree = p.parseFragment(html)
#     # walker = treewalkers.getTreeWalker("dom")
#     # stream = walker(dom_tree)
#     # s = serializer.HTMLSerializer(omit_optional_tags=False,
#     #                               quote_attr_values=True)
#     # output_generator = s.serialize(stream)
#     # return u''.join(output_generator)

# #######################################


def site_url(url):
    from openode.conf import settings
    base_url = urlparse(settings.APP_URL)
    return base_url.scheme + '://' + base_url.netloc + url


def site_link(url_name, title):
    """returns html for the link to the given url
    todo: may be improved to process url parameters, keyword
    and other arguments
    """
    from openode.conf import settings
    base_url = urlparse(settings.APP_URL)
    url = site_url(reverse(url_name))
    return '<a href="%s">%s</a>' % (url, title)


def unescape(text):
    """source: http://effbot.org/zone/re-sub.htm#unescape-html
    Removes HTML or XML character references and entities from a text string.
    @param text The HTML (or XML) source text.
    @return The plain text, as a Unicode string, if necessary.
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text  # leave as is
    return re.sub("&#?\w+;", fixup, text)
