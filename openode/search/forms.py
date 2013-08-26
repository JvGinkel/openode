# -*- coding: utf-8 -*-

from django import forms
from django.utils.translation import ugettext as _

from haystack.forms import SearchForm as HaystackSearchForm
from haystack.constants import DJANGO_CT

################################################################################

SEARCH_IN_CHOICE_DOC = 1
SEARCH_IN_CHOICE_QA = 2
SEARCH_IN_CHOICE_DIS = 3
SEARCH_IN_CHOICE_NODES = 4
SEARCH_IN_CHOICE_ORGS = 5
SEARCH_IN_CHOICE_USERS = 6

SEARCH_IN_CHOICES = (
    (SEARCH_IN_CHOICE_NODES, _("Nodes")),
    (SEARCH_IN_CHOICE_DOC, _("Documents")),
    (SEARCH_IN_CHOICE_QA, _("Questions")),
    (SEARCH_IN_CHOICE_DIS, _("Discussions")),
    (SEARCH_IN_CHOICE_ORGS, _("Organizations")),
    (SEARCH_IN_CHOICE_USERS, _("Users")),
)

# THREADS_MAP = {
#     SEARCH_IN_CHOICE_DOC: "document",
#     SEARCH_IN_CHOICE_QA: "question",
#     SEARCH_IN_CHOICE_DIS: "discussion",
# }

################################################################################


class SearchForm(HaystackSearchForm):

    search_in = forms.MultipleChoiceField(
        choices=SEARCH_IN_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        initial=dict(SEARCH_IN_CHOICES).keys(),
        required=False,
        label=_(u"Search in")
    )

    def get_filter_types(self):
        ret = []
        cl_data = [int(i) for i in self.cleaned_data["search_in"]]

        # NODE
        if SEARCH_IN_CHOICE_NODES in cl_data:
            ret.append({
                DJANGO_CT: "openode.node",
            })

        # DOCUMENT
        if SEARCH_IN_CHOICE_DOC in cl_data:
            ret.extend([
                {DJANGO_CT: "document.document"},
                {DJANGO_CT: "document.page"}
            ])

        # QUESTION
        if SEARCH_IN_CHOICE_QA in cl_data:
            ret.extend([
                {DJANGO_CT: "openode.questionproxy"},
                {DJANGO_CT: "openode.answerproxy"}
            ])

        # DISCUSSION
        if SEARCH_IN_CHOICE_DIS in cl_data:
            ret.append({
                DJANGO_CT: "openode.discussionpostproxy",
            })

        # ORGANIZATIONS
        if SEARCH_IN_CHOICE_ORGS in cl_data:
            ret.append({
                DJANGO_CT: "openode.organization",
            })

        # USERS
        if SEARCH_IN_CHOICE_USERS in cl_data:
            ret.append({
                DJANGO_CT: "auth.user",
            })

        # for k in THREADS_MAP.keys():
        #     if k in cl_data:
        #         ret.append({
        #             DJANGO_CT: "openode.thread",
        #             "thread_type": THREADS_MAP[k]
        #         })

        return ret

    # MODELS = [
    #     Node,
    #     Thread
    # ]

    # def search(self):
    #     return super(SearchForm, self).search().models(*self.MODELS)
