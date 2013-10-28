# -*- coding: utf-8 -*-

import simplejson as json

# from django.contrib.auth.models import User
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from haystack import views
from haystack.query import EmptySearchQuerySet, SearchQuerySet, SQ

from openode.const import (
    NODE_VISIBILITY_PUBLIC,
    NODE_VISIBILITY_REGISTRED_USERS,
    NODE_VISIBILITY_PRIVATE,
    NODE_VISIBILITY_SEMIPRIVATE,
    )
from openode.models import Tag  # , Node, Thread
from openode.search.forms import SearchForm
from openode.skins.loaders import render_into_skin, get_template

################################################################################
################################################################################

RESULTS_PER_PAGE = 20

################################################################################


class BaseSearchView(object):
    """
        Base class for all search view.
    """

    # def update_search_query(self, sq, term=None, auto_query=None):
    def update_search_query(self, sq):
        """
            update SearchQuerySet - add filters and excludes
        """

        if self.request.user.is_authenticated():
            enabled_nodes_sq = SQ(
                node_visibility__in=[
                    NODE_VISIBILITY_PUBLIC,
                    NODE_VISIBILITY_SEMIPRIVATE,
                    NODE_VISIBILITY_REGISTRED_USERS,
                ]
            )
            perm_filter = SQ(
                SQ(SQ(node_visibility=NODE_VISIBILITY_PRIVATE) & SQ(node_users=self.request.user.pk))
                | SQ(SQ(django_ct='openode.thread') & SQ(external_access=True))
                | enabled_nodes_sq
            )
            index_types_sq_exclude = None
        else:
            enabled_nodes_sq = SQ(
                node_visibility__in=[
                    NODE_VISIBILITY_PUBLIC,
                    NODE_VISIBILITY_SEMIPRIVATE,
                ]
            )
            perm_filter = SQ(
                SQ(SQ(django_ct='openode.thread') & SQ(external_access=True))
                | enabled_nodes_sq
            )
            index_types_sq_exclude = SQ(django_ct__in=['auth.user', 'openode.organization'])

        ###############################

        # if auto_query and self.query:
        #     sq = sq.auto_query(self.query)
        # elif term:
        if self.query:
            sq = sq.filter(
                SQ(title=self.query) | SQ(text=self.query)
            )

        # excelude indexes for not authenticated users
        if index_types_sq_exclude:
            sq = sq.exclude(index_types_sq_exclude)

        # permissions filter
        sq = sq.filter(
            SQ(django_ct__in=['auth.user', 'openode.organization'])  # find in User or Organizations
            |
            perm_filter  # OR find in other all model indexes, check perms
        )

        return sq

################################################################################
################################################################################


