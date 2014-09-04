# -*- coding: utf-8 -*-

import datetime
import logging
import operator
import re
from uuid import uuid4

from mptt.models import MPTTModel, TreeForeignKey

from django.conf import settings as django_settings
from django.db import models
from django.contrib.auth.models import User
from django.core import cache  # import cache, not from cache import cache, to be able to monkey-patch cache.cache in test cases
from django.core import exceptions as django_exceptions
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse
# from django.utils.hashcompat import md5_constructor
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils.translation import get_language

import openode
from openode.conf import settings as openode_settings
# from openode import mail
# from openode.mail import messages
from openode.models.fields import SlugField
from openode.models.node import Node
from openode.models.tag import Tag

from openode.models.tag import get_tags_by_names
from openode.models.tag import filter_accepted_tags, filter_suggested_tags
from openode.models.tag import delete_tags, separate_unused_tags
from openode.models.base import DraftContent, BaseQuerySetManager

from openode.models.post import Post, PostRevision
# from openode.models.user import Organization
from openode.models import signals
from openode import const
from openode.utils.lists import LazyList
from openode.utils.path import sanitize_file_name
from openode.utils.text import extract_numbers
from openode.search import mysql
# from openode.utils.slug import slugify
from openode.skins.loaders import get_template  # jinja2 template loading enviroment
from openode.search.state_manager import DummySearchState

from django.conf import settings


class ThreadQuerySet(models.query.QuerySet):

    def get_questions(self):
        return self.filter(thread_type=const.THREAD_TYPE_QUESTION)

    def get_discussions(self):
        return self.filter(thread_type=const.THREAD_TYPE_DISCUSSION)

    def get_documents(self):
        return self.filter(thread_type=const.THREAD_TYPE_DOCUMENT)

    def get_visible(self, user):
        """filters out threads not belonging to the user organizations"""
        if user.is_authenticated():
            organizations = user.get_organizations()
        else:
            organizations = []
        return self.filter(organizations__in=organizations).distinct()


