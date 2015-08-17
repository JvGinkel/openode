# -*- coding: utf-8 -*-

import logging

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Q
from django.utils.html import strip_tags

from haystack.indexes import (
    BooleanField,
    CharField,
    Indexable,
    MultiValueField,
    SearchIndex,
    )

from openode.const import (
    NODE_VISIBILITY_PRIVATE,
    # POST_TYPE_COMMENT,
    # POST_TYPE_QUESTION,
    POST_TYPE_THREAD_POST,
    THREAD_TYPE_DISCUSSION,
    THREAD_TYPE_QUESTION,
    )
from openode.document.models import Document, Page, DOCUMENT_PAGE_CONTENT_IF_ERROR
from openode.models import Node, Thread, Organization, Post

################################################################################
# PROXY MODELS
################################################################################

# NOTE:
# Haystack allow for one Model only one Index.
# It is necessary to make some Proxy classes for extra Indexes


class AnswerProxy(Post):
    class Meta:
        proxy = True
        verbose_name = 'AnswerProxy'
        verbose_name_plural = 'AnswerProxies'


class DiscussionPostProxy(Post):
    class Meta:
        proxy = True
        verbose_name = 'DiscussionPostProxy'
        verbose_name_plural = 'DiscussionPostProxies'


class QuestionProxy(Thread):
    class Meta:
        proxy = True
        verbose_name = 'QuestionProxy'
        verbose_name_plural = 'QuestionProxies'


################################################################################
# INDEXES
################################################################################


class QuestionIndex(SearchIndex, Indexable):
    """
        Thread proxy model index
    """

    title = CharField(model_attr="title", boost=5)
    text = CharField(document=True)

    ###################################

    node_visibility = CharField(model_attr="node__visibility", indexed=False)
    external_access = BooleanField(model_attr="external_access", indexed=False)
    node_users = MultiValueField(indexed=False)

    ###################################

    text_for_highlighting = CharField(indexed=False)
    node_title = CharField(indexed=False)
    thread_type = CharField(model_attr="thread_type", indexed=False)
    url = CharField(model_attr="get_absolute_url", indexed=False)
    last_changed = CharField(model_attr="render_last_changed", indexed=False)
    main_post_text = CharField(indexed=False)
    display_title = CharField(model_attr="node__title", indexed=False)
    tags = MultiValueField()
    tags_data = MultiValueField(indexed=False)

    def get_model(self):
        return QuestionProxy

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        qs = self.get_model().objects.filter(
            is_deleted=False,
            thread_type=THREAD_TYPE_QUESTION,
            # posts__post_type__in=[
            #     POST_TYPE_QUESTION,  # _main_post
            #     POST_TYPE_COMMENT
            # ]
        ).select_related(
            "node"
        )
        return qs

    ###################################

    def prepare_title(self, obj):
        return obj.title

    def prepare_text(self, obj):

        try:
            main_post = obj._main_post()
        except ObjectDoesNotExist, e:
            logging.error("FulltextIndex error | %s" % repr({
                "pk": obj.pk,
                "error": str(e),
                "type": type(obj),
            }))
            main_post = None

        data = []
        data.append(obj.title)
        if main_post:
            data.append(obj.node.title)
            data.append(main_post.text)
            for text in main_post.comments.all().values_list("text", flat=True):
                data.append(text)

        return " ".join([
            strip_tags(ch).strip() for ch in data
        ])

        # return " ".join([
        #     obj.title,
        #     main_post.summary,
        #     self.prepare_text_for_highlighting(obj)
        # ])

    ###################################

    def prepare_main_post_text(self, obj):
        try:
            main_post = obj._main_post()
        except Post.DoesNotExist:
            pass
        else:
            if main_post:
                return main_post.text

    def prepare_node_title(self, obj):
        return obj.node.title_with_status()

    def prepare_display_title(self, obj):
        try:
            return obj.get_title('html')
        except Post.DoesNotExist:
            pass

    def prepare_tags(self, obj):
        return list(obj.tags.order_by("name").values_list("name", flat=True))

    def prepare_tags_data(self, obj):
        return list(obj.tags.order_by("name").values_list("id", "name"))

    def prepare_node_users(self, obj):

        if obj.node.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.node.node_users.values_list("user_id", flat=True))
        return []

    ###################################

    def prepare_text_for_highlighting(self, obj):

        data = []

        try:
            main_post = obj._main_post()
        except Post.DoesNotExist, e:
            logging.error("%s | thread pk:%s" % (
                str(e),
                obj.pk,
            ))
            return ""

        data.append(main_post.text)
        data.extend(main_post.comments.values_list("text", flat=True))

        for answer in obj.get_answers().filter(deleted=False).order_by("-points"):
            data.append(answer.text)
            data.extend(answer.comments.values_list("text", flat=True))

        # if thread is document, add all page's text to fulltext
        if obj.is_document():
            doc = obj.get_document()
            if doc:
                if doc.plain_text:
                    data.append(doc.plain_text)
                data.extend(doc.get_pages().values_list("plaintext", flat=True))

        data.append(obj.node.title)

        return " ".join(data)


