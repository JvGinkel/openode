# -*- coding: utf-8 -*-
import csv
import codecs
from datetime import datetime, timedelta
import hashlib
import random
from urlparse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.template.defaultfilters import slugify
from django.utils import simplejson
from django.utils.functional import update_wrapper
from django.utils.hashcompat import md5_constructor
from django.utils.html import strip_tags
from django.utils.http import urlquote
from django.utils.translation import ugettext_lazy as _

import unidecode


def count_visit(request, thread, main_post):
    #count visits
    #import ipdb; ipdb.set_trace()
    from openode.utils import functions
    if functions.not_a_robot_request(request):
        #todo: split this out into a subroutine
        #todo: merge view counts per user and per session

        #1) view count per session
        update_view_count = False
        if 'question_view_times' not in request.session:
            request.session['question_view_times'] = {}

        last_seen = request.session['question_view_times'].get(main_post.id, None)

        if thread.last_activity_by_id != request.user.id:
            if last_seen:
                if last_seen < thread.last_activity_at:
                    update_view_count = True
            else:
                update_view_count = True

        request.session['question_view_times'][main_post.id] = datetime.now()
        request.session.modified = True

        #2) run the slower jobs in a celery task
        from openode import tasks

        if request.user.is_authenticated():
            tasks.record_thread_visit.delay(
                thread=thread,
                user=request.user,
                update_view_count=update_view_count
            )


class GroupIterator(object):
    """
    Instance of GroupIterator can be iterated over by groups of 'objects', each of size 'group_size'
    """
    def __init__(self, objects, group_size):
        self.objects = list(objects)
        self.group_size = group_size

    def __nonzero__(self):
        return bool(self.objects)

    def __iter__(self):
        pos = 0
        size = len(self.objects)
        group_size = self.group_size
        while pos < size:
            yield self.objects[pos:pos + group_size]
            pos += group_size


class FieldStack(object):
    """
    Wrapper for group of fields in form
    """
    def __init__(self, form, *args, **kwargs):
        self.form, self.args, self.kwargs = form, args, kwargs

    def __nonzero__(self):
        if self.args:
            return bool(list(self))
        else:
            return False

    def __iter__(self):
        from django.forms.forms import BoundField
        for field in self.args:
            if field in self.form.fields:
                yield BoundField(self.form, self.form.fields[field], field)

    def __getattr__(self, name):
        try:
            return self.kwargs[name]
        except KeyError, e:
            raise AttributeError(e)

    def copy(self, title=None):
        kwargs = self.kwargs.copy()
        if not title is None:
            kwargs['title'] = title
        return FieldStack(*self.args, **kwargs)


class FieldStackLazy(object):
    """
    Wrapper for group of fields in form - lazy variant
    """
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    def __nonzero__(self):
        return bool(self.args)

    def __get__(self, form, objtype=None):
        return FieldStack(form, *self.args, **self.kwargs)


class PdfResponse(HttpResponse):
    """ PDF response

    """
    def __init__(self, content, status=None, mimetype=None, filename=None):
        super(PdfResponse, self).__init__(content=content, mimetype=mimetype or 'application/pdf', status=status)
        if filename:
            self['Content-Disposition'] = 'attachment; filename=%s' % filename
        self['Cache-Control'] = 'no-cache'
        self['Pragma'] = 'no-cache'


class PngResponse(HttpResponse):
    """ PNG response

    """
    def __init__(self, content, status=None, mimetype=None, filename=None):
        super(PngResponse, self).__init__(content=content, mimetype=mimetype or 'image/png', status=status)


class JsonResponse(HttpResponse):
    """ JSON response

    """
    def __init__(self, content, status=None, mimetype=None):
        if not isinstance(content, basestring):
            content = simplejson.dumps(content)
        super(JsonResponse, self).__init__(content=content, mimetype=mimetype or 'application/json', status=status)
        self['Cache-Control'] = 'no-cache'
        self['Pragma'] = 'no-cache'


def json_view(view):
    """ Decorator, that ensures return value of wrapped function to be a JSON value

    """
    def wrapper(*args, **kwargs):
        retval = view(*args, **kwargs)
        if isinstance(retval, JsonResponse):
            return retval
        else:
            return JsonResponse(retval)
    return update_wrapper(wrapper, view)