class ThreadManager(BaseQuerySetManager):

    def get_query_set(self):
        return ThreadQuerySet(self.model)

    def get_tag_summary_from_threads(self, threads):
        """returns a humanized string containing up to
        five most frequently used
        unique tags coming from the ``threads``.
        Variable ``threads`` is an iterable of
        :class:`~openode.models.Thread` model objects.

        This is not implemented yet as a query set method,
        because it is used on a list.
        """
        # TODO: In Python 2.6 there is collections.Counter() thing which would be very useful here
        # TODO: In Python 2.5 there is `defaultdict` which already would be an improvement
        tag_counts = dict()
        for thread in threads:
            for tag_name in thread.get_tag_names():
                if tag_name in tag_counts:
                    tag_counts[tag_name] += 1
                else:
                    tag_counts[tag_name] = 1
        tag_list = tag_counts.keys()
        tag_list.sort(key=lambda t: tag_counts[t], reverse=True)

        #note that double quote placement is important here
        if len(tag_list) == 1:
            last_topic = '"'
        elif len(tag_list) <= 5:
            last_topic = _('" and "%s"') % tag_list.pop()
        else:
            tag_list = tag_list[:5]
            last_topic = _('" and more')

        return '"' + '", "'.join(tag_list) + last_topic

    def public(self):
        return self.filter(is_deleted=False)

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def create_new(self, title, author, added_at, text, tagnames='', by_email=False, email_address=None, node=None, thread_type=None, category=None, external_access=None):
        """creates new thread"""
        # TODO: Some of this code will go to Post.objects.create_new

        thread = super(
            ThreadManager,
            self
        ).create(
            title=title,
            tagnames=tagnames,
            last_activity_at=added_at,
            last_activity_by=author,
            node=node,
            thread_type=thread_type,
            category=category,
            external_access=bool(external_access),
            dt_created=added_at
        )

        #todo: code below looks like ``Post.objects.create_new()``
        post = Post(
            post_type=thread_type,  # DANGER  maybe some mapping function should be here
            thread=thread,
            author=author,
            added_at=added_at,
            #html field is denormalized in .save() call
            text=text,
            #summary field is denormalized in .save() call
        )

        #this is kind of bad, but we save assign privacy organizations to posts and thread
        #this call is rather heavy, we should split into several functions
        # inbox and activity is replaced by follow
        # parse_results = post.parse_and_save(author=author)
        post.parse_and_save(author=author)

        revision = post.add_revision(
            title=title,
            author=author,
            text=text,
            comment=const.POST_STATUS['default_version'],
            revised_at=added_at,
            by_email=by_email,
            email_address=email_address
        )

        #todo: this is handled in signal because models for posts
        #are too spread out
        # signals.post_updated.send(
        #     post=post,
        #     updated_by=author,
        #     newly_mentioned_users=parse_results['newly_mentioned_users'],
        #     timestamp=added_at,
        #     created=True,
        #     diff=parse_results['diff'],
        #     sender=post.__class__
        # )
        # print thread.pk, thread.slug, post.pk
        # # INFO: Question has to be saved before update_tags() is called
        # thread.update_tags(tagnames=tagnames, user=author, timestamp=added_at)

        return thread

    def get_for_query(self, search_query, qs=None):
        """returns a query set of questions,
        matching the full text query
        """
        if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):  # HEYSTACK DEPRECATED
            from openode.search.haystack import OpenodeSearchQuerySet
            hs_qs = OpenodeSearchQuerySet().filter(content=search_query)
            return hs_qs.get_django_queryset()
        else:
            if not qs:
                qs = self.all()
            if openode.get_database_engine_name().endswith('mysql') \
                and mysql.supports_full_text_search():
                return qs.filter(
                    models.Q(title__search=search_query) |
                    models.Q(tagnames__search=search_query) |
                    models.Q(posts__deleted=False, posts__text__search=search_query)
                )
            elif 'postgresql_psycopg2' in openode.get_database_engine_name():
                from openode.search import postgresql
                return postgresql.run_full_text_search(qs, search_query)
            else:
                return qs.filter(
                    models.Q(title__icontains=search_query) |
                    models.Q(tagnames__icontains=search_query) |
                    models.Q(posts__deleted=False, posts__text__icontains=search_query)
                )

    def run_advanced_search(self, request_user, search_state):  # TODO: !! review, fix, and write tests for this
        #DEPRECATED
        """
        all parameters are guaranteed to be clean
        however may not relate to database - in that case
        a relvant filter will be silently dropped

        """
        # from openode.conf import settings as openode_settings  # Avoid circular import

        # TODO: add a possibility to see deleted questions
        thread_type = const.THREAD_TYPE_BY_NODE_MODULE[search_state.module]
        qs = self.filter(
                posts__post_type=thread_type,
                # posts__deleted=False,
                is_deleted=False,
            )  # (***) brings `openode_post` into the SQL query, see the ordering section below

        if search_state.module:
            qs = qs.filter(thread_type=thread_type)

        if search_state.node:
            qs = qs.filter(node=search_state.node)

        #run text search while excluding any modifier in the search string
        #like #tag [title: something] @user
        if search_state.stripped_query:
            qs = self.get_for_query(search_query=search_state.stripped_query, qs=qs)

        #we run other things after full text search, because
        #FTS may break the chain of the query set calls,
        #since it might go into an external asset, like Solr

        #search in titles, if necessary
        if search_state.query_title:
            qs = qs.filter(title__icontains=search_state.query_title)

        #search user names if @user is added to search string
        #or if user name exists in the search state
        if search_state.query_users:
            query_users = User.objects.filter(username__in=search_state.query_users)
            if query_users:
                qs = qs.filter(
                    posts__post_type=thread_type,
                    posts__author__in=query_users
                )  # TODO: unify with search_state.author ?
        #unified tags - is list of tags taken from the tag selection
        #plus any tags added to the query string with #tag or [tag:something]
        #syntax.
        #run tag search in addition to these unified tags
        meta_data = {}
        tags = search_state.unified_tags()
        if len(tags) > 0:

            if openode_settings.TAG_SEARCH_INPUT_ENABLED:
                #todo: this may be gone or disabled per option
                #"tag_search_box_enabled"
                existing_tags = set()
                non_existing_tags = set()
                #we're using a one-by-one tag retreival, b/c
                #we want to take advantage of case-insensitive search indexes
                #in postgresql, plus it is most likely that there will be
                #only one or two search tags anyway
                for tag in tags:
                    try:
                        tag_record = Tag.objects.get(name__iexact=tag)
                        existing_tags.add(tag_record.name)
                    except Tag.DoesNotExist:
                        non_existing_tags.add(tag)

                meta_data['non_existing_tags'] = list(non_existing_tags)
                tags = existing_tags
            else:
                meta_data['non_existing_tags'] = list()

            #construct filter for the tag search
            for tag in tags:
                qs = qs.filter(tags__name=tag)  # Tags or AND-ed here, not OR-ed (i.e. we fetch only threads with all tags)
        else:
            meta_data['non_existing_tags'] = list()

        if search_state.scope == const.THREAD_SCOPE_WITH_NO_ACCEPTED_ANSWER:
            qs = qs.filter(closed=False, accepted_answer__isnull=True)

        if search_state.scope == const.THREAD_SCOPE_WITH_ACCEPTED_ANSWER:
            qs = qs.filter(closed=False, accepted_answer__isnull=False)

        elif search_state.scope == const.THREAD_SCOPE_UNANSWERED:
            qs = qs.filter(closed=False, answer_count=0)  # Do not show closed questions in unanswered section

        elif search_state.scope == const.THREAD_SCOPE_FOLLOWED:
            followed_filter = models.Q(followed_by=request_user)
            if 'followit' in django_settings.INSTALLED_APPS:
                followed_users = request_user.get_followed_users()
                followed_filter |= models.Q(posts__post_type__in=(thread_type, 'answer'), posts__author__in=followed_users)
            qs = qs.filter(followed_filter)

        # user contributed questions
        if search_state.author:
            try:
                if isinstance(search_state.author, (list, tuple, set)):
                    _ids = [
                        int(_id)
                        for _id in search_state.author
                        if str(_id).isdigit()
                    ]
                    u = User.objects.filter(
                        is_active=True,
                        is_hidden=False,
                        id__in=_ids
                    )
                elif search_state.author.isdigit():
                    u = User.objects.filter(
                        is_active=True,
                        is_hidden=False,
                        id=search_state.author
                    )
                else:
                    ids = [
                        int(ch)
                        for ch in extract_numbers(search_state.author)
                    ]
                    u = User.objects.filter(
                        id__in=ids,
                        is_active=True,
                        is_hidden=False
                    )
            except User.DoesNotExist:
                meta_data['authors'] = []
            else:
                if u.exists():
                    qs = qs.filter(
                        posts__post_type__in=(thread_type, 'answer', "comment"),
                        posts__author__in=u,
                        posts__deleted=False
                    )
                meta_data['authors'] = u

        #get users tag filters
        if request_user and request_user.is_authenticated():
            #mark questions tagged with interesting tags
            #a kind of fancy annotation, would be nice to avoid it
            interesting_tags = Tag.objects.filter(
                user_selections__user=request_user,
                user_selections__reason='good'
            )
            ignored_tags = Tag.objects.filter(
                user_selections__user=request_user,
                user_selections__reason='bad'
            )
            subscribed_tags = Tag.objects.none()
            if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
                subscribed_tags = Tag.objects.filter(
                    user_selections__user=request_user,
                    user_selections__reason='subscribed'
                )
                meta_data['subscribed_tag_names'] = [tag.name for tag in subscribed_tags]

            meta_data['interesting_tag_names'] = [tag.name for tag in interesting_tags]
            meta_data['ignored_tag_names'] = [tag.name for tag in ignored_tags]

            if request_user.display_tag_filter_strategy == const.INCLUDE_INTERESTING and (interesting_tags or request_user.has_interesting_wildcard_tags()):
                #filter by interesting tags only
                interesting_tag_filter = models.Q(tags__in=interesting_tags)
                if request_user.has_interesting_wildcard_tags():
                    interesting_wildcards = request_user.interesting_tags.split()
                    extra_interesting_tags = Tag.objects.get_by_wildcards(interesting_wildcards)
                    interesting_tag_filter |= models.Q(tags__in=extra_interesting_tags)
                qs = qs.filter(interesting_tag_filter)

            # get the list of interesting and ignored tags (interesting_tag_names, ignored_tag_names) = (None, None)
            if request_user.display_tag_filter_strategy == const.EXCLUDE_IGNORED and (ignored_tags or request_user.has_ignored_wildcard_tags()):
                #exclude ignored tags if the user wants to
                qs = qs.exclude(tags__in=ignored_tags)
                if request_user.has_ignored_wildcard_tags():
                    ignored_wildcards = request_user.ignored_tags.split()
                    extra_ignored_tags = Tag.objects.get_by_wildcards(ignored_wildcards)
                    qs = qs.exclude(tags__in=extra_ignored_tags)

            if request_user.display_tag_filter_strategy == const.INCLUDE_SUBSCRIBED \
                and subscribed_tags:
                qs = qs.filter(tags__in=subscribed_tags)

            if openode_settings.USE_WILDCARD_TAGS:
                meta_data['interesting_tag_names'].extend(request_user.interesting_tags.split())
                meta_data['ignored_tag_names'].extend(request_user.ignored_tags.split())

        QUESTION_ORDER_BY_MAP = {
            (const.THREAD_SORT_METHOD_AGE, const.THREAD_SORT_DIR_DOWN): '-added_at',
            (const.THREAD_SORT_METHOD_AGE, const.THREAD_SORT_DIR_UP): 'added_at',
            (const.THREAD_SORT_METHOD_ACTIVITY, const.THREAD_SORT_DIR_DOWN): '-last_activity_at',
            (const.THREAD_SORT_METHOD_ACTIVITY, const.THREAD_SORT_DIR_UP): 'last_activity_at',
            (const.THREAD_SORT_METHOD_POSTS, const.THREAD_SORT_DIR_DOWN): '-answer_count',
            (const.THREAD_SORT_METHOD_POSTS, const.THREAD_SORT_DIR_UP): 'answer_count',
        }

        orderby = QUESTION_ORDER_BY_MAP[(search_state.sort_method, search_state.sort_dir)]

        if not (
            # HEYSTACK DEPRECATED
            getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False) \
            and orderby == '-relevance'
        ):
            #FIXME: this does not produces the very same results as postgres.
            qs = qs.extra(order_by=[orderby])

        # HACK: We add 'ordering_key' column as an alias and order by it, because when distict() is used,
        #       qs.extra(order_by=[orderby,]) is lost if only `orderby` column is from openode_post!
        #       Removing distinct() from the queryset fixes the problem, but we have to use it here.
        # UPDATE: Apparently we don't need distinct, the query don't duplicate Thread rows!
        # qs = qs.extra(select={'ordering_key': orderby.lstrip('-')}, order_by=['-ordering_key' if orderby.startswith('-') else 'ordering_key'])
        # qs = qs.distinct()

        qs = qs.only('id', 'title', 'view_count', 'answer_count', 'last_activity_at', 'last_activity_by', 'closed', 'tagnames', 'accepted_answer')

        #print qs.query

        return qs.distinct(), meta_data

    def precache_view_data_hack(self, threads):
        # TODO: Re-enable this when we have a good test cases to verify that it works properly.
        #
        #       E.g.: - make sure that not precaching give threads never increase # of db queries for the main page
        #             - make sure that it really works, i.e. stuff for non-cached threads is fetched properly
        # Precache data only for non-cached threads - only those will be rendered
        #threads = [thread for thread in threads if not thread.summary_html_cached()]

        thread_ids = [obj.id for obj in threads]
        thread_types = [tt[0] for tt in const.THREAD_TYPES]
        page_main_posts = Post.objects.filter(
            post_type__in=thread_types, thread__id__in=thread_ids
        ).only(  # pick only the used fields
            'id', 'thread', 'points',
            'summary', 'post_type', 'deleted'
        )
        page_main_posts_map = {}
        for pq in page_main_posts:
            page_main_posts_map[pq.thread_id] = pq
        for thread in threads:
            thread._question_cache = page_main_posts_map[thread.pk]

        last_activity_by_users = User.objects.filter(id__in=[obj.last_activity_by_id for obj in threads])\
                                    .only('id', 'username',)
        user_map = {}
        for la_user in last_activity_by_users:
            user_map[la_user.id] = la_user
        for thread in threads:
            try:
                thread._last_activity_by_cache = user_map[thread.last_activity_by_id]
            except KeyError:
                continue

    #todo: this function is similar to get_response_receivers - profile this function against the other one
    def get_thread_contributors(self, thread_list):
        """Returns query set of Thread contributors"""
        # INFO: Evaluate this query to avoid subquery in the subsequent query below (At least MySQL can be awfully slow on subqueries)
        u_id = list(Post.objects.filter(post_type__in=('question', 'answer'), thread__in=thread_list).values_list('author', flat=True))

        #todo: this does not belong gere - here we select users with real faces
        #first and limit the number of users in the result for display
        #on the main page, we might also want to completely hide fake gravatars
        #and show only real images and the visitors - even if he does not have
        #a real image and try to prompt him/her to upload a picture
        # from openode.conf import settings as openode_settings
        avatar_limit = openode_settings.SIDEBAR_MAIN_AVATAR_LIMIT
        contributors = User.objects.filter(is_active=True, id__in=u_id).order_by('avatar_type', '?')[:avatar_limit]
        return contributors

    def get_for_user(self, user):
        """returns threads where a given user had participated"""
        post_ids = PostRevision.objects.filter(
                                        author=user
                                    ).values_list(
                                        'post_id', flat=True
                                    ).distinct()
        thread_ids = Post.objects.filter(
                                        id__in=post_ids
                                    ).values_list(
                                        'thread_id', flat=True
                                    ).distinct()
        return self.filter(id__in=thread_ids)


