# -*- coding: utf-8 -*-
import copy
import re

from django.db import models
from django.db.models import TextField
from django.utils.encoding import smart_unicode

from openode.forms.fields import WysiwygFormField
from openode.utils import utf_to_ascii, parse_attr


class WysiwygField(TextField):
    """
    A large string field for HTML content.
    """

    def formfield(self, **kwargs):
        defaults = {
            'form_class': WysiwygFormField,
        }
        defaults.update(kwargs)
        return super(WysiwygField, self).formfield(**defaults)


class SlugField(models.Field):

    def createSlug(self, model_instance, querySet, slug):
        slugField = self.name

        if not(slug == '' and self.null):
            if slug != '':
                if len(slug) > 1 and slug[0] == self.slug_replacer:
                    if slug[0] == self.slug_replacer:
                        slug = slug[1:]
                if len(slug) == 1 and slug[0] == self.slug_replacer:
                    slug = ''
                if len(slug) > 1 and slug[-1] == self.slug_replacer:
                    slug = slug[0:-1]
            if slug == '':
                slug = '_'

            if model_instance._get_pk_val():
                querySet = apply(querySet.exclude, [], {model_instance._meta.pk.attname: model_instance._get_pk_val()})

            #single search
            if self.slug_mode == 'single':
                #pomocna promenna
                odd = 1
                #
                querySet = apply(querySet.filter, [], {slugField + '__startswith': slug})

                slugDict = {}
                a = list(querySet)
                for object in a:
                    slugDict[getattr(object, slugField)] = object

                testSlug = slug

                while testSlug in slugDict:
                    odd += 1
                    testSlug = slug + self.slug_separator + str(odd)

                return testSlug

            elif self.slug_mode == 'multiple':
                #pomocna promenna
                odd = 1
                #
                oldQuerySet = querySet

                querySet = apply(querySet.filter, [], {slugField: slug})
                while querySet.count() != 0:
                    odd += 1
                    testSlug = slug + self.slug_separator + smart_unicode(odd)
                    querySet = apply(oldQuerySet.filter, [], {slugField: testSlug})

                slug = slug + (odd != 1) * (self.slug_separator + str(odd))
                return slug

            elif self.slug_mode == 'binary':

                #pomocna promenna
                odd = 1
                #
                interval = self.slug_mode_settings.get('interval', 20)

                start = 0
                oldQuerySet = querySet

                querySet = apply(querySet.filter, [], {slugField: slug})

                while querySet.count() != 0:
                    start = odd
                    odd += interval
                    testSlug = slug + (odd != 1) * (self.slug_separator + str(odd))
                    querySet = apply(oldQuerySet.filter, [], {slugField: testSlug})

                end = odd
                odd = max(((end - start) / 2) + start, start + 1)

                while end != odd:
                    testSlug = slug + (odd != 1) * (self.slug_separator + str(odd))

                    querySet = apply(oldQuerySet.filter, [], {slugField: testSlug})
                    if querySet.count() == 0:
                        end = odd
                    else:
                        start = odd
                    odd = max(((end - start) / 2) + start, start + 1)

                slug = slug + (end != 1) * (self.slug_separator + str(end))

                return slug
        else:
            return slug

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 50)
        if 'db_index' not in kwargs:
            kwargs['db_index'] = True

        #meine liebe kwargs
        self.slug_unique = kwargs.pop('slug_unique', False)
        self.slug_unique_together = kwargs.pop('slug_unique_together', [])

        self.slug_test = kwargs.pop('slug_test', {})

        self.slug_from = kwargs.pop('slug_from', [])
        self.slug_filter = kwargs.pop('slug_filter', {})
        self.slug_exclude = kwargs.pop('slug_exclude', {})
        self.slug_replacer = kwargs.pop('slug_replacer', '-')
        self.slug_separator = kwargs.pop('slug_separator', '-')

        self.slug_not_from = kwargs.pop('slug_not_from', self.slug_from)
        self.slug_not_filter = kwargs.pop('slug_not_filter', self.slug_filter)
        self.slug_not_exclude = kwargs.pop('slug_not_exclude', self.slug_exclude)
        self.slug_not_replacer = kwargs.pop('slug_not_replacer', self.slug_replacer)
        self.slug_not_separator = kwargs.pop('slug_not_separator', self.slug_separator)

        self.slug_mode = kwargs.pop('slug_mode', 'multiple')
        self.slug_mode_settings = kwargs.pop('slug_mode_settings', {})

        models.Field.__init__(self, *args, **kwargs)

    def pre_save(self, model_instance, add):
        #provadi se test na slug_test a pote jsou prirazeny do vstupnich promennych odpovidajici hodnoty
        test_failed = False
        for test in self.slug_test:
            if parse_attr(model_instance, test) != self.slug_test[test]:
                test_failed = True
        #nutnost delat hluboke kopie, jinak je to jen reference!
        if not test_failed:
            slug_from = copy.deepcopy(self.slug_from)
            slug_separator = copy.deepcopy(self.slug_separator)
            slug_filter = copy.deepcopy(self.slug_filter)
            slug_exclude = copy.deepcopy(self.slug_exclude)
            slug_replacer = copy.deepcopy(self.slug_replacer)
        else:
            slug_from = copy.deepcopy(self.slug_not_from)
            slug_separator = copy.deepcopy(self.slug_not_separator)
            slug_filter = copy.deepcopy(self.slug_not_filter)
            slug_exclude = copy.deepcopy(self.slug_not_exclude)
            slug_replacer = copy.deepcopy(self.slug_not_replacer)
        ###
        # provedeme prepopulate
        value = getattr(model_instance, self.attname)
        if value == '':
            slug_from_value = []
            if type(slug_from) == type(''):
                slug_from_value.append(parse_attr(model_instance, slug_from))
            else:
                for column in slug_from:
                    slug_from_value.append(parse_attr(model_instance, column))
            fromStr = slug_separator.join(slug_from_value)
        else:
            fromStr = value
        #generujeme zakladni slug
        slug = re.sub('[^\w_]+', slug_replacer, utf_to_ascii(fromStr).lower())

        #pokud ma byt hodnota unikatni, tak ji "zunikatnime" :)

        if self.slug_unique:

            querySet = model_instance.__class__.objects.all()

            #vytvoreni omezeni filtru
            #pokud slug_unique_together tak pridame do filtru omezujici podminky
            if type(self.slug_unique_together) == type(''):
                if getattr(model_instance, self.slug_unique_together):
                    slug_filter[self.slug_unique_together] = getattr(model_instance, self.slug_unique_together)

                else:
                    slug_filter[self.slug_unique_together + '__isnull'] = True

            else:
                for unique_together in self.slug_unique_together:
                    if getattr(model_instance, unique_together):
                        slug_filter[unique_together] = getattr(model_instance, unique_together)

                    else:
                        slug_filter[unique_together + '__isnull'] = True
            #zpracovani slugfiltru - mozna by melo byt pred zpracovani unique_together
            if slug_filter != {}:
                for filter in slug_filter:
                    if type(slug_filter[filter]) == type(''):
                        slug_filter[filter] = parse_attr(model_instance, slug_filter[filter])
                querySet = apply(querySet.filter, [], slug_filter)
            if slug_exclude != {}:
                for filter in slug_exclude:
                    slug_exclude[filter] = parse_attr(model_instance, slug_exclude[filter])
                querySet = apply(querySet.exclude, [], slug_exclude)

            return self.createSlug(model_instance, querySet, slug)
        else:
            return slug