def get_dict_by_attr(records, attr_name, dict_class=dict):
    """ Vraci vstupni pole zaznamu sdruzene do slovniku podle hodnot atributu 'attr_name'

    """
    retval = dict_class()
    for record in records:
        if isinstance(attr_name, (list, tuple)):
            attr_val = tuple([getattr(record, a) for a in attr_name])
        else:
            attr_val = getattr(record, attr_name)
        if attr_val in retval:
            retval[attr_val].append(record)
        else:
            retval[attr_val] = [record]
    return retval


def get_dict_by_unique_attr(records, attr_name, dict_class=dict):
    """ Vraci vstupni pole zaznamu sdruzene do slovniku podle hodnot atributu 'attr_name', ktery mu si byt unikatni

    """
    retval = dict_class()
    for record in records:
        if isinstance(attr_name, (list, tuple)):
            attr_val = tuple([getattr(record, a) for a in attr_name])
        else:
            attr_val = getattr(record, attr_name)
        retval[attr_val] = record
    return retval


def get_random_hash(seed=u''):
    """
    Generates random hash using current microseconds and random seed
    """
    return hashlib.md5('%s.%s.%s' % (random.random(), datetime.now().microsecond, seed)).hexdigest()


SESSION_USER_DATA_KEY = 'user_settings'


def store_user_setting(request, name, val):
    """ Store client-dependent data in session

    """
    data_dict = request.session.get(SESSION_USER_DATA_KEY, {})
    data_dict[name] = val
    request.session[SESSION_USER_DATA_KEY] = data_dict


def load_user_setting(request, name, default=u''):
    """ Load client-dependent data from session

    """
    return request.session.get(SESSION_USER_DATA_KEY, {}).get(name, default)


################################################################################

def any_of_attrs_changed(obj1, obj2, attrs):
    """
    Returns True, if any of given attrs of obj1 does not equal to its counterpart of obj2
    """
    for a in attrs:
        if not (getattr(obj1, a) == getattr(obj2, a)):
            return True
    return False

################################################################################


def attr_changed(obj1, obj2, attr):
    """
    Returns True, if attr of obj1 does not equal to attr of obj2
    """
    return not (getattr(obj1, attr) == getattr(obj2, attr))


################################################################################

def sanitize_file_name(original_name):
    """
        Remove non-alphanumeric characters from original_name and replace UTF-8 characters with their ASCII equivalent.
        Lowercase final name.

        @return: sanitized file name
            e.g.: ščřžýáí_3456ĚŠČŘ 34%^&.PDF => scrzyai-3456escr-34.pdf
    """
    file_name = slugify(utf_to_ascii(original_name))
    crumb = original_name.split(".")
    ext = crumb[-1]
    name = crumb[:-1]
    if name and ext:
        file_name = "%s.%s" % (slugify("_".join(name)), ext)
        file_name = file_name.lower()
    return file_name

################################################################################


def compose(func_1, func_2, unpack=False):
    """
    compose(func_1, func_2, unpack=False) -> function

    The function returned by compose is a composition of func_1 and func_2.
    That is, compose(func_1, func_2)(5) == func_1(func_2(5))
    """
    if not callable(func_1):
        raise TypeError("First argument to compose must be callable")
    if not callable(func_2):
        raise TypeError("Second argument to compose must be callable")

    def composition(*args, **kwargs):
        return func_1(func_2(*args, **kwargs))

    return composition

################################################################################


def invalidate_template_cache(fragment_name, *variables):
    """
    Delete cache of template fragment cached by templatetag
    """
    args = md5_constructor(u':'.join([urlquote(var) for var in variables]))
    cache_key = 'template.cache.%s.%s' % (fragment_name, args.hexdigest())
    cache.delete(cache_key)

################################################################################


def timedelta_total_seconds(td):
    """
    Util function for supplying method total_seconds() of timedelta object prior to Python2.7.
    """
    if hasattr(td, 'total_seconds'):
        return td.total_seconds()
    else:
        return td.days * 3600 + td.seconds + td.microseconds / 1e6