class ThreadCategory(MPTTModel):
    """
    ThreadCategory model
    """
    parent = TreeForeignKey('self', null=True, related_name='children', blank=True)
    node = models.ForeignKey('openode.Node', related_name='thread_categories')
    name = models.CharField(max_length=1000)

    class Meta:
        app_label = 'openode'

    def __unicode__(self):
        return self.name

    def has_update_perm(self, user):
        return user.has_openode_perm("document_directory_update", self.node)

    def has_delete_perm(self, user):
        return user.has_openode_perm("document_directory_delete", self.node)


class Thread(models.Model):
    SUMMARY_CACHE_KEY_TPL = 'thread-question-summary-%d-%s'
    ANSWER_LIST_KEY_TPL = 'thread-answer-list-%d'

    dt_created = models.DateTimeField(auto_now_add=True, verbose_name=_(u"Create date"))
    dt_changed = models.DateTimeField(auto_now=True, verbose_name=_(u"Change date"))

    title = models.CharField(max_length=300)

    tags = models.ManyToManyField('Tag', related_name='threads')
    # groups = models.ManyToManyField(Group, through=ThreadToGroup, related_name='group_threads')
    node = models.ForeignKey(Node, related_name='threads')
    slug = SlugField(
        slug_from='title',
        slug_unique=True,
        max_length=300,
    )
    category = models.ForeignKey(ThreadCategory, null=True, blank=True,
        related_name="threads",
        on_delete=models.CASCADE,  # !!!
        help_text=_('Valid only for document')
    )

    thread_type = models.CharField(max_length='50', choices=const.THREAD_TYPES, default=const.THREAD_TYPE_QUESTION)
    description = models.OneToOneField(
        'Post', related_name='described_thread',
        null=True, blank=True
    )

    is_deleted = models.BooleanField(default=False, db_index=True)

    # Denormalised data, transplanted from Question
    tagnames = models.CharField(max_length=125)
    view_count = models.PositiveIntegerField(default=0)
    followed_count = models.PositiveIntegerField(default=0)
    answer_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(default=datetime.datetime.now)
    last_activity_by = models.ForeignKey(User, related_name='unused_last_active_in_threads', on_delete=models.SET_NULL, null=True, default=None)

    followed_by = models.ManyToManyField(User, through='FollowedThread', related_name='followed_threads')
    subscribed_by = models.ManyToManyField(User, through='SubscribedThread', related_name='subscribed_threads')

    external_access = models.BooleanField(default=False, db_index=True, help_text=_('Valid only for document'))

    closed = models.BooleanField(default=False, db_index=True)
    closed_by = models.ForeignKey(User, null=True, blank=True)  # , related_name='closed_questions')
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.TextField(blank=True, null=True)

    #denormalized data: the core approval of the posts is made
    #in the revisions. In the revisions there is more data about
    #approvals - by whom and when
    approved = models.BooleanField(default=True, db_index=True, help_text=_('Valid only for question'))

    accepted_answer = models.ForeignKey(Post, null=True, blank=True, related_name='+')
    answer_accepted_at = models.DateTimeField(null=True, blank=True)
    added_at = models.DateTimeField(default=datetime.datetime.now)

    #db_column will be removed later
    points = models.IntegerField(default=0, db_column='score')

    objects = ThreadManager()

    class Meta:
        app_label = 'openode'

    def __unicode__(self):
        return self.title

    def delete(self, soft=False, using=None):
        if soft:
            self.is_deleted = True
            self.save()
        else:
            super(Thread, self).delete(using=using)

    def is_discussion(self):
        return self.thread_type == const.THREAD_TYPE_DISCUSSION

    def is_question(self):
        return self.thread_type == const.THREAD_TYPE_QUESTION

    def is_document(self):
        return self.thread_type == const.THREAD_TYPE_DOCUMENT

    #property to support legacy themes in case there are.
    @property
    def score(self):
        return int(self.points)

    @score.setter
    def score(self, number):
        if number:
            self.points = int(number)

    def _main_post(self, refresh=False):
        if refresh and hasattr(self, '_thread_cache'):
            delattr(self, '_thread_cache')
        post = getattr(self, '_thread_cache', None)
        if post:
            return post
        self._thread_cache = Post.objects.get(post_type=self.thread_type, thread=self)
        return self._thread_cache

    def is_author(self, user):
        # TODO: protect for case when main_post is None
        if user is None or user.is_anonymous() or not self._main_post():
            return False
        return (user.pk == self._main_post().author.pk)

    ###################################
    # perms shortcuts
    ###################################

    def has_edit_perm(self, user):
        """
            has user permission for edit thread
        """
        if self.thread_type in (const.THREAD_TYPE_QUESTION, const.THREAD_TYPE_DISCUSSION):
            perm_any = user.has_openode_perm("%s_update_any" % self.thread_type, self)
            perm_mine = user.has_openode_perm("%s_update_mine" % self.thread_type, self)
            return perm_any or (self.is_author(user) and perm_mine)
        else:
            return user.has_openode_perm("%s_update" % self.thread_type, self)

    def has_delete_perm(self, user):
        """
            has user permission for edit thread
        """
        if self.thread_type in (const.THREAD_TYPE_QUESTION, const.THREAD_TYPE_DISCUSSION):
            perm_any = user.has_openode_perm("%s_delete_any" % self.thread_type, self)
            perm_mine = user.has_openode_perm("%s_delete_mine" % self.thread_type, self)
            return perm_any or (self.is_author(user) and perm_mine)
        else:
            return user.has_openode_perm("%s_delete" % self.thread_type, self)

    def has_response_perm(self, user):
        """
            used for checking perms when
                create answer to question
                OR add new post to discussion
        """
        if self.thread_type == const.THREAD_TYPE_QUESTION:
            return user.has_openode_perm("question_answer_create", self)
        elif self.thread_type == const.THREAD_TYPE_DISCUSSION:
            return user.has_openode_perm("discussion_post_create", self)
        else:
            return False

    def can_retag(self, user):
        """
            describe if user is allowed to retag question
        """
        # TODO refactor and user correct permissions
        main_post = self._main_post()
        if main_post.is_question() \
                and not self.closed \
                and user.is_authenticated() \
                and user.has_perm('openode.change_tag') \
                and user.pk in [main_post.author.pk] + list(self.node.node_users.filter(role=const.NODE_USER_ROLE_MANAGER).values_list("user_id", flat=True)) \
                and not user.pk in list(self.node.node_users.filter(role=const.NODE_USER_ROLE_READONLY).values_list("user_id", flat=True)):
            return True
        return False

    ###################################

    def get_absolute_url(self):
        return reverse('thread', kwargs={
            'node_id': self.node.pk,
            'node_slug': self.node.slug,

            'thread_id': self.pk,
            'thread_slug': self.slug,

            'module': self.get_module(),
            }
        )
        # return self._main_post().get_absolute_url(thread=self)
        #question_id = self._main_post().id
        #return reverse('question', args = [question_id]) + slugify(self.title)

    def get_module(self):
        return const.NODE_MODULE_BY_THREAD_TYPE[self.thread_type]

    def get_answer_count(self, user=None):
        """returns answer count depending on who the user is.
        When user groups are enabled and some answers are hidden,
        the answer count to show must be reflected accordingly"""
        return self.get_answers(user).count()

    def get_sharing_info(self, visitor=None):
        """returns a dictionary with abbreviated thread sharing info:
        * users - up to a certain number of users, excluding the visitor
        * groups - up to a certain number of groups
        * more_users_count - remaining count of shared-with users
        * more_groups_count - remaining count of shared-with groups
        """
        shared_users = self.get_users_shared_with(
            max_count=2,  # "visitor" is implicit
            exclude_user=visitor
        )
        organizations = self.organizations
        gorganizations = organizations.all()

        sharing_info = {
            'users': shared_users,
            'organizations': self.get_organizations_shared_with(max_count=3),
            'more_users_count': 0,
            'more_organizations_count': max(0, gorganizations.count() - 3)
        }
        return sharing_info

    # def number_of_unread_posts(self, user):
    #     thread_view = self.viewed.get(user=user)
    #     return thread_view.not_view_count

    def recount_unread_posts(self):
        """
            update ThreadView unread count
        """
        for thread_view in self.viewed.iterator():

            count_qs = self.posts.filter(
                models.Q(added_at__gt=thread_view.last_visit) | models.Q(last_edited_at__gt=thread_view.last_visit)
            )

            thread_view.not_view_comment_count = count_qs.filter(
                post_type="comment"
            ).count()

            thread_view.not_view_post_count = count_qs.filter(
                post_type="answer"
            ).count()

            thread_view.not_view_count = thread_view.not_view_comment_count + thread_view.not_view_post_count

            main_post = self._main_post()

            # add red-ball when main post is changed
            if main_post.dt_changed > thread_view.last_visit:
                thread_view.not_view_count += 1

            dt_to_compare = main_post.last_edited_at or main_post.added_at
            thread_view.main_post_viewed = bool(thread_view.last_visit > dt_to_compare)
            thread_view.save()

    def visit(self, user, force=False, timestamp=None):
        """
            call when user visit thread
        """
        if not (user.is_authenticated() or force):
            return

        if timestamp:
            last_visit = timestamp
        else:
            last_visit = datetime.datetime.now()

        thread_view, created = self.viewed.get_or_create(
            user=user,
            defaults={
                "last_visit": last_visit,
                "main_post_viewed": True,
            }
        )

        if not created:
            thread_view.main_post_viewed = True
            thread_view.last_visit = last_visit
            thread_view.not_view_count = 0
            thread_view.not_view_post_count = 0
            thread_view.not_view_comment_count = 0
            thread_view.save()

        self.node.visit(user, timestamp)


    def render_last_changed(self):
        return get_template('snippets/thread_last_changed.html').render({"thread": self})

    def get_viewed_unread_count(self, user):
        return self.viewed.filter(user=user).aggregate(s=models.Sum("not_view_count"))["s"] or 0

    def update_followed_count(self):
        #TODO how about deactivated users?
        self.followed_count = FollowedThread.objects.filter(thread=self).count()
        self.save()

    def update_answer_count(self):
        self.answer_count = self.get_answers().count()
        self.save()

    def increase_view_count(self, increment=1):
        qset = Thread.objects.filter(id=self.id)
        qset.update(
            view_count=models.F('view_count') + increment
            )

        # get the new view_count back because other pieces of code relies on such behaviour
        self.view_count = qset.values('view_count')[0]['view_count']

        self.update_summary_html()  # regenerate question/thread summary html

    def set_closed_status(self, closed, closed_by, closed_at, close_reason):
        self.closed = closed
        self.closed_by = closed_by
        self.closed_at = closed_at
        self.close_reason = close_reason
        self.save()
        self.invalidate_cached_data()

    def set_accepted_answer(self, answer, timestamp):
        if answer and answer.thread != self:
            raise ValueError("Answer doesn't belong to this thread")
        self.accepted_answer = answer
        self.answer_accepted_at = timestamp
        self.save()

    def set_last_activity(self, last_activity_at, last_activity_by):
        self.last_activity_at = last_activity_at
        self.last_activity_by = last_activity_by
        self.save()
        ####################################################################
        self.update_summary_html()  # regenerate question/thread summary html
        ####################################################################

    def get_document(self, with_deleted=False):

        if with_deleted:
            qs = self.documents.all()
        else:
            qs = self.documents.public()

        doc = qs[:1]
        if doc:
            return doc[0]
        return None

    def exists_document(self):
        return self.documents.public().exists()

    def get_tag_names(self):
        "Creates a list of Tag names from the ``tagnames`` attribute."
        if self.tagnames.strip() == '':
            return list()
        else:
            return self.tagnames.split(u' ')

    def get_tags(self):
        """
            TODO: inject this method with loading from cache
        """
        return self.tags.all()

    def get_title(self, style='plain'):
        # allowed styles are: 'html', 'plain'
        if not style in ('html', 'plain'):
            raise ValueError('Unknown style, valid values are \'plain\' (default) and \'html\'.')

        HTML_TPL = u'<span class="status">%s</span>'
        TXT_TPL = u'[%s]'

        status_list = []

        if style == 'plain':
            if self.is_deleted or (self._main_post() and self._main_post().deleted):
                status_list.append(TXT_TPL % const.POST_STATUS['deleted'])
            elif self.closed:
                if self.accepted_answer_id:
                    status_list.append(TXT_TPL % const.POST_STATUS['solved'])
                else:
                    status_list.append(TXT_TPL % const.POST_STATUS['closed'])

        if style == 'html':
            if self.is_deleted or (self._main_post() and self._main_post().deleted):
                status_list.append(HTML_TPL % const.POST_STATUS['deleted'])
            elif self.closed:
                if self.accepted_answer_id:
                    status_list.append(HTML_TPL % const.POST_STATUS['solved'])
                else:
                    status_list.append(HTML_TPL % const.POST_STATUS['closed'])

        style_str = u' '.join(status_list)

        if style_str:
            return u'%s %s' % (escape(self.title), style_str)

        return escape(self.title)

    def format_for_email(self, user=None):
        """experimental function: output entire thread for email"""
        main_post, answers, junk, published_ans_ids = self.get_cached_post_data(user=user)
        output = main_post.format_for_email_as_subthread()
        if answers:
            answer_heading = ungettext(
                                    '%(count)d answer:',
                                    '%(count)d answers:',
                                    len(answers)
                                ) % {'count': len(answers)}
            output += '<p>%s</p>' % answer_heading
            for answer in answers:
                output += answer.format_for_email_as_subthread()
        return output

    def get_answers_by_user(self, user):
        """regardless - deleted or not"""
        return self.posts.filter(post_type='answer', author=user, deleted=False)

    def has_answer_by_user(self, user):
        #use len to cache the queryset
        return len(self.get_answers_by_user(user)) > 0

    def requires_response_moderation(self, author):
        """true, if answers by a given author must be moderated
        before publishing to the enquirers"""
        author_organizations = author.get_organizations()
        thread_organizations = self.get_organizations_shared_with()
        for organization in set(author_organizations) & set(thread_organizations):
            if organization.moderate_answers_to_enquirers:
                return True

        return False

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.get_tag_names()])

    def all_answers(self):
        return self.posts.get_answers()

    def get_answers(self, user=None):
        """returns query set for answers to this question
        that may be shown to the given user
        """
        if user is None or user.is_anonymous():
            return self.posts.get_answers().filter(deleted=False)
        else:
            return self.posts.get_answers(
                                    user=user
                                ).filter(deleted=False)
            #    return self.posts.get_answers(user=user).filter(
            #                models.Q(deleted=False) \
            #                | models.Q(author=user) \
            #                | models.Q(deleted_by=user)
            #            )
            #we used to show deleted answers to admins,
            #users who deleted those answers and answer owners
            #but later decided to not show deleted answers at all
            #because it makes caching the post lists for thread easier
            #if user.is_administrator() or user.is_moderator():
            #    return self.posts.get_answers(user=user)
            #else:
            #    return self.posts.get_answers(user=user).filter(
            #                models.Q(deleted=False) \
            #                | models.Q(author=user) \
            #                | models.Q(deleted_by=user)
            #            )

    def invalidate_cached_thread_content_fragment(self):
        cache.cache.delete(self.SUMMARY_CACHE_KEY_TPL % (self.id, get_language()))

    def get_post_data_cache_key(self, sort_method=None):
        return 'thread-data-%s-%s' % (self.id, sort_method)

    def invalidate_cached_post_data(self):
        """needs to be called when anything notable
        changes in the post data - on votes, adding,
        deleting, editing content"""
        #we can call delete_many() here if using Django > 1.2
        for sort_method in const.ANSWER_SORT_METHODS:
            cache.cache.delete(self.get_post_data_cache_key(sort_method))

    def invalidate_cached_data(self):
        self.invalidate_cached_post_data()
        #self.invalidate_cached_thread_content_fragment()
        self.update_summary_html()

    def get_default_sort_method(self):
        if self.is_question():
            return 'votes'
        elif self.is_discussion():
            return 'latest'
        else:
            return 'votes'

    def get_cached_post_data(self, user=None, sort_method=None, qs=None):
        """returns cached post data, as calculated by
        the method get_post_data()"""
        #temporary plug: bypass cache where groups are enabled
        return self.get_post_data(sort_method=sort_method, user=user, qs=qs)

        #TODO

        # key = self.get_post_data_cache_key(sort_method)
        # post_data = cache.cache.get(key)
        # if not post_data:
        #     post_data = self.get_post_data(sort_method)
        #     cache.cache.set(key, post_data, const.LONG_TIME)
        # return post_data

    def get_post_data(self, sort_method=None, user=None, qs=None):
        """returns question, answers as list and a list of post ids
        for the given thread, and the list of published post ids
        (four values)
        the returned posts are pre-stuffed with the comments
        all (both posts and the comments sorted in the correct
        order)
        """
        if qs is None:
            thread_posts = self.posts.all()
        else:
            thread_posts = qs


        if sort_method is None:
            sort_method = self.get_default_sort_method()

        thread_posts = thread_posts.order_by({
                'latest': '-added_at',
                'oldest': 'added_at',
                'votes': '-points'
            }[sort_method])
        print thread_posts.query

        #1) collect question, answer and comment posts and list of post id's
        answers = list()
        post_map = dict()
        comment_map = dict()
        post_to_author = dict()
        question_post = None
        thread_types = [tt[0] for tt in const.THREAD_TYPES]
        for post in thread_posts:
            #pass through only deleted question posts
            if post.deleted and post.post_type not in thread_types:
                continue

            post_to_author[post.id] = post.author_id

            if post.is_answer():
                answers.append(post)
                post_map[post.id] = post
            elif post.is_comment():
                if post.parent_id not in comment_map:
                    comment_map[post.parent_id] = list()
                comment_map[post.parent_id].append(post)
            elif post.post_type in thread_types:
                assert(question_post == None)
                post_map[post.id] = post
                question_post = post

        #2) sort comments in the temporal order
        for comment_list in comment_map.values():
            comment_list.sort(key=operator.attrgetter('added_at'))

        #3) attach comments to question and the answers
        for post_id, comment_list in comment_map.items():
            try:
                post_map[post_id].set_cached_comments(comment_list)
            except KeyError:
                pass  # comment to deleted answer - don't want it

        if self.has_accepted_answer() and self.accepted_answer.deleted == False:
            #Put the accepted answer to front
            #the second check is for the case when accepted answer is deleted
            if self.accepted_answer_id in post_map:
                accepted_answer = post_map[self.accepted_answer_id]
                answers.remove(accepted_answer)
                answers.insert(0, accepted_answer)

        return (question_post, answers, post_to_author)

    def has_accepted_answer(self):
        return self.accepted_answer_id != None

    def get_similarity(self, other_thread=None):
        """return number of tags in the other question
        that overlap with the current question (self)
        """
        my_tags = set(self.get_tag_names())
        others_tags = set(other_thread.get_tag_names())
        return len(my_tags & others_tags)

    def get_similar_threads(self):
        """
        Get 10 similar threads for given one.
        Threads with the individual tags will be added to list if above questions are not full.

        This function has a limitation that it will
        retrieve only 100 records then select 10 most similar
        from that list as querying entire database may
        be very expensive - this function will benefit from
        some sort of optimization
        """

        def get_data():
            # todo: code in this function would be simpler if
            # we had main_post id denormalized on the thread
            tags_list = self.get_tag_names()
            similar_threads = Thread.objects.filter(
                                        tags__name__in=tags_list
                                    ).exclude(
                                        id=self.id
                                    ).exclude(
                                        posts__post_type__in=('question', 'discussion'),
                                        posts__deleted=True
                                    ).filter(
                                        is_deleted=False
                                    ).distinct()[:100]
            similar_threads = list(similar_threads)

            for thread in similar_threads:
                thread.similarity = self.get_similarity(other_thread=thread)

            similar_threads.sort(key=operator.attrgetter('similarity'), reverse=True)
            similar_threads = similar_threads[:10]

            # Denormalize main_posts to speed up template rendering
            # todo: just denormalize main_post_id on the thread!
            thread_map = dict([(thread.id, thread) for thread in similar_threads])
            main_posts = Post.objects.get_questions_and_discussions()
            main_posts = main_posts.select_related('thread').filter(thread__in=similar_threads)
            for mp in main_posts:
                thread_map[mp.thread_id].main_post_denorm = mp

            # Postprocess data for the final output
            result = list()
            for thread in similar_threads:
                result.append({'url': thread.get_absolute_url(), 'title': thread.get_title()})

            return result

        def get_cached_data():
            """similar thread data will expire
            with the default expiration delay
            """
            key = 'similar-threads-%s' % self.id
            data = cache.cache.get(key)
            if data is None:
                data = get_data()
                cache.cache.set(key, data)
            return data

        return LazyList(get_cached_data)

    # def remove_author_anonymity(self):
    #     """removes anonymous flag from the question
    #     and all its revisions
    #     the function calls update method to make sure that
    #     signals are not called
    #     """
    #     #note: see note for the is_anonymous field
    #     #it is important that update method is called - not save,
    #     #because we do not want the signals to fire here
    #     thread_question = self._main_post()
    #     Post.objects.filter(id=thread_question.id).update(is_anonymous=False)
    #     thread_question.revisions.all().update(is_anonymous=False)

    def is_followed_by(self, user=None):
        """True if thread is followed by user"""
        if user and user.is_authenticated():
            return self.followed_by.filter(id=user.id).count() > 0
        return False

    def is_subscribed_by(self, user=None):
        """True if thread is subscribed by user"""
        if user and user.is_authenticated():
            return self.subscribed_by.filter(id=user.id).count() > 0
        return False

    def remove_tags_by_names(self, tagnames):
        """removes tags from thread by names"""
        removed_tags = list()
        for tag in self.tags.all():
            if tag.name in tagnames:
                tag.used_count -= 1
                removed_tags.append(tag)
        self.tags.remove(*removed_tags)
        return removed_tags

    def update_tags(self, tagnames=None, user=None, timestamp=None):
        """
        Updates Tag associations for a thread to match the given
        tagname string.
        When tags are removed and their use count hits 0 - the tag is
        automatically deleted.
        When an added tag does not exist - it is created
        If tag moderation is on - new tags are placed on the queue

        Tag use counts are recalculated
        A signal tags updated is sent

        *IMPORTANT*: self._main_post() has to
        exist when update_tags() is called!
        """
        if tagnames.strip() == '':
            return

        previous_tags = list(self.tags.filter(status=Tag.STATUS_ACCEPTED))

        ordered_updated_tagnames = [t for t in tagnames.strip().split(' ')]

        previous_tagnames = set([tag.name for tag in previous_tags])
        updated_tagnames = set(ordered_updated_tagnames)
        removed_tagnames = previous_tagnames - updated_tagnames

        #remove tags from the question's tags many2many relation
        #used_count values are decremented on all tags
        removed_tags = self.remove_tags_by_names(removed_tagnames)

        #modified tags go on to recounting their use
        #todo - this can actually be done asynchronously - not so important
        modified_tags, unused_tags = separate_unused_tags(removed_tags)

        delete_tags(unused_tags)  # tags with used_count == 0 are deleted
        modified_tags = removed_tags

        #add new tags to the relation
        added_tagnames = updated_tagnames - previous_tagnames

        if added_tagnames:
            #find reused tags
            reused_tags, new_tagnames = get_tags_by_names(added_tagnames)
            reused_tags.mark_undeleted()

            added_tags = list(reused_tags)
            #tag moderation is in the call below
            created_tags = Tag.objects.create_in_bulk(
                                        tag_names=new_tagnames,
                                        user=user
                                    )

            added_tags.extend(created_tags)
            #todo: not nice that assignment of added_tags is way above
            self.tags.add(*added_tags)
            modified_tags.extend(added_tags)
        else:
            added_tags = Tag.objects.none()

        #Save denormalized tag names on thread. Preserve order from user input.
        accepted_added_tags = filter_accepted_tags(added_tags)
        added_tagnames = set([tag.name for tag in accepted_added_tags])
        final_tagnames = (previous_tagnames - removed_tagnames) | added_tagnames
        ordered_final_tagnames = list()
        for tagname in ordered_updated_tagnames:
            if tagname in final_tagnames:
                ordered_final_tagnames.append(tagname)

        self.tagnames = ' '.join(ordered_final_tagnames)
        self.save()  # need to save here?

        #todo: factor out - tell author about suggested tags
        suggested_tags = filter_suggested_tags(added_tags)
        if len(suggested_tags) > 0:
            #1) notify author that the tag is going to be moderated
            #todo: factor this out
            if len(suggested_tags) == 1:
                msg = _(
                    'Tag %s is new and will be submitted for the '
                    'moderators approval'
                ) % suggested_tags[0].name
            else:
                msg = _(
                    'Tags %s are new and will be submitted for the '
                    'moderators approval'
                ) % ', '.join([tag.name for tag in suggested_tags])
            user.message_set.create(message=msg)
            #2) todo: notify moderators about newly suggested tags

        ####################################################################
        self.update_summary_html()  # regenerate question/thread summary html
        ####################################################################
        #if there are any modified tags, update their use counts
        modified_tags = set(modified_tags) - set(unused_tags)
        if modified_tags:
            Tag.objects.update_use_counts(modified_tags)
            signals.tags_updated.send(None,
                                thread=self,
                                tags=modified_tags,
                                user=user,
                                timestamp=timestamp
                            )
            return True

        return False

    def add_tag(self, user=None, timestamp=None, tag_name=None, silent=False):
        """adds one tag to thread"""
        tag_names = self.get_tag_names()
        if tag_name in tag_names:
            return
        tag_names.append(tag_name)

        self.retag(
            retagged_by=user,
            retagged_at=timestamp,
            tagnames=' '.join(tag_names),
            silent=silent
        )

    def retag(self, retagged_by=None, retagged_at=None, tagnames=None, silent=False):
        """changes thread tags"""
        if None in (retagged_by, retagged_at, tagnames):
            raise Exception('arguments retagged_at, retagged_by and tagnames are required')

        if len(tagnames) > 125:  # todo: remove magic number!!!
            raise django_exceptions.ValidationError('tagnames value too long')

        main_post = self._main_post()

        self.tagnames = tagnames.strip()
        self.save()

        # Update the Question itself
        if silent == False:
            # main_post.last_edited_at = retagged_at
            #main_post.thread.last_activity_at = retagged_at
            main_post.last_edited_by = retagged_by
            #main_post.thread.last_activity_by = retagged_by
            main_post.save()

        # Update the Thread's tag associations
        self.update_tags(tagnames=tagnames, user=retagged_by, timestamp=retagged_at)

        # Create a new revision
        latest_revision = main_post.get_latest_revision()
        PostRevision.objects.create(
            post=main_post,
            title=latest_revision.title,
            author=retagged_by,
            revised_at=retagged_at,
            tagnames=tagnames,
            summary=const.POST_STATUS['retagged'],
            text=latest_revision.text
        )

    # def has_followed_by_user(self, user):
    #     if not user.is_authenticated():
    #         return False

    #     return FollowedThread.objects.filter(thread=self, user=user).exists()

    def get_last_update_info(self):
        posts = list(self.posts.select_related('author', 'last_edited_by'))

        last_updated_at = posts[0].added_at
        last_updated_by = posts[0].author

        for post in posts:
            last_updated_at, last_updated_by = max((last_updated_at, last_updated_by), (post.added_at, post.author))
            if post.last_edited_at:
                last_updated_at, last_updated_by = max((last_updated_at, last_updated_by), (post.last_edited_at, post.last_edited_by))

        return last_updated_at, last_updated_by

    def get_summary_html(self, search_state=None, visitor=None, with_breadcrumbs=False):
        html = self.get_cached_summary_html(visitor)
        if not html:
            html = self.update_summary_html(visitor, with_breadcrumbs=with_breadcrumbs)

        # todo: this work may be pushed onto javascript we post-process tag names
        # in the snippet so that tag urls match the search state
        # use `<<<` and `>>>` because they cannot be confused with user input
        # - if user accidentialy types <<<tag-name>>> into question title or body,
        # then in html it'll become escaped like this: &lt;&lt;&lt;tag-name&gt;&gt;&gt;
        regex = re.compile(
            r'<<<(%s)>>>' % const.TAG_REGEX_BARE,
            re.UNICODE
        )

        if search_state is None:
            search_state = DummySearchState()

        if not html:
            return "TODO"

        while True:
            match = regex.search(html)
            if not match:
                break
            seq = match.group(0)  # e.g "<<<my-tag>>>"
            tag = match.group(1)  # e.g "my-tag"
            full_url = search_state.add_tag(tag).full_url()
            html = html.replace(seq, full_url)

        return html

    def get_cached_summary_html(self, visitor=None):
        #todo: remove this plug by adding cached foreign user group
        #parameter to the key. Now with groups on caching is turned off
        #parameter visitor is there to get summary out by the user groups
        return None

        return cache.cache.get(self.SUMMARY_CACHE_KEY_TPL % (self.id, get_language()))

    ###################################

    def get_thread_view(self, user):
        """
            return ThreadView for user or None if no ThreadView exists.
        """
        thread_view = None
        if user and user.is_authenticated():
            try:
                thread_view = self.viewed.get(user=user)
            except ThreadView.DoesNotExist:
                pass
        return thread_view

    def has_unread_main_post(self, thread_view, user):
        """
            unread main post without answers
        """
        if (user and user.is_anonymous()) or self.is_deleted:
            return False

        if (not thread_view) or (not thread_view.main_post_viewed):
            return True

        return False

    def has_unread_main_post_for_user(self, user):
        return self.has_unread_main_post(
            self.get_thread_view(user),
            user
        )

    def has_unread_posts(self, thread_view, user):
        """
            unread answers without main post
        """
        if (user and user.is_anonymous()) or self.is_deleted:
            return False

        if (thread_view is None):
            return False
        elif (thread_view.has_unread_posts()):
            return True

        return False

    def has_unread_posts_for_user(self, user):
        return self.has_unread_posts(
            self.get_thread_view(user),
            user
        )

    def update_summary_html(self, visitor=None, with_breadcrumbs=False):
        #todo: it is quite wrong that visitor is an argument here
        #because we do not include any visitor-related info in the cache key
        #ideally cache should be shareable between users, so straight up
        #using the user id for cache is wrong, we could use group
        #memberships, but in that case we'd need to be more careful with
        #cache invalidation
        context = {
            'thread': self,
            #fetch new question post to make sure we're up-to-date
            'main_post': self._main_post(refresh=True),
            'search_state': DummySearchState(),
            'visitor': visitor,
        }

        thread_view = self.get_thread_view(visitor)

        # display_new = self.is_thread_view_new(thread_view=thread_view)

        context.update({
            "thread_view": thread_view,
            "thread_is_unread": thread_view.main_post_viewed if thread_view else False,
            "has_unread_posts": self.has_unread_posts(thread_view, visitor),
            "has_unread_main_post": self.has_unread_main_post(thread_view, visitor),
            "with_breadcrumbs": with_breadcrumbs
        })

        if self.is_question():
            template = "thread_summary_question.html"
        elif self.is_discussion():
            template = "thread_summary_discussion.html"
        elif self.is_document():
            template = "thread_summary_document.html"
            # return  # TODO?
        else:
            raise NotImplementedError()

        html = get_template('widgets/%s' % template).render(context)
        # INFO: Timeout is set to 30 days:
        # * timeout=0/None is not a reliable cross-backend way to set infinite timeout
        # * We probably don't need to pollute the cache with threads older than 30 days
        # * Additionally, Memcached treats timeouts > 30day as dates (https://code.djangoproject.com/browser/django/tags/releases/1.3/django/core/cache/backends/memcached.py#L36),
        #   which probably doesn't break anything but if we can stick to 30 days then let's stick to it
        cache.cache.set(
            self.SUMMARY_CACHE_KEY_TPL % (self.id, get_language()),
            html,
            timeout=const.LONG_TIME
        )
        return html

    def summary_html_cached(self):
        key = self.SUMMARY_CACHE_KEY_TPL % (self.id, get_language())
        return key in cache.cache