################################################################################
################################################################################

class AnswerIndex(SearchIndex, Indexable):
    """
        Post proxy model
    """

    title = CharField(boost=5)
    text = CharField(document=True)

    url = CharField(indexed=False)
    last_changed = CharField(indexed=False)
    # tags = MultiValueField()
    # tags_data = MultiValueField(indexed=False)

    # PERM FIELDS
    external_access = BooleanField(indexed=False)
    node_users = MultiValueField(indexed=False)
    node_visibility = CharField(indexed=False)

    def get_model(self):
        return AnswerProxy

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        qs = self.get_model().objects.filter(
            deleted=False,
            post_type=POST_TYPE_THREAD_POST,
            thread__thread_type=THREAD_TYPE_QUESTION
        )
        return qs

    def prepare_title(self, obj):
        return obj.thread.title

    def prepare_text(self, obj):
        # TODO
        data = []
        data.append(obj.thread.node.title)
        data.append(obj.text)
        for c in obj.comments.all():
            data.append(c.text)

        return " ".join([
            strip_tags(ch).strip() for ch in data
        ])

    def prepare_url(self, obj):
        return obj.get_absolute_url()

    # def prepare_tags(self, obj):
    #     return list(
    #         obj.thread.tags.order_by("name").values_list("name", flat=True)
    #     )

    # def prepare_tags_data(self, obj):
    #     return list(
    #         obj.thread.tags.order_by("name").values_list("id", "name")
    #     )

    ###################################

    def prepare_node_users(self, obj):
        if obj.thread.node.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.thread.node.node_users.values_list("user_id", flat=True))
        return []

    def prepare_external_access(self, obj):
        return obj.thread.external_access

    def prepare_node_visibility(self, obj):
        return obj.thread.node.visibility

    def prepare_last_changed(self, obj):
        return obj.thread.render_last_changed()

################################################################################
################################################################################


class DiscussionPostIndex(SearchIndex, Indexable):
    """
        Post proxy model
    """

    title = CharField(boost=5)
    text = CharField(document=True)

    url = CharField(indexed=False)
    last_changed = CharField(indexed=False)

    # PERM FIELDS
    external_access = BooleanField(indexed=False)
    node_users = MultiValueField(indexed=False)
    node_visibility = CharField(indexed=False)

    def get_model(self):
        return DiscussionPostProxy

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        qs = self.get_model().objects.filter(
            deleted=False,
            post_type=POST_TYPE_THREAD_POST,
            thread__thread_type=THREAD_TYPE_DISCUSSION,
            thread__node__id__gte=1,
        )
        return qs

    def prepare_title(self, obj):
        return obj.thread.node.title_with_status()

    def prepare_text(self, obj):
        data = []
        data.append(obj.thread.node.title)
        data.append(obj.text)
        return " ".join([
            strip_tags(ch).strip() for ch in data
        ])

    def prepare_url(self, obj):
        return obj.get_absolute_url()

    def prepare_last_changed(self, obj):
        return obj.thread.render_last_changed()

    ###################################

    def prepare_node_users(self, obj):
        if obj.thread.node.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.thread.node.node_users.values_list("user_id", flat=True))
        return []

    def prepare_external_access(self, obj):
        return obj.thread.external_access

    def prepare_node_visibility(self, obj):
        return obj.thread.node.visibility

################################################################################
################################################################################


class DocumentIndex(SearchIndex, Indexable):
    """
        Document index
    """
    title = CharField(boost=5)
    text = CharField(document=True)

    # PERM FIELDS
    external_access = BooleanField(indexed=False)
    node_users = MultiValueField(indexed=False)
    node_visibility = CharField(indexed=False)

    icon = CharField(indexed=False)
    node_title = CharField(indexed=False)
    url = CharField(indexed=False)
    last_changed = CharField(indexed=False)

    def get_model(self):
        return Document

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        qs = self.get_model().objects.filter(
            is_deleted=False,
            thread__is_deleted=False
        ).select_related(
            "thread"
        )
        return qs

    def prepare_title(self, obj):
        return obj.thread.title

    def prepare_text(self, obj):

        thread = obj.thread
        main_post = thread._main_post()

        data = []
        data.append(thread.node.title)
        data.append(thread.title)
        data.append(main_post.text)

        return " ".join([
            strip_tags(ch).strip() for ch in data
        ])

    def prepare_icon(self, obj):
        return obj.get_icon()

    def prepare_node_title(self, obj):
        return obj.thread.node.title_with_status()

    def prepare_url(self, obj):
        return obj.get_absolute_url()

    def prepare_last_changed(self, obj):
        return obj.thread.render_last_changed()

    ###################################

    def prepare_node_users(self, obj):
        if obj.thread.node.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.thread.node.node_users.values_list("user_id", flat=True))
        return []

    def prepare_external_access(self, obj):
        return obj.thread.external_access

    def prepare_node_visibility(self, obj):
        return obj.thread.node.visibility