def merge_classes(attrs1, attrs2):
    classes1 = attrs1.get("class", "").split(" ")
    classes2 = attrs2.get("class", "").split(" ")
    return " ".join(set(classes1).union(classes2))


def dictfetchall(cursor):
    """
    Returns all rows from a cursor as a dict
    """
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def match_dict(new_list, old_list, match_key):
    """
    Obohacuje new_list slovník o data v old_listu podle nějakého
    klíče (match_key - str).
    """
    old = dict((v[match_key], v) for v in old_list)
    for d in new_list:
        if d[match_key] in old:
            d.update(old[d[match_key]])

    return new_list


def get_progress_bar_percentage(respondents_count, target_responses):
    """
    Procento splnění požadovaných dotazníků

    result = APR / PPR * 100
    """
    if target_responses:
        progress_percentage = (respondents_count / float(target_responses)) * 100

        # Extreme precautions
        if progress_percentage > 100:
            progress_percentage = 100
        elif progress_percentage < 0:
            progress_percentage = 0
    else:
        progress_percentage = 0

    return int(progress_percentage)


def get_referer_redirect_url(request, redir_url):
    """
    Validuje referer URL podle defaultně stanovené redir_url. Pokud se
    referer shoduje s defaultně nastaveným redir_url, tak k redir_url přidá
    GET parametry z referera.

    Slouží zejména k redirectování při mazání a bezp. ověření, že redirect
    přijde vždy na redir_url.

    @params:
        redir_urls   - reverse('survey:index'), <str>

    @returns:
        redir_url, <str>

    """
    referer = request.META.get('HTTP_REFERER')

    if referer:
        referer = urlparse(referer)
        if referer.path == redir_url and referer.query:
            redir_url = '%s?%s' % (redir_url, referer.query)

    return redir_url


def utf_to_ascii(inputStr, mode='ignore'):
    return unidecode.unidecode(inputStr).encode("ascii", mode)


def render_forbidden(request, template='403.html', context={}):
    response = render(request, template, context)
    response.status_code = HttpResponseForbidden.status_code
    return response


def get_ct_for_model(model):
    """
    Zkratka pro ziskani content type instance pro dany model.
    """
    return ContentType.objects.get_for_model(model)


def transposed(lists):
    if not lists: return []
    return map(lambda *row: list(row), *lists)


def get_mimetype(file_data):
    from commands import getoutput
    try:
        cmd = 'file -i %s' % file_data
        output = getoutput('file -i %s' % file_data)
        return output.split()[1].replace(';', '')
    except Exception, e:
        return u'application/octet-stream'


def parse_attr(obj, attr, sep='__'):
    attrs = attr.split(sep)
    for attr_ in attrs:
        if attr_ != '':
            try:
                obj = getattr(obj, attr_)
            except:
                return None
    return obj


class UTF8Recoder(object):
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return strip_tags(self.reader.next().encode("utf-8")).encode("utf-8")


class CSVUnicodeReader(object):
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self


def humanize_datetime(value, limit):
    """
    For date and time values shows how many seconds, minutes or hours ago
    compared to current timestamp returns representing string.
    """

    now = datetime.now()
    delta = now - value
    if delta < timedelta(seconds=limit) and delta.total_seconds < 48*3600:
        if (now.date() - value.date()).days == 1:
            return _('yesterday %(hours)d:%(minutes)02d') % {'hours': value.hour, 'minutes': value.minute}
        elif delta.total_seconds >= 2*3600:
            return _('%(hours)d hours ago') % {'hours': delta.total_seconds / 3600}
        elif delta.total_seconds >= 3600:
            return _('an hour ago')
        elif delta.total_seconds >= 2*60:
            return _('%(minutes)d minutes ago') % {'minutes': delta.total_seconds / 60}
        elif delta.total_seconds >= 60:
            return _('1 minute ago')
        elif delta.total_seconds < 60:
            return _('less then minute ago')
    return '%d.&nbsp;%d.&nbsp;%d&nbsp;%d:%02d' % (value.day, value.month, value.year, value.hour, value.minute)