class ThreadView(models.Model):
    """
        user vs. thread
    """
    thread = models.ForeignKey(Thread, related_name='viewed')
    user = models.ForeignKey(User, related_name='thread_views')
    last_visit = models.DateTimeField()

    # count of posts not viewed since last visit
    not_view_count = models.PositiveIntegerField(default=0)

    main_post_viewed = models.BooleanField(default=False)
    not_view_post_count = models.PositiveIntegerField(default=0)  # answers, discussion, ...
    not_view_comment_count = models.PositiveIntegerField(default=0)  # only comments

    class Meta:
        app_label = 'openode'
        unique_together = ("thread", "user")

    def __unicode__(self):
        return '[%s] viewed at %s' % (self.user, self.last_visit)

    def not_view_sum_count(self):
        return self.not_view_post_count + self.not_view_comment_count

    def has_unread_posts(self):
        """
            comments + posts
        """
        return bool(self.not_view_count)


class FollowedThread(models.Model):
    """A followed Question of a User."""
    thread = models.ForeignKey(Thread, related_name='thread_following_users')
    user = models.ForeignKey(User, related_name='user_followed_threads')

    last_visit = models.DateTimeField(default=datetime.datetime.now)
    added_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'openode'
        db_table = u'followed_thread'

    def __unicode__(self):
        return '[%s] followed at %s' % (self.user, self.added_at)