class SearchView(BaseSearchView, views.SearchView):

    def __init__(self, *args, **kwargs):
        kwargs["form_class"] = SearchForm
        self.results_per_page = RESULTS_PER_PAGE
        super(SearchView, self).__init__(*args, **kwargs)

    def __call__(self, request, tags=None):

        # Tag objects, from url
        self.selected_tags = []
        if tags:
            self.selected_tags = Tag.objects.valid_tags().filter(pk__in=[int(_id) for _id in tags.split("+")])

        return super(SearchView, self).__call__(request)

    def prepare_search_queryset(self):
        sq = SearchQuerySet()

        filter_types = self.form.get_filter_types()
        _sq = SQ()
        for or_filter in filter_types:
            _sq.add(SQ(**or_filter), SQ.OR)

        if not filter_types:
            return sq
        return sq.filter(_sq)

    def build_form(self, form_kwargs=None):
        """
        Instantiates the form the class should use to process the search query.
        """
        data = None
        kwargs = {
            'load_all': self.load_all,
        }
        if form_kwargs:
            kwargs.update(form_kwargs)

        if len(self.request.GET):
            data = self.request.GET

        if self.searchqueryset is not None:
            kwargs['searchqueryset'] = self.searchqueryset

        return self.form_class(data or {}, **kwargs)

    def get_results(self):
        """
        Fetches the results via the form.
        Returns an empty list if there's no query to search with.
        """

        if not(self.selected_tags or self.query):
            return EmptySearchQuerySet()

        sq = self.prepare_search_queryset()

        if self.selected_tags:
            # OR version
            # sq = sq.filter(tags__in=[tag.name for tag in self.selected_tags])

            # AND version
            for tag in self.selected_tags:
                sq = sq.filter(tags=tag.name)

        # return self.update_search_query(sq, auto_query=True)
        return self.update_search_query(sq)

    def create_response(self):
        """
        Generates the actual HttpResponse to send back to the user.
        """

        def tags_reduce_fx(all_pks, pk):
            """
                clean function to template
            """
            ret = list(all_pks)
            ret.remove(pk)
            return "+".join([str(i) for i in ret])

        (paginator, page) = self.build_page()

        ###############################

        others_tags_ids = set()
        for res in page.object_list:
            if not res.tags_data:
                continue
            for tag_data in res.tags_data:
                others_tags_ids.add(tag_data[0])

        tags_pks = set([tag.pk for tag in self.selected_tags])
        if tags_pks:
            other_tags = Tag.objects.valid_tags().filter(pk__in=set(others_tags_ids - tags_pks))
        else:
            other_tags = Tag.objects.valid_tags().order_by("-used_count")

        ###############################

        search_in_query = ""
        if self.form["search_in"].data:
            search_in_query = "&".join(["search_in=%s" % i for i in self.form["search_in"].data])

        context = {
            "search_in_query": search_in_query,
            'query': self.query,
            'form': self.form,
            'page': page,
            'paginator': paginator,
            'suggestion': None,
            "other_tags": other_tags,

            "selected_tags": self.selected_tags,
            "tags_query": "+".join([str(tag.pk) for tag in self.selected_tags]),
            "tags_pks": tags_pks,
            "tags_reduce_fx": tags_reduce_fx,

            "show_results": bool(self.selected_tags or self.query)
        }

        if self.results and hasattr(self.results, 'query') and self.results.query.backend.include_spelling:
            context['suggestion'] = self.form.get_suggestion()
        context.update(self.extra_context())
        return render_into_skin(self.template, context, self.request)


################################################################################
################################################################################


class AutocompleteSearchView(BaseSearchView):
    __name__ = 'AutocompleteSearchView'
    RESULTS_COUNT = 5

    def __call__(self, request):
        self.request = request
        return self.create_response()

    def create_response(self):

        term = self.request.GET.get('autoq', '').strip()
        self.query = term
        sqs = self.update_search_query(
            SearchQuerySet().all(),
            # term=term,
        )[:self.RESULTS_COUNT + 1]

        templates = {
            "openode.node": get_template("search/results/autocomplete_node.html"),
            "openode.questionproxy": get_template("search/results/autocomplete_question.html"),
            "openode.answerproxy": get_template("search/results/autocomplete_answer.html"),
            "openode.discussionpostproxy": get_template("search/results/autocomplete_discussion_post.html"),
            "document.document": get_template("search/results/autocomplete_document.html"),
            "document.page": get_template("search/results/autocomplete_document.html"),
            "openode.organization": get_template("search/results/autocomplete_organization.html"),
            "auth.user": get_template("search/results/autocomplete_user.html"),
        }

        suggestions = []

        for i, result in enumerate(sqs):
            if i < self.RESULTS_COUNT:
                suggestions.append(
                    {
                        "label": templates[result.content_type()].render({"result": result}),
                        "value": result.title.strip(),
                        "url": result.url,
                    }
                )

        if len(sqs) > self.RESULTS_COUNT:
            suggestions.append(
                {
                    "label": u'<span class="more-results">%s</span>' % _('more results'),
                    "value": term,
                    "url": u'%s?q=%s' % (reverse('search'), term),
                }
            )

        json_data = json.dumps({
            "results": suggestions
        })
        return HttpResponse(json_data, content_type='application/json')