################################################################################
################################################################################


class DocumentPageIndex(SearchIndex, Indexable):
    """
        Post proxy model
    """

    title = CharField(boost=5)
    text = CharField(document=True)

    # PERM FIELDS
    external_access = BooleanField(indexed=False)
    node_users = MultiValueField(indexed=False)
    node_visibility = CharField(indexed=False)

    url = CharField(indexed=False)
    document_icon = CharField(indexed=False)
    node_title = CharField(indexed=False)
    page = CharField(indexed=False)

    def get_model(self):
        return Page

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        qs = self.get_model().objects.filter(
            document_revision__document__thread__is_deleted=False,
        ).exclude(
            Q(plaintext=DOCUMENT_PAGE_CONTENT_IF_ERROR)
            |
            Q(plaintext="")
        )
        return qs

    def prepare_title(self, obj):
        return obj.document_revision.document.thread.title

    def prepare_text(self, obj):
        return obj.plaintext

    def prepare_node_title(self, obj):
        return obj.document_revision.document.thread.node.title_with_status()

    def prepare_document_icon(self, obj):
        return obj.document_revision.document.get_icon()

    def prepare_page(self, obj):
        return "%s/%s" % (
            obj.number,
            obj.document_revision.pages.aggregate(_max=Max("number")).get("_max", obj.number)
        )

    def prepare_url(self, obj):
        # TODO: go to selected page
        return obj.document_revision.document.get_absolute_url()

    ###################################

    def prepare_node_users(self, obj):
        if obj.document_revision.document.thread.node.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.document_revision.document.thread.node.node_users.values_list("user_id", flat=True))
        return []

    def prepare_external_access(self, obj):
        return obj.document_revision.document.thread.external_access

    def prepare_node_visibility(self, obj):
        return obj.document_revision.document.thread.node.visibility


################################################################################
################################################################################


class NodeIndex(SearchIndex, Indexable):

    title = CharField(boost=10)
    text = CharField(document=True)

    text_for_highlighting = CharField(indexed=False)

    url = CharField(model_attr="get_absolute_url", indexed=False)
    full_title = CharField(indexed=False)

    node_visibility = CharField(model_attr="visibility", indexed=False)
    node_users = MultiValueField(indexed=False)

    def get_model(self):
        return Node

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()

    ###################################

    def prepare(self, obj):
        data = super(NodeIndex, self).prepare(obj)
        data['boost'] = 1.1
        return data

    def prepare_title(self, obj):
        return obj.title_with_status()

    def prepare_full_title(self, obj):
        return obj.full_title_with_status(style="html")

    def prepare_text(self, obj):
        return " ".join([
            obj.title,
            self.prepare_text_for_highlighting(obj)
        ])

    def prepare_node_users(self, obj):
        if obj.visibility == NODE_VISIBILITY_PRIVATE:
            # store users only for private nodes
            return list(obj.node_users.values_list("user_id", flat=True))
        return []

    ###################################

    def prepare_text_for_highlighting(self, obj):
        data = [
            obj.title,
            obj.long_title,
            obj.perex_node,
            obj.perex_qa,
            obj.perex_forum,
            obj.perex_annotation,
            obj.perex_library,
        ]
        if obj.description:
            data.append(obj.description)
        return " ".join([strip_tags(ch).strip() for ch in data])

################################################################################
################################################################################


class UserIndex(SearchIndex, Indexable):

    title = CharField()
    text = CharField(document=True)
    text_for_highlighting = CharField(indexed=False)

    url = CharField(model_attr="get_absolute_url", indexed=False)

    def get_model(self):
        return User

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()

    ###################################

    def prepare_title(self, obj):
        return obj.screen_name

    def prepare_text(self, obj):
        return " ".join([
            self.prepare_title(obj),
            self.prepare_text_for_highlighting(obj)
        ])

    def prepare_text_for_highlighting(self, obj):
        return obj.description.text if obj.description else ""


################################################################################
################################################################################


class OrganizationIndex(SearchIndex, Indexable):

    title = CharField()
    text = CharField(document=True)

    url = CharField(model_attr="get_absolute_url", indexed=False)

    def get_model(self):
        return Organization

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()

    ###################################

    def prepare_title(self, obj):
        return obj.title

    def prepare_text(self, obj):
        return " ".join([
            obj.title,
            obj.long_title,
            obj.description.text if obj.description else ""
        ])