class SubscribedThread(models.Model):
    """A followed Question of a User."""
    thread = models.ForeignKey(Thread)
    user = models.ForeignKey(User, related_name='user_subscribed_threads')

    added_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'openode'
        db_table = u'subscribed_thread'

    def __unicode__(self):
        return '[%s] subscribed at %s' % (self.user, self.added_at)


class DraftQuestion(models.Model):
    """Provides space to solve unpublished draft
    questions. Contents is used to populate the Ask form.
    """
    author = models.ForeignKey(User)
    title = models.CharField(max_length=300, null=True)
    text = models.TextField(null=True)
    tagnames = models.CharField(max_length=125, null=True)

    class Meta:
        app_label = 'openode'


class AnonymousQuestion(DraftContent):
    """question that was asked before logging in
    maybe the name is a little misleading, the user still
    may or may not want to stay anonymous after the question
    is published
    """
    title = models.CharField(max_length=300)
    tagnames = models.CharField(max_length=125)
    node = models.ForeignKey('Node')
    thread_type = models.CharField(max_length='50', choices=const.THREAD_TYPES, default=const.THREAD_TYPE_QUESTION)

    def publish(self, user):
        added_at = datetime.datetime.now()
        #todo: wrong - use User.post_thread() instead
        Thread.objects.create_new(
            title=self.title,
            added_at=added_at,
            author=user,
            tagnames=self.tagnames,
            text=self.text,
            thread_type=const.THREAD_TYPE_QUESTION
        )
        self.delete()

################################################################################
################################################################################


class AttachmentFile(models.Model):

    uuid = models.CharField(max_length=40, unique=True, editable=False)

    class Meta:
        app_label = 'openode'
        abstract = True

    def save(self, *args, **kwargs):
        """
            TODO
        """
        if not self.uuid:
            self.uuid = str(uuid4())[:8]
        return super(AttachmentFile, self).save(*args, **kwargs)

#######################################


class AttachmentFileNode(AttachmentFile):

    class Meta:
        app_label = 'openode'
        db_table = "openode_attachmentfilenode"

    def get_path(self):
        return "/".join([
            self.uuid[:2],
            self.uuid,
        ])

    def upload_to_fx(self, original_name):
        return "/".join([
            self.get_path(),
            sanitize_file_name(original_name),
        ])

    file_data = models.FileField(
        upload_to=upload_to_fx,
        storage=FileSystemStorage(
            location=settings.WYSIWYG_NODE_ROOT,
            base_url=settings.WYSIWYG_NODE_URL
        ),
        max_length=512,
        blank=True,
    )
    node = models.ForeignKey("openode.Node", null=False, related_name='attachment_files', verbose_name='Node')

#######################################


class AttachmentFileThread(AttachmentFile):

    class Meta:
        app_label = 'openode'

    def get_path(self):
        return "/".join([
            self.uuid[:2],
            self.uuid,
        ])

    def upload_to_fx(self, original_name):
        return "/".join([
            self.get_path(),
            sanitize_file_name(original_name),
        ])

    file_data = models.FileField(
        upload_to=upload_to_fx,
        storage=FileSystemStorage(
            location=settings.WYSIWYG_THREAD_ROOT,
            base_url=settings.WYSIWYG_THREAD_URL
        ),
        max_length=512,
        blank=True,
    )
    thread = models.ForeignKey("openode.Thread", null=False, related_name='attachment_files', verbose_name='Node')

################################################################################
################################################################################

from django.db.models.signals import post_save


def update_latest(*args, **kwargs):
    """
        update latest activity by latest updated node's thread
    """
    thread = kwargs["instance"]
    thread.node.update_latest()


def log_thread_save(sender, **kwargs):
    thread = kwargs["instance"]
    logger = logging.getLogger('thread')
    logger.info("Thread save: %s" % repr({
        "pk": thread.pk,
        "title": thread.title,
        "user": thread.last_activity_by_id,
        "node": thread.node_id if thread.node else None,
        "thread_type": thread.thread_type,
        "created": kwargs["created"]
    }))


post_save.connect(update_latest, sender=Thread)
post_save.connect(log_thread_save, sender=Thread)
