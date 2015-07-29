# -*- coding: utf-8 -*-

from collections import defaultdict
import datetime
import operator
import cgi
import logging

# from django.utils.html import strip_tags
from django.contrib.sitemaps import ping_google
from django.utils import html
from django.conf import settings
from django.contrib.auth.models import User
from django.core import urlresolvers
from django.db import models
from django.utils import html as html_utils
from django.utils.translation import ugettext as _
# from django.utils.translation import ungettext
# from django.utils.http import urlquote as django_urlquote
from django.core import exceptions as django_exceptions
from django.core import cache
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType

import openode

from openode.utils.slug import slugify
from openode import const
from openode.models.user import Activity
from openode.models.user import EmailFeedSetting
# from openode.models.user import Organization
from openode.models.user import OrganizationMembership
# from openode.models.tag import Tag
from openode.models.tag import MarkedTag

from openode.models.tag import tags_match_some_wildcard
from openode.conf import settings as openode_settings
from openode import exceptions
from openode.utils.html import bleach_html
from openode.models.base import BaseQuerySetManager, DraftContent

from openode.utils.diff import textDiff as htmldiff
# from openode.search import mysql


class PostQuerySet(models.query.QuerySet):
    """
    Custom query set subclass for :class:`~openode.models.Post`
    """

    def get_by_text_query(self, search_query):
        """returns a query set of questions,
        matching the full text query
        """
        return self.filter(
            models.Q(thread__title__icontains=search_query) \
            | models.Q(text__icontains=search_query) \
            | models.Q(thread__tagnames=search_query) \
            | models.Q(thread__posts__text__icontains=search_query, thread__posts__post_type='answer')
        )
#        #todo - goes to thread - we search whole threads
#        if getattr(settings, 'USE_SPHINX_SEARCH', False):
#            matching_questions = Question.sphinx_search.query(search_query)
#            question_ids = [q.id for q in matching_questions]
#            return Question.objects.filter(deleted = False, id__in = question_ids)
#        if settings.DATABASE_ENGINE == 'mysql' and mysql.supports_full_text_search():
#            return self.filter(
#                models.Q(thread__title__search = search_query)\
#                | models.Q(text__search = search_query)\
#                | models.Q(thread__tagnames__search = search_query)\
#                | models.Q(answers__text__search = search_query)
#            )
#        elif 'postgresql_psycopg2' in openode.get_database_engine_name():
#            rank_clause = "ts_rank(question.text_search_vector, plainto_tsquery(%s))";
#            search_query = '&'.join(search_query.split())
#            extra_params = (search_query,)
#            extra_kwargs = {
#                'select': {'relevance': rank_clause},
#                'where': ['text_search_vector @@ plainto_tsquery(%s)'],
#                'params': extra_params,
#                'select_params': extra_params,
#                }
#            return self.extra(**extra_kwargs)
#        else:
#            #fallback to dumb title match search
#            return self.filter(thread__title__icontains=search_query)

    def added_between(self, start, end):
        """questions added between ``start`` and ``end`` timestamps"""
        #todo: goes to thread
        return self.filter(
            added_at__gt=start
        ).exclude(
            added_at__gt=end
        )

    def get_questions_needing_reminder(self,
                                       user=None,
                                       activity_type=None,
                                       recurrence_delay=None):
        """returns list of questions that need a reminder,
        corresponding the given ``activity_type``
        ``user`` - is the user receiving the reminder
        ``recurrence_delay`` - interval between sending the
        reminders about the same question
        """
        #todo: goes to thread
        # from openode.models import Activity  # avoid circular import
        question_list = list()
        for question in self:
            try:
                activity = Activity.objects.get(
                    user=user,
                    question=question,
                    activity_type=activity_type
                )
                now = datetime.datetime.now()
                if now < activity.active_at + recurrence_delay:
                    continue
            except Activity.DoesNotExist:
                activity = Activity(
                    user=user,
                    question=question,
                    activity_type=activity_type,
                    content_object=question,
                )
            activity.active_at = datetime.datetime.now()
            activity.save()
            question_list.append(question)
        return question_list

    def get_author_list(self, **kwargs):
        #todo: - this is duplication - answer manager also has this method
        #will be gone when models are consolidated
        #note that method get_question_and_answer_contributors is similar in function
        #todo: goes to thread
        authors = set()
        for question in self:
            authors.update(question.get_author_list(**kwargs))
        return list(authors)


class PostManager(BaseQuerySetManager):
    def get_query_set(self):
        return PostQuerySet(self.model)

    def get_questions_and_discussions(self, user=None):
        return self.filter(post_type__in=('question', 'discussion'))

    def get_questions(self, user=None):
        return self.filter(post_type='question')

    def get_discussions(self, user=None):
        return self.filter(post_type='discussion')

    def get_answers(self, user=None):
        """returns query set of answer posts,
        optionally filtered to exclude posts of organizations
        to which user does not belong"""
        return self.filter(post_type='answer')

    def get_comments(self):
        return self.filter(post_type='comment')

    def create_new_description(self, post_type, text=None, author=None):
        return self.create_new(
            None,  # this post type is threadless
            author, datetime.datetime.now(), text, post_type=post_type
            )

    def create_new(self, thread, author, added_at, text, parent=None, email_notify=False, post_type=None, by_email=False, is_published=True):
        # TODO: Some of this code will go to Post.objects.create_new
        assert(post_type in const.POST_TYPES)

        post = Post(post_type=post_type, thread=thread, parent=parent,
            author=author, added_at=added_at, text=text
            )
        # inbox and activity is replaced by follow
        parse_results = post.parse_and_save(author=author)
        # from openode.models import signals
        # signals.post_updated.send(
        #     post=post,
        #     updated_by=author,
        #     newly_mentioned_users=parse_results['newly_mentioned_users'],
        #     timestamp=added_at,
        #     created=True,
        #     diff=parse_results['diff'],
        #     sender=post.__class__
        # )

        post.add_revision(author=author, revised_at=added_at, text=text,
            comment=const.POST_STATUS['default_version'], by_email=by_email
            )
        return post

    #todo: instead of this, have Thread.add_answer()
    def create_new_answer(self, thread, author, added_at, text, email_notify=False, by_email=False):

        answer = self.create_new(thread, author, added_at, text,
            post_type='answer', by_email=by_email,
            is_published=not thread.node.is_question_flow_enabled,
            )

        # question flow - answer
        if thread.node.is_question_flow_enabled:
            if thread.question_flow_interviewee_user == author and \
                thread.question_flow_state == const.QUESTION_FLOW_STATE_SUBMITTED:

                thread.question_flow_state = const.QUESTION_FLOW_STATE_ANSWERED
                thread.save()

        else:
            # set notification/delete
            if email_notify:
                author.subscribe_thread(thread)
            else:
                author.unsubscribe_thread(thread)

            # update thread data
            # todo: this totally belongs to some `Thread` class method
            thread.answer_count += 1
            thread.save()

            # this should be here because it regenerates cached thread summary html
            thread.set_last_activity(last_activity_at=added_at, last_activity_by=author)

        return answer

    def precache_comments(self, for_posts, visitor):
        """
        Fetches comments for given posts, and stores them in post._cached_comments
        Additionally, annotates posts with ``upvoted_by_user`` parameter, if visitor is logged in

        """
        qs = Post.objects.get_comments().filter(parent__in=for_posts).select_related('author')

        if visitor.is_anonymous():
            comments = list(qs.order_by('added_at'))
        else:
            upvoted_by_user = list(qs.filter(votes__user=visitor).distinct())
            not_upvoted_by_user = list(qs.exclude(votes__user=visitor).distinct())

            for c in upvoted_by_user:
                c.upvoted_by_user = 1  # numeric value to maintain compatibility with previous version of this code

            comments = upvoted_by_user + not_upvoted_by_user
            comments.sort(key=operator.attrgetter('added_at'))

        post_map = defaultdict(list)
        for cm in comments:
            post_map[cm.parent_id].append(cm)
        for post in for_posts:
            post.set_cached_comments(post_map[post.id])


class Post(models.Model):

    dt_created = models.DateTimeField(auto_now_add=True, verbose_name=_(u"Create date"))
    dt_changed = models.DateTimeField(auto_now=True, verbose_name=_(u"Change date"))

    post_type = models.CharField(max_length=255, db_index=True)

    parent = models.ForeignKey('Post', blank=True, null=True, related_name='comments')  # Answer or Question for Comment
    thread = models.ForeignKey('Thread', blank=True, null=True, default=None, related_name='posts')

    author = models.ForeignKey(User, related_name='posts')
    added_at = models.DateTimeField(default=datetime.datetime.now)

    #denormalized data: the core approval of the posts is made
    #in the revisions. In the revisions there is more data about
    #approvals - by whom and when

    deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, related_name='deleted_posts')

    points = models.IntegerField(default=0, db_column='score')
    vote_up_count = models.IntegerField(default=0)
    vote_down_count = models.IntegerField(default=0)

    comment_count = models.PositiveIntegerField(default=0)
    offensive_flag_count = models.SmallIntegerField(default=0)

    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_posts')

    html = models.TextField(null=True)  # html rendition of the latest revision
    text = models.TextField(null=True)  # denormalized copy of latest revision

    # Denormalised data
    summary = models.TextField(null=True)

    question_flow_is_published = models.BooleanField(default=True, db_index=True, verbose_name=_("Is post published?"))

    #note: anonymity here applies to question only, but
    #the field will still go to thread
    #maybe we should rename it to is_question_anonymous
    #we might have to duplicate the is_anonymous on the Post,
    #if we are to allow anonymous answers
    #the reason is that the title and tags belong to thread,
    #but the question body to Post

    objects = PostManager()

    class Meta:
        app_label = 'openode'
        db_table = 'openode_post'

    #property to support legacy themes in case there are.
    @property
    def score(self):
        return int(self.points)

    @score.setter
    def score(self, number):
        if number:
            self.points = int(number)

    def parse_post_text(self):
        """typically post has a field to store raw source text
        in comment it is called .comment, in Question and Answer it is
        called .text
        also there is another field called .html (consistent across models)
        so the goal of this function is to render raw text into .html
        and extract any metadata given stored in source (currently
        this metadata is limited by twitter style @mentions
        but there may be more in the future

        function returns a dictionary with the following keys
        html
        newly_mentioned_users - list of <User> objects
        removed_mentions - list of mention <Activity> objects - for removed ones
        """

        text = self.text

        if self.post_type in const.POST_TYPES:
            text = bleach_html(text)
        else:
            raise NotImplementedError

        # DEPRECATED
        # if _escape_html:
        #     text = cgi.escape(text)

        # if _urlize:
        #     text = html.urlize(text)

        # if _use_markdown:
        #     text = bleach_html(text)

        #todo, add markdown parser call conditional on
        #self.use_markdown flag
        post_html = text
        mentioned_authors = list()
        removed_mentions = list()
        # DEPRECATED mentioned users
        # if '@' in text:
        #     op = self.get_origin_post()
        #     anticipated_authors = op.get_author_list(
        #         include_comments=True,
        #         recursive=True
        #     )

        #     #extra_name_seeds = markup.extract_mentioned_name_seeds(text)
        #     extra_name_seeds = []
        #     extra_authors = set()
        #     for name_seed in extra_name_seeds:
        #         extra_authors.update(
        #             User.objects.filter(username__istartswith=name_seed)
        #         )

        #     #it is important to preserve order here so that authors of post
        #     #get mentioned first
        #     anticipated_authors += list(extra_authors)

        #     # mentioned_authors, post_html = markup.mentionize_text(
        #     #     text,
        #     #     anticipated_authors
        #     # )

        #     #find mentions that were removed and identify any previously
        #     #entered mentions so that we can send alerts on only new ones
        #     # from openode.models.user import Activity
        #     if self.pk is not None:
        #         #only look for previous mentions if post was already saved before
        #         prev_mention_qs = Activity.objects.get_mentions(
        #             mentioned_in=self
        #         )
        #         new_set = set(mentioned_authors)
        #         for prev_mention in prev_mention_qs:

        #             user = prev_mention.get_mentioned_user()
        #             if user is None:
        #                 continue
        #             if user in new_set:
        #                 #don't report mention twice
        #                 new_set.remove(user)
        #             else:
        #                 removed_mentions.append(prev_mention)
        #         mentioned_authors = list(new_set)

        data = {
            'html': post_html,
            'newly_mentioned_users': mentioned_authors,
            'removed_mentions': removed_mentions,
            }
        return data

    ###################################
    # perms shortcuts
    ###################################

    def has_edit_perm(self, user):
        if not self.thread or not user or user.is_anonymous():
            return False

        if self.thread.thread_type == "discussion":
            key = "%s_post_update" % (self.thread.thread_type)
        else:
            key = "%s_%s_update" % (self.thread.thread_type, self.post_type)

        perm_any = user.has_openode_perm("%s_any" % key, self.thread)
        perm_mine = user.has_openode_perm("%s_mine" % key, self.thread)

        return perm_any or ((self.author.pk == user.pk) and perm_mine)

    def has_delete_perm(self, user):
        if not self.thread or not user or user.is_anonymous():
            return False

        if self.thread.thread_type == "discussion":
            if self.post_type == "discussion":
                key = "discussion_delete"
            else:
                if self.author == user:
                    key = "discussion_post_delete_mine"
                else:
                    key = "discussion_post_delete_any"
        else:
            key = "%s_%s_delete_any" % (self.thread.thread_type, self.post_type)

        return user.has_openode_perm(key, self.thread)

    ###################################

    #todo: when models are merged, it would be great to remove author parameter
    def parse_and_save(self, author=None, **kwargs):
        """generic method to use with posts to be used prior to saving
        post edit or addition
        """

        assert(author is not None)

        last_revision = self.html
        data = self.parse_post_text()

        self.html = data['html']
        newly_mentioned_users = set(data['newly_mentioned_users']) - set([author])
        removed_mentions = data['removed_mentions']

        #a hack allowing to save denormalized .summary field for questions
        if hasattr(self, 'summary'):
            self.summary = self.get_snippet()

        #delete removed mentions
        for rm in removed_mentions:
            rm.delete()

        # created = self.pk is None

        #this save must precede saving the mention activity
        #because generic relation needs primary key of the related object
        super(self.__class__, self).save(**kwargs)

        if last_revision:
            diff = htmldiff(
                        bleach_html(last_revision),
                        bleach_html(self.html)
                    )
        else:
            diff = bleach_html(self.get_snippet())

        # timestamp = self.get_time_of_last_edit()

        try:
            from openode.conf import settings as openode_settings
            if openode_settings.GOOGLE_SITEMAP_CODE != '':
                ping_google()
        except Exception:
            logging.debug('cannot ping google - did you register with them?')

        return {'diff': diff, 'newly_mentioned_users': newly_mentioned_users}

    def is_discussion(self):
        return self.post_type == const.POST_TYPE_DISCUSSION

    def is_question(self):
        return self.post_type == const.POST_TYPE_QUESTION

    def is_document(self):
        return self.post_type == const.POST_TYPE_DOCUMENT

    def is_answer(self):
        return self.post_type == const.POST_TYPE_THREAD_POST

    def is_comment(self):
        return self.post_type == const.POST_TYPE_COMMENT

    def is_node_description(self):
        return self.post_type == const.POST_TYPE_NODE_DESCRIPTION

    def is_organization_description(self):
        return self.post_type == const.POST_TYPE_ORGANIZATION_DESCRIPTION

    def is_user_description(self):
        return self.post_type == const.POST_TYPE_USER_DESCRIPTION

    def is_reject_reason(self):
        return self.post_type == const.POST_TYPE_REJECT_REASON

    # DEPRECATED
    # def issue_update_notifications(
    #                             self,
    #                             updated_by=None,
    #                             notify_sets=None,
    #                             activity_type=None,
    #                             timestamp=None,
    #                             diff=None
    #                         ):
    #     """Called when a post is updated. Arguments:

    #     * ``notify_sets`` - result of ``Post.get_notify_sets()`` method

    #     The method does two things:

    #     * records "red envelope" recipients of the post
    #     * sends email alerts to all subscribers to the post
    #     """
    #     assert(activity_type is not None)
    #     if diff:
    #         summary = diff
    #     else:
    #         summary = self.get_snippet()

    #     update_activity = Activity(
    #                     user=updated_by,
    #                     active_at=timestamp,
    #                     content_object=self,
    #                     activity_type=activity_type,
    #                     question=self.get_origin_post(),
    #                     summary=summary
    #                 )
    #     update_activity.save()

    #     update_activity.add_recipients(notify_sets['for_inbox'])

    #     #create new mentions (barring the double-adds)
    #     for u in notify_sets['for_mentions'] - notify_sets['for_inbox']:
    #         Activity.objects.create_new_mention(
    #                                 mentioned_whom=u,
    #                                 mentioned_in=self,
    #                                 mentioned_by=updated_by,
    #                                 mentioned_at=timestamp
    #                             )

    #     for user in (notify_sets['for_inbox'] | notify_sets['for_mentions']):
    #         user.update_response_counts()

    #     #shortcircuit if the email alerts are disabled
    #     if openode_settings.ENABLE_EMAIL_ALERTS == False:
    #         return

    #     if not settings.CELERY_ALWAYS_EAGER:
    #         cache_key = 'instant-notification-%d-%d' % (self.thread.id, updated_by.id)
    #         if cache.cache.get(cache_key):
    #             return
    #         cache.cache.set(cache_key, True, settings.NOTIFICATION_DELAY_TIME)

    #     from openode.models import send_instant_notifications_about_activity_in_post
    #     send_instant_notifications_about_activity_in_post.apply_async((
    #                             update_activity,
    #                             self,
    #                             notify_sets['for_email']),
    #                             countdown=settings.NOTIFICATION_DELAY_TIME
    #                         )

    def get_absolute_url(self, no_slug=False, question_post=None, thread=None):
        # from openode.utils.slug import slugify
        #todo: the url generation function is pretty bad -
        #the trailing slash is entered in three places here + in urls.py
        if not hasattr(self, '_thread_cache') and thread:
            self._thread_cache = thread
        if self.is_answer():
            node = self.thread.node
            if not question_post:
                question_post = self.thread._main_post()
            return u'%(base)s?answer=%(id)d#post-id-%(id)d' % {
                'base': urlresolvers.reverse('thread', kwargs={
                        'node_id': node.pk,
                        'node_slug': node.slug,
                        'thread_id': self.thread.id,
                        'thread_slug': self.thread.slug,
                        'module': const.NODE_MODULE_BY_THREAD_TYPE[self.thread.thread_type]
                     }),
                'id': self.id
            }
        elif self.is_question():
            node = self.thread.node
            url = urlresolvers.reverse('thread', kwargs={
                    'node_id': node.pk,
                    'node_slug': node.slug,
                    'thread_id': self.thread.id,
                    'thread_slug': self.thread.slug,
                    'module': const.NODE_MODULE_BY_THREAD_TYPE[self.thread.thread_type]
            })
            # if thread:
            #     url += django_urlquote(slugify(thread.title)) + '/'
            # elif no_slug is False:
            #     url += django_urlquote(self.slug) + '/'
            return url
        elif self.is_discussion():
            node = self.thread.node
            url = urlresolvers.reverse('thread', kwargs={
                    'node_id': node.pk,
                    'node_slug': node.slug,
                    'thread_id': self.thread.id,
                    'thread_slug': self.thread.slug,
                    'module': const.NODE_MODULE_BY_THREAD_TYPE[self.thread.thread_type]
            })
            # if thread:
            #     url += django_urlquote(slugify(thread.title)) + '/'
            # elif no_slug is False:
            #     url += django_urlquote(self.slug) + '/'
            return url
        elif self.is_comment():
            # origin_post = self.get_origin_post()
            node = self.thread.node
            url = urlresolvers.reverse('thread', kwargs={
                    'node_id': node.pk,
                    'node_slug': node.slug,
                    'thread_id': self.thread.id,
                    'thread_slug': self.thread.slug,
                    'module': const.NODE_MODULE_BY_THREAD_TYPE[self.thread.thread_type]
            })
            return '%(url)s?comment=%(id)d#comment-%(id)d' % \
                {'url': url, 'id': self.id}

        elif self.is_document():
            node = self.thread.node
            return urlresolvers.reverse('node_module', args=[node.pk, node.slug, const.NODE_MODULE_LIBRARY])

        raise NotImplementedError

    def delete(self, **kwargs):
        """deletes comment and concomitant response activity
        records, as well as mention records, while preserving
        integrity or response counts for the users
        """
        if self.is_comment():
            #todo: implement a custom delete method on these
            #all this should pack into Activity.responses.filter( somehow ).delete()
            #activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
            #activity_types += (const.TYPE_ACTIVITY_MENTION,)
            #todo: not very good import in models of other models
            #todo: potentially a circular import
            from openode.models.user import Activity
            comment_content_type = ContentType.objects.get_for_model(self)
            activities = Activity.objects.filter(
                                content_type=comment_content_type,
                                object_id=self.id,
                                #activity_type__in = activity_types
                            )

            recipients = set()
            for activity in activities:
                for user in activity.recipients.all():
                    recipients.add(user)

            #activities need to be deleted before the response
            #counts are updated
            activities.delete()

            for user in recipients:
                user.update_response_counts()

        super(Post, self).delete(**kwargs)

    def __unicode__(self):
        if self.is_question() or self.is_discussion():
            return self.thread.title
        elif self.is_answer() or self.is_reject_reason():
            return self.html
        elif self.is_comment():
            return self.text
        elif self.is_node_description():
            return self.text
        elif self.is_document():
            return self.thread.title
        else:
            return self.post_type
        raise NotImplementedError

    def save(self, *args, **kwargs):
        super(Post, self).save(*args, **kwargs)
        if self.is_answer() and 'postgres' in openode.get_database_engine_name():
            #hit the database to trigger update of full text search vector
            self.thread._main_post().save()

    def _get_slug(self):
        if not (self.is_question() or self.is_discussion()):
            raise NotImplementedError
        return slugify(self.thread.title)
    slug = property(_get_slug)

    def get_snippet(self, max_length=120):
        """returns an abbreviated snippet of the content
        """
        return html_utils.strip_tags(self.html)[:max_length] + ' ...'

    def filter_authorized_users(self, candidates):
        """returns list of users who are allowed to see this post"""
        # print "TODO %s method: filter_authorized_users" % (__file__)
        # self.organizations doesn't exist
        return set()

        if len(candidates) == 0:
            return candidates
        #get post organizations
        organizations = list(self.organizations.all())

        if len(organizations) == 0:
            logging.critical('post %d is organizationless' % self.id)
            return list()

        #load organization memberships for the candidates
        memberships = OrganizationMembership.objects.filter(
                                        user__in=candidates,
                                        organization__in=organizations
                                    )
        user_ids = set(memberships.values_list('user__id', flat=True))

        #scan through the user ids and see which are organization members
        filtered_candidates = set()
        for candidate in candidates:
            if candidate.id in user_ids:
                filtered_candidates.add(candidate)

        return filtered_candidates

    def format_for_email(
        self, quote_level=0, is_leaf_post=False, format=None
    ):
        """format post for the output in email,
        if quote_level > 0, the post will be indented that number of times
        todo: move to views?
        """
        from openode.skins.loaders import get_template
        from django.template import Context
        template = get_template('email/quoted_post.html')
        data = {
            'post': self,
            'quote_level': quote_level,
            'is_leaf_post': is_leaf_post,
            'format': format
        }
        return template.render(Context(data))

    def format_for_email_as_parent_thread_summary(self):
        """format for email as summary of parent posts
        all the way to the original question"""
        quote_level = 0
        current_post = self
        output = ''
        while True:
            parent_post = current_post.get_parent_post()
            if parent_post is None:
                break
            quote_level += 1
            """
            output += '<p>'
            output += _(
                'In reply to %(user)s %(post)s of %(date)s'
            ) % {
                'user': parent_post.author.username,
                'post': _(parent_post.post_type),
                'date': parent_post.added_at.strftime(const.DATETIME_FORMAT)
            }
            output += '</p>'
            """
            output += parent_post.format_for_email(
                quote_level=quote_level,
                format='parent_subthread'
            )
            current_post = parent_post
        return output

    def format_for_email_as_subthread(self):
        """outputs question or answer and all it's comments
        returns empty string for all other post types
        """
        from openode.skins.loaders import get_template
        from django.template import Context
        template = get_template('email/post_as_subthread.html')
        return template.render(Context({'post': self}))

    def set_cached_comments(self, comments):
        """caches comments in the lifetime of the object
        does not talk to the actual cache system
        """
        self._cached_comments = comments

        # update comments count when is some different here
        l = len(self._cached_comments)
        if self.comment_count != l:
            self.comment_count = l
            type(self).objects.filter(pk=self.pk).update(comment_count=l)

    def get_cached_comments(self):
        try:
            return self._cached_comments
        except AttributeError:
            self._cached_comments = list()
            return self._cached_comments

    def add_comment(self, comment=None, user=None, added_at=None, by_email=False):
        if added_at is None:
            added_at = datetime.datetime.now()
        if None in (comment, user):
            raise Exception('arguments comment and user are required')

        comment_post = self.__class__.objects.create_new(
            self.thread,
            user,
            added_at,
            comment,
            parent=self,
            post_type='comment',
            by_email=by_email
        )
        self.comment_count = self.comment_count + 1
        self.save()

        #tried to add this to bump updated question
        #in most active list, but it did not work
        #becase delayed email updates would be triggered
        #for cases where user did not subscribe for them
        #
        #need to redo the delayed alert sender
        #
        #origin_post = self.get_origin_post()
        #if origin_post == self:
        #    self.last_activity_at = added_at # WARNING: last_activity_* are now in Thread
        #    self.last_activity_by = user
        #else:
        #    origin_post.last_activity_at = added_at
        #    origin_post.last_activity_by = user
        #    origin_post.save()

        return comment_post

    def get_global_tag_based_subscribers(
            self,
            tag_mark_reason=None,
            subscription_records=None
    ):
        """returns a list of users who either follow or "do not ignore"
        the given set of tags, depending on the tag_mark_reason

        ``subscription_records`` - query set of ``~openode.models.EmailFeedSetting``
        this argument is used to reduce number of database queries
        """
        if tag_mark_reason == 'good':
            email_tag_filter_strategy = const.INCLUDE_INTERESTING
            user_set_getter = User.objects.filter
        elif tag_mark_reason == 'bad':
            email_tag_filter_strategy = const.EXCLUDE_IGNORED
            user_set_getter = User.objects.exclude
        else:
            raise ValueError('Uknown value of tag mark reason %s' % tag_mark_reason)

        #part 1 - find users who follow or not ignore the set of tags
        tag_names = self.get_tag_names()
        tag_selections = MarkedTag.objects.filter(
            tag__name__in=tag_names,
            reason=tag_mark_reason
        )
        subscribers = set(
            user_set_getter(
                tag_selections__in=tag_selections
            ).filter(
                email_tag_filter_strategy=email_tag_filter_strategy,
                notification_subscriptions__in=subscription_records
            )
        )

        #part 2 - find users who follow or not ignore tags via wildcard selections
        #inside there is a potentially time consuming loop
        if openode_settings.USE_WILDCARD_TAGS:
            #todo: fix this
            #this branch will not scale well
            #because we have to loop through the list of users
            #in python
            if tag_mark_reason == 'good':
                empty_wildcard_filter = {'interesting_tags__exact': ''}
                wildcard_tags_attribute = 'interesting_tags'
                update_subscribers = lambda the_set, item: the_set.add(item)
            elif tag_mark_reason == 'bad':
                empty_wildcard_filter = {'ignored_tags__exact': ''}
                wildcard_tags_attribute = 'ignored_tags'
                update_subscribers = lambda the_set, item: the_set.discard(item)

            potential_wildcard_subscribers = User.objects.filter(
                notification_subscriptions__in=subscription_records
            ).filter(
                email_tag_filter_strategy=email_tag_filter_strategy
            ).exclude(
                **empty_wildcard_filter  # need this to limit size of the loop
            )
            for potential_subscriber in potential_wildcard_subscribers:
                wildcard_tags = getattr(
                    potential_subscriber,
                    wildcard_tags_attribute
                ).split(' ')

                if tags_match_some_wildcard(tag_names, wildcard_tags):
                    update_subscribers(subscribers, potential_subscriber)

        return subscribers

    def get_global_instant_notification_subscribers(self):
        """returns a set of subscribers to post according to tag filters
        both - subscribers who ignore tags or who follow only
        specific tags

        this method in turn calls several more specialized
        subscriber retrieval functions
        todo: retrieval of wildcard tag followers ignorers
              won't scale at all
        """
        subscriber_set = set()

        global_subscriptions = EmailFeedSetting.objects.filter(
            feed_type='q_all',
            frequency='i'
        )

        #segment of users who have tag filter turned off
        global_subscribers = User.objects.filter(
            email_tag_filter_strategy=const.INCLUDE_ALL
        )
        subscriber_set.update(global_subscribers)

        #segment of users who want emails on selected questions only
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                subscription_records=global_subscriptions,
                tag_mark_reason='good'
            )
        )

        #segment of users who want to exclude ignored tags
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                subscription_records=global_subscriptions,
                tag_mark_reason='bad'
            )
        )
        return subscriber_set

    def _qa__get_instant_notification_subscribers(
            self,
            potential_subscribers=None,
            mentioned_users=None,
            exclude_list=None,
            ):
        """get list of users who have subscribed to
        receive instant notifications for a given post

        this method works for questions and answers

        Arguments:

        * ``potential_subscribers`` is not used here! todo: why? - clean this out
          parameter is left for the uniformity of the interface
          (Comment method does use it)
          normally these methods would determine the list
          :meth:`~openode.models.question.Question.get_response_recipients`
          :meth:`~openode.models.question.Answer.get_response_recipients`
          - depending on the type of the post
        * ``mentioned_users`` - users, mentioned in the post for the first time
        * ``exclude_list`` - users who must be excluded from the subscription

        Users who receive notifications are:

        * of ``mentioned_users`` - those who subscribe for the instant
          updates on the @name mentions
        * those who follow the parent question
        * global subscribers (any personalized tag filters are applied)
        * author of the question who subscribe to instant updates
          on questions that they asked
        * authors or any answers who subsribe to instant updates
          on the questions which they answered
        """

        subscriber_set = set()

        #1) mention subscribers - common to questions and answers
        if mentioned_users:
            mention_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=mentioned_users,
                feed_type='m_and_c',
                frequency='i'
            )
            subscriber_set.update(mention_subscribers)

        origin_post = self.get_origin_post()

        #2) individually selected - make sure that users
        #are individual subscribers to this question
        # TODO: The line below works only if origin_post is Question !
        selective_subscribers = origin_post.thread.followed_by.all()
        #print 'question followers are ', [s for s in selective_subscribers]
        if selective_subscribers:
            selective_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=selective_subscribers,
                feed_type='q_sel',
                frequency='i'
            )
            subscriber_set.update(selective_subscribers)
            #print 'selective subscribers: ', selective_subscribers

        #3) whole forum subscribers
        global_subscribers = origin_post.get_global_instant_notification_subscribers()
        subscriber_set.update(global_subscribers)

        #4) question asked by me (todo: not "edited_by_me" ???)
        question_author = origin_post.author
        if EmailFeedSetting.objects.filter(
            subscriber=question_author,
            frequency='i',
            feed_type='q_ask'
        ).exists():
            subscriber_set.add(question_author)

        #4) questions answered by me -make sure is that people
        #are authors of the answers to this question
        #todo: replace this with a query set method
        answer_authors = set()
        for answer in origin_post.thread.posts.get_answers().all():
            authors = answer.get_author_list()
            answer_authors.update(authors)

        if answer_authors:
            answer_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=answer_authors,
                frequency='i',
                feed_type='q_ans',
            )
            subscriber_set.update(answer_subscribers)
            #print 'answer subscribers: ', answer_subscribers

        #print 'exclude_list is ', exclude_list
        return subscriber_set - set(exclude_list)

    def _comment__get_instant_notification_subscribers(
                                    self,
                                    potential_subscribers=None,
                                    mentioned_users=None,
                                    exclude_list=None
                                ):
        """get list of users who want instant notifications about comments

        argument potential_subscribers is required as it saves on db hits

        Here is the list of people who will receive the notifications:

        * mentioned users
        * of response receivers
          (see :meth:`~openode.models.meta.Comment.get_response_receivers`) -
          those who subscribe for the instant
          updates on comments and @mentions
        * all who follow the question explicitly
        * all global subscribers
          (tag filtered, and subject to personalized settings)
        """
        #print 'in meta function'
        #print 'potential subscribers: ', potential_subscribers

        subscriber_set = set()

        if potential_subscribers:
            potential_subscribers = set(potential_subscribers)
        else:
            potential_subscribers = set()

        if mentioned_users:
            potential_subscribers.update(mentioned_users)

        if potential_subscribers:
            comment_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                        potential_subscribers=potential_subscribers,
                                        feed_type='m_and_c',
                                        frequency='i'
                                    )
            subscriber_set.update(comment_subscribers)
            #print 'comment subscribers: ', comment_subscribers

        origin_post = self.get_origin_post()
        # TODO: The line below works only if origin_post is Question !
        selective_subscribers = origin_post.thread.followed_by.all()
        if selective_subscribers:
            selective_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                    potential_subscribers=selective_subscribers,
                                    feed_type='q_sel',
                                    frequency='i'
                                )
            for subscriber in selective_subscribers:
                if origin_post.passes_tag_filter_for_user(subscriber):
                    subscriber_set.add(subscriber)

            subscriber_set.update(selective_subscribers)
            #print 'selective subscribers: ', selective_subscribers

        global_subscribers = origin_post.get_global_instant_notification_subscribers()
        #print 'global subscribers: ', global_subscribers

        subscriber_set.update(global_subscribers)

        return subscriber_set - set(exclude_list)

    def get_instant_notification_subscribers(
        self, potential_subscribers=None,
        mentioned_users=None, exclude_list=None
    ):
        if self.is_question() or self.is_discussion() or self.is_document() or self.is_answer():
            subscribers = self._qa__get_instant_notification_subscribers(
                potential_subscribers=potential_subscribers,
                mentioned_users=mentioned_users,
                exclude_list=exclude_list
            )
        elif self.is_comment():
            subscribers = self._comment__get_instant_notification_subscribers(
                potential_subscribers=potential_subscribers,
                mentioned_users=mentioned_users,
                exclude_list=exclude_list
            )
        elif self.is_organization_description() or self.is_node_description() or self.is_reject_reason():
            return set()
        else:
            raise NotImplementedError

        return self.filter_authorized_users(subscribers)

    def get_notify_sets(self, mentioned_users=None, exclude_list=None):
        """returns three lists in a dictionary with keys:
        * 'for_inbox' - users for which to add inbox items
        * 'for_mentions' - for whom mentions are added
        * 'for_email' - to whom email notifications should be sent
        """
        result = dict()
        result['for_mentions'] = set(mentioned_users) - set(exclude_list)
        #what users are included depends on the post type
        #for example for question - all Q&A contributors
        #are included, for comments only authors of comments and parent
        #post are included
        result['for_inbox'] = self.get_response_receivers(exclude_list=exclude_list)

        if openode_settings.ENABLE_EMAIL_ALERTS == False:
            result['for_email'] = set()
        else:
            #todo: weird thing is that only comments need the recipients
            #todo: debug these calls and then uncomment in the repo
            #argument to this call
            result['for_email'] = self.get_instant_notification_subscribers(
                                            potential_subscribers=result['for_inbox'],
                                            mentioned_users=result['for_mentions'],
                                            exclude_list=exclude_list
                                        )
        return result

    def get_latest_revision(self):
        return self.revisions.order_by('-revised_at')[0]

    def get_latest_revision_number(self):
        return self.get_latest_revision().revision

    def get_time_of_last_edit(self):
        if self.is_comment():
            return self.added_at

        if self.last_edited_at:
            return self.last_edited_at
        else:
            return self.added_at

    def get_owner(self):  # TODO: remove me
        return self.author

    def get_author_list(
            self,
            include_comments=False,
            recursive=False,
            exclude_list=None):

        #todo: there may be a better way to do these queries
        authors = set()
        authors.update([r.author for r in self.revisions.all()])
        if include_comments:
            authors.update([c.author for c in self.comments.all()])
        if recursive:
            if self.is_question():  # hasattr(self, 'answers'):
                #for a in self.answers.exclude(deleted = True):
                for a in self.thread.posts.get_answers().exclude(deleted=True):
                    authors.update(a.get_author_list(include_comments=include_comments))
        if exclude_list:
            authors -= set(exclude_list)
        return list(authors)

    def passes_tag_filter_for_user(self, user):

        question = self.get_origin_post()
        if user.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
            #at least some of the tags must be marked interesting
            return user.has_affinity_to_question(
                question,
                affinity_type='like'
            )
        elif user.email_tag_filter_strategy == const.EXCLUDE_IGNORED:
            return not user.has_affinity_to_question(
                question,
                affinity_type='dislike'
            )
        elif user.email_tag_filter_strategy == const.INCLUDE_ALL:
            return True
        else:
            raise ValueError(
                'unexpected User.email_tag_filter_strategy %s'\
                % user.email_tag_filter_strategy
            )

    def post_get_last_update_info(self):  # todo: rename this subroutine
        when = self.added_at
        who = self.author
        if self.last_edited_at and self.last_edited_at > when:
            when = self.last_edited_at
            who = self.last_edited_by
        comments = self.comments.all()
        if len(comments) > 0:
            for c in comments:
                if c.added_at > when:
                    when = c.added_at
                    who = c.user
        return when, who

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.get_tag_names()])

    def get_parent_post(self):
        """returns parent post or None
        if there is no parent, as it is in the case of question post"""
        if self.is_comment():
            return self.parent
        elif self.is_answer():
            return self.get_origin_post()
        else:
            return None

    def get_origin_post(self):
        if self.is_question():
            return self

        if self.is_document():
            # TODO ???
            return self

        if self.is_user_description():
            return self

        if self.is_organization_description() or self.is_reject_reason():
            return None
        else:
            return self.thread._main_post()

    def _repost_as_question(self, new_title=None):
        """posts answer as question, together with all the comments
        while preserving time stamps and authors
        does not delete the answer itself though
        """
        if not self.is_answer():
            raise NotImplementedError
        revisions = self.revisions.all().order_by('revised_at')
        rev0 = revisions[0]
        new_question = rev0.author.post_thread(
            title=new_title,
            body_text=rev0.text,
            tags=self.question.thread.tagnames,
            timestamp=rev0.revised_at,
            node=rev0.node,
            thread_type=rev0.thread.thread_type
        )
        if len(revisions) > 1:
            for rev in revisions[1:]:
                rev.author.edit_thread(
                    thread=new_question.thread,
                    body_text=rev.text,
                    revision_comment=rev.summary,
                    timestamp=rev.revised_at
                )
        for comment in self.comments.all():
            comment.content_object = new_question
            comment.save()
        return new_question

    def _repost_as_answer(self, question=None):
        """posts question as answer to another question,
        but does not delete the question,
        but moves all the comments to the new answer"""
        if not self.is_question():
            raise NotImplementedError
        revisions = self.revisions.all().order_by('revised_at')
        rev0 = revisions[0]
        new_answer = rev0.author.post_answer(
            question=question,
            body_text=rev0.text,
            timestamp=rev0.revised_at
        )
        if len(revisions) > 1:
            for rev in revisions:
                rev.author.edit_answer(
                    answer=new_answer,
                    body_text=rev.text,
                    revision_comment=rev.summary,
                    timestamp=rev.revised_at
                )
        for comment in self.comments.all():
            comment.content_object = new_answer
            comment.save()
        return new_answer

    def swap_with_question(self, new_title=None):
        """swaps answer with the question it belongs to and
        sets the title of question to ``new_title``
        """
        if not self.is_answer():
            raise NotImplementedError
            #1) make new question by using new title, tags of old question
        #   and the answer body, as well as the authors of all revisions
        #   and repost all the comments
        new_question = self._repost_as_question(new_title=new_title)

        #2) post question (all revisions and comments) as answer
        new_answer = self.question._repost_as_answer(question=new_question)

        #3) assign all remaining answers to the new question
        self.question.answers.update(question=new_question)
        self.question.delete()
        self.delete()
        return new_question

    def get_user_vote(self, user):
        if not self.is_answer():
            raise NotImplementedError

        if user.is_anonymous():
            return None

        votes = self.votes.filter(user=user)
        if votes and votes.count() > 0:
            return votes[0]
        else:
            return None

    def _thread__assert_is_visible_to(self, user):
        """raises QuestionHidden"""
        if self.deleted:
            message = _(
                'Sorry, this question has been '
                'deleted and is no longer accessible'
            )
            if user.is_anonymous():
                raise exceptions.QuestionHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.QuestionHidden(message)

    def _answer__assert_is_visible_to(self, user):
        """raises QuestionHidden or AnswerHidden"""
        try:
            self.thread._main_post().assert_is_visible_to(user)
        except exceptions.QuestionHidden:
            message = _(
                'Sorry, the answer you are looking for is '
                'no longer available, because the parent '
                'question has been removed'
            )
            raise exceptions.QuestionHidden(message)
        if self.deleted:
            message = _(
                'Sorry, this answer has been '
                'removed and is no longer accessible'
            )
            if user.is_anonymous():
                raise exceptions.AnswerHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.AnswerHidden(message)

    def _comment__assert_is_visible_to(self, user):
        """raises QuestionHidden or AnswerHidden"""
        try:
            self.parent.assert_is_visible_to(user)
        except exceptions.QuestionHidden:
            message = _(
                        'Sorry, the comment you are looking for is no '
                        'longer accessible, because the parent question '
                        'has been removed'
                       )
            raise exceptions.QuestionHidden(message)
        except exceptions.AnswerHidden:
            message = _(
                        'Sorry, the comment you are looking for is no '
                        'longer accessible, because the parent answer '
                        'has been removed'
                       )
            raise exceptions.AnswerHidden(message)

    def assert_is_visible_to_user_organizations(self, user):
        """raises permission denied of the post
        is hidden due to organization memberships"""
        assert(self.is_comment() == False)
        return True  # TODO vyresit pomoci novych opravneni
        post_organizations = self.organizations.all()

        if self.is_question() or self.is_discussion() or self.is_document():  # todo maybe merge the "hidden" exceptions
            exception = exceptions.QuestionHidden
        elif self.is_answer():
            exception = exceptions.AnswerHidden
        else:
            raise NotImplementedError

        message = _('This post is temporarily not available')
        if user.is_anonymous():
            raise exception(message)
        else:
            user_organizations_ids = user.get_organizations().values_list('id', flat=True)
            if post_organizations.filter(id__in=user_organizations_ids).count() == 0:
                raise exception(message)

    def assert_is_visible_to(self, user):
        if self.is_comment() == False:
            self.assert_is_visible_to_user_organizations(user)
        if self.is_question() or self.is_discussion():
            return self._thread__assert_is_visible_to(user)
        elif self.is_answer():
            return self._answer__assert_is_visible_to(user)
        elif self.is_comment():
            return self._comment__assert_is_visible_to(user)

        elif self.is_document():
            # TODO ???
            return

        raise NotImplementedError

    def get_updated_activity_data(self, created=False):
        if self.is_answer():
            #todo: simplify this to always return latest revision for the second
            #part
            if created:
                return const.TYPE_ACTIVITY_ANSWER, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_ANSWER, latest_revision
        elif self.is_question():
            if created:
                return const.TYPE_ACTIVITY_ASK_QUESTION, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_QUESTION, latest_revision
        elif self.is_discussion():
            if created:
                return const.TYPE_ACTIVITY_CREATE_DISCUSSION, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_DISCUSSION, latest_revision
        elif self.is_document():
            if created:
                return const.TYPE_ACTIVITY_CREATE_DOCUMENT, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_DOCUMENT, latest_revision
        elif self.is_comment():
            if self.parent.is_question():
                return const.TYPE_ACTIVITY_COMMENT_QUESTION, self
            elif self.parent.is_answer():
                return const.TYPE_ACTIVITY_COMMENT_ANSWER, self
        elif self.is_organization_description():
            if created:
                return const.TYPE_ACTIVITY_CREATE_ORGANIZATION_DESCRIPTION, self
            else:
                return const.TYPE_ACTIVITY_UPDATE_ORGANIZATION_DESCRIPTION, self
        elif self.is_node_description():
            if created:
                return const.TYPE_ACTIVITY_CREATE_NODE_DESCRIPTION, self
            else:
                return const.TYPE_ACTIVITY_UPDATE_NODE_DESCRIPTION, self
        elif self.is_reject_reason():
            if created:
                return const.TYPE_ACTIVITY_CREATE_REJECT_REASON, self
            else:
                return const.TYPE_ACTIVITY_UPDATE_REJECT_REASON, self

        raise NotImplementedError

    def get_tag_names(self):
        return self.thread.get_tag_names()

    def __apply_edit(
                    self,
                    edited_at=None,
                    edited_by=None,
                    text=None,
                    title='',
                    tags='',
                    comment=None,
                    by_email=False
                ):
        if text is None:
            text = self.get_latest_revision().text
        if edited_at is None:
            edited_at = datetime.datetime.now()
        if edited_by is None:
            raise Exception('edited_by is required')

        self.last_edited_at = edited_at
        self.last_edited_by = edited_by
        #self.html is denormalized in save()
        self.text = text

        #must add revision before saving the answer
        self.add_revision(
            author=edited_by,
            revised_at=edited_at,
            text=text,
            comment=comment,
            by_email=by_email,
            title=title,
            tags=tags
        )

        parse_results = self.parse_and_save(author=edited_by)

        from openode.models import signals
        signals.post_updated.send(
            post=self,
            updated_by=edited_by,
            newly_mentioned_users=parse_results['newly_mentioned_users'],
            timestamp=edited_at,
            created=False,
            diff=parse_results['diff'],
            sender=self.__class__
        )

    def _answer__apply_edit(
                        self,
                        edited_at=None,
                        edited_by=None,
                        text=None,
                        comment=None,
                        by_email=False
                    ):

        self.__apply_edit(
            edited_at=edited_at,
            edited_by=edited_by,
            text=text,
            comment=comment,
            by_email=by_email
        )

        if edited_at is None:
            edited_at = datetime.datetime.now()
        self.thread.set_last_activity(last_activity_at=edited_at, last_activity_by=edited_by)

    def _thread__apply_edit(self, edited_at=None, edited_by=None, title=None,\
                              text=None, comment=None, tags=None, by_email=False
                            ):
        #todo: the thread editing should happen outside of this
        #method, then we'll be able to unify all the *__apply_edit
        #methods
        latest_revision = self.get_latest_revision()
        #a hack to allow partial edits - important for SE loader
        if title is None:
            title = self.thread.title
        if tags is None:
            tags = latest_revision.tagnames
        if edited_at is None:
            edited_at = datetime.datetime.now()

        # Update the Question tag associations
        if latest_revision.tagnames != tags:
            self.thread.update_tags(
                tagnames=tags, user=edited_by, timestamp=edited_at
            )

        self.thread.title = title
        self.thread.tagnames = tags
        self.thread.save()

        self.__apply_edit(
            edited_at=edited_at,
            edited_by=edited_by,
            text=text,
            title=title,
            tags=tags,
            comment=comment,
            by_email=by_email
        )

        self.thread.set_last_activity(last_activity_at=edited_at, last_activity_by=edited_by)

    def apply_edit(self, *args, **kwargs):
        #todo: unify this, here we have unnecessary indirection
        #the question__apply_edit function is backwards:
        #the title edit and tag edit should apply to thread
        #not the question post
        if self.is_answer():
            return self._answer__apply_edit(*args, **kwargs)

        elif self.is_question() or self.is_discussion() or self.is_document():
            return self._thread__apply_edit(*args, **kwargs)

        elif self.is_organization_description() or self.is_user_description() or self.is_comment() or \
             self.is_reject_reason() or self.is_node_description():
            return self.__apply_edit(*args, **kwargs)

        raise NotImplementedError

    def __add_revision(
                    self,
                    author=None,
                    revised_at=None,
                    text=None,
                    comment=None,
                    by_email=False,
                    email_address='',
                    title='',
                    tags=''
                ):
        #todo: this may be identical to Question.add_revision
        if None in (author, revised_at, text):
            raise Exception('arguments author, revised_at and text are required')
        rev_no = self.revisions.all().count() + 1
        if comment in (None, ''):
            if rev_no == 1:
                comment = const.POST_STATUS['default_version']
            else:
                comment = 'No.%s Revision' % rev_no
        return PostRevision.objects.create(
            post=self,
            author=author,
            revised_at=revised_at,
            text=text,
            title=title,
            tagnames=tags,
            summary=comment,
            revision=rev_no,
            by_email=by_email,
            email_address=email_address
        )

    # def _question__add_revision(
    #         self,
    #         author=None,
    #         text=None,
    #         comment=None,
    #         revised_at=None,
    #         by_email=False,
    #         email_address=None
    # ):
    #     if None in (author, text):
    #         raise Exception('author, text and comment are required arguments')
    #     rev_no = self.revisions.all().count() + 1
    #     if comment in (None, ''):
    #         if rev_no == 1:
    #             comment = const.POST_STATUS['default_version']
    #         else:
    #             comment = 'No.%s Revision' % rev_no

    #     return PostRevision.objects.create(
    #         post=self,
    #         revision=rev_no,
    #         title=self.thread.title,
    #         author=author,
    #         revised_at=revised_at,
    #         tagnames=self.thread.tagnames,
    #         summary=comment,
    #         text=text,
    #         by_email=by_email,
    #         email_address=email_address
    #     )

    def add_revision(self, *kargs, **kwargs):
        #todo: unify these
        if self.post_type in const.POST_TYPES:
            return self.__add_revision(*kargs, **kwargs)
        raise NotImplementedError

    def _answer__get_response_receivers(self, exclude_list=None):
        """get list of users interested in this response
        update based on their participation in the main_post
        activity

        exclude_list is required and normally should contain
        author of the updated so that he/she is not notified of
        the response
        """
        assert(exclude_list is not None)
        recipients = set()
        recipients.update(
            self.get_author_list(
                include_comments=True
            )
        )
        main_post = self.thread._main_post()
        recipients.update(
            main_post.get_author_list(
                include_comments=True
            )
        )
        for answer in main_post.thread.posts.get_answers().all():
            recipients.update(answer.get_author_list())

        return recipients - set(exclude_list)

    def _question__get_response_receivers(self, exclude_list=None):
        """returns list of users who might be interested
        in the question update based on their participation
        in the question activity

        exclude_list is mandatory - it normally should have the
        author of the update so the he/she is not notified about the update
        """
        assert(exclude_list != None)
        recipients = set()
        recipients.update(
            self.get_author_list(
                include_comments=True
            )
        )
        #do not include answer commenters here
        for a in self.thread.posts.get_answers().all():
            recipients.update(a.get_author_list())

        return recipients - set(exclude_list)

    def _discussion__get_response_receivers(self, exclude_list=None):
        """returns list of users who might be interested
        in the question update based on their participation
        in the question activity

        exclude_list is mandatory - it normally should have the
        author of the update so the he/she is not notified about the update
        """
        assert(exclude_list != None)
        recipients = set()
        recipients.update(
            self.get_author_list()
        )
        #do not include answer commenters here
        for a in self.thread.posts.get_answers().all():
            recipients.update(a.get_author_list())

        return recipients - set(exclude_list)

    def _document__get_response_receivers(self, exclude_list=None):
        """returns list of users who might be interested
        in the question update based on their participation
        in the question activity

        exclude_list is mandatory - it normally should have the
        author of the update so the he/she is not notified about the update
        """
        assert(exclude_list != None)
        recipients = set()
        recipients.update(
            self.get_author_list()
        )

        return recipients - set(exclude_list)

    def _comment__get_response_receivers(self, exclude_list=None):
        """Response receivers are commenters of the
        same post and the authors of the post itself.
        """
        assert(exclude_list is not None)
        users = set()
        #get authors of parent object and all associated comments
        users.update(
            self.parent.get_author_list(
                    include_comments=True,
                )
        )
        return users - set(exclude_list)

    def get_response_receivers(self, exclude_list=None):
        """returns a list of response receiving users
        who see the on-screen notifications
        """
        if self.is_answer():
            receivers = self._answer__get_response_receivers(exclude_list)
        elif self.is_question():
            receivers = self._question__get_response_receivers(exclude_list)
        elif self.is_discussion():
            receivers = self._discussion__get_response_receivers(exclude_list)
        elif self.is_document():
            receivers = self._document__get_response_receivers(exclude_list)
        elif self.is_comment():
            receivers = self._comment__get_response_receivers(exclude_list)
        elif self.is_organization_description() or self.is_node_description() or self.is_reject_reason():
            return set()  # todo: who should get these?
        else:
            raise NotImplementedError

        return self.filter_authorized_users(receivers)

    def get_main_post_title(self):
        if self.is_question() or self.is_discussion() or self.is_document():
            if self.thread.closed:
                attr = const.POST_STATUS['closed']
            elif self.deleted:
                attr = const.POST_STATUS['deleted']
            else:
                attr = None
            if attr is not None:
                return u'%s %s' % (self.thread.title, attr)
            else:
                return self.thread.title
        raise NotImplementedError

    def accepted(self):
        if self.is_answer():
            return self.thread.accepted_answer_id == self.id
        raise NotImplementedError

    def get_page_number(self, answer_posts):
        """When question has many answers, answers are
        paginated. This function returns number of the page
        on which the answer will be shown, using the default
        sort order. The result may depend on the visitor."""
        if not self.is_answer() and not self.is_comment():
            raise NotImplementedError

        if self.is_comment():
            post = self.parent
        else:
            post = self

        order_number = 0
        for answer_post in answer_posts:
            if post == answer_post:
                break
            order_number += 1
        return int(order_number / const.ANSWERS_PAGE_SIZE) + 1

    def get_order_number(self):
        if not self.is_comment():
            raise NotImplementedError
        return self.parent.comments.filter(added_at__lt=self.added_at).count() + 1

    def is_upvoted_by(self, user):
        from openode.models.repute import Vote
        return Vote.objects.filter(user=user, voted_post=self, vote=Vote.VOTE_UP).exists()

    def is_last(self):
        """True if there are no newer comments on
        the related parent object
        """
        if not self.is_comment():
            raise NotImplementedError
        return Post.objects.get_comments().filter(
            added_at__gt=self.added_at,
            parent=self.parent
        ).exists() is False

    def hack_template_marker(self, name):
        list(Post.objects.filter(text=name))


class PostRevisionManager(models.Manager):
    def create(self, *kargs, **kwargs):
        revision = super(PostRevisionManager, self).create(*kargs, **kwargs)
        from openode.models import signals
        signals.post_revision_published.send(None, revision=revision)
        return revision


class PostRevision(models.Model):
    QUESTION_REVISION_TEMPLATE_NO_TAGS = (
        '<h3>%(title)s</h3>\n'
        '<div class="text">%(html)s</div>\n'
    )

    post = models.ForeignKey('openode.Post', related_name='revisions', null=True, blank=True)
    revision = models.PositiveIntegerField()
    author = models.ForeignKey('auth.User', related_name='%(class)ss')
    revised_at = models.DateTimeField()
    summary = models.CharField(max_length=300, blank=True)
    text = models.TextField(blank=True, default='')

    by_email = models.BooleanField(default=False)  # true, if edited by email
    email_address = models.EmailField(null=True, blank=True)

    # Question-specific fields
    title = models.CharField(max_length=300, blank=True, default='')
    tagnames = models.CharField(max_length=125, blank=True, default='')

    objects = PostRevisionManager()

    class Meta:
        # INFO: This `unique_together` constraint might be problematic for databases in which
        #       2+ NULLs cannot be stored in an UNIQUE column.
        #       As far as I know MySQL, PostgreSQL and SQLite allow that so we're on the safe side.
        unique_together = ('post', 'revision')
        ordering = ('-revision',)
        app_label = 'openode'


    def __unicode__(self):
        return u'%s - revision %s of %s' % (self.post.post_type, self.revision, self.title)

    def parent(self):
        return self.post

    def clean(self):
        "Internal cleaning method, called from self.save() by self.full_clean()"
        if not self.post:
            raise ValidationError('Post field has to be set.')

    def save(self, **kwargs):
        # Determine the revision number, if not set
        if not self.revision:
            # TODO: Maybe use Max() aggregation? Or `revisions.count() + 1`
            self.revision = self.parent().revisions.values_list(
                                                'revision', flat=True
                                            )[0] + 1
        self.full_clean()
        super(PostRevision, self).save(**kwargs)

    def get_absolute_url(self):
        if self.post.is_question():
            return reverse('question_revisions', args=(self.post.id,))
        elif self.post.is_answer():
            return reverse('answer_revisions', kwargs={'id': self.post.id})
        else:
            return self.post.get_absolute_url()

    def get_main_post_title(self):
        #INFO: ack-grepping shows that it's only used for Questions, so there's no code for Answers
        return self.question.thread.title

    def get_origin_post(self):
        """same as Post.get_origin_post()"""
        return self.post.get_origin_post()

    @property
    def html(self, **kwargs):
        sanitized_html = bleach_html(self.text)

        if self.post.is_question():
            return self.QUESTION_REVISION_TEMPLATE_NO_TAGS % {
                'title': self.title,
                'html': sanitized_html
            }
        elif self.post.is_answer():
            return sanitized_html

    def get_snippet(self, max_length=120):
        """same as Post.get_snippet"""
        return html_utils.strip_tags(self.html)[:max_length] + '...'


class PostFlagReason(models.Model):
    added_at = models.DateTimeField()
    author = models.ForeignKey('auth.User')
    title = models.CharField(max_length=128)
    details = models.ForeignKey(Post, related_name='post_reject_reasons')

    class Meta:
        app_label = 'openode'


class DraftAnswer(models.Model):
    """Provides space for draft answers,
    note that unlike ``AnonymousAnswer`` the foreign key
    is going to ``Thread`` as it should.
    """
    thread = models.ForeignKey('Thread', related_name='draft_answers')
    author = models.ForeignKey(User, related_name='draft_answers')
    text = models.TextField(null=True)

    class Meta:
        app_label = 'openode'


class AnonymousAnswer(DraftContent):
    """Todo: re-route the foreign key to ``Thread``"""
    question = models.ForeignKey(Post, related_name='anonymous_answers')

    def publish(self, user):
        added_at = datetime.datetime.now()
        Post.objects.create_new_answer(
            thread=self.question.thread,
            author=user,
            added_at=added_at,
            text=self.text
        )
        self.delete()

################################################################################
################################################################################

from django.db.models.signals import post_save, pre_save
from openode.models.slots.post import recount_unread_posts


def log_post_save(sender, **kwargs):
    post = kwargs["instance"]
    logger = logging.getLogger('post')

    logger.info("Post save: %s" % repr({
        "pk": post.pk,
        "post_type": post.post_type,
        "author": post.author_id,

        # "node": post.node_id if post.node else None,
        # "post_type": post.thread_type,
        "created": kwargs["created"]
    }))


def fill_dt_created(sender, **kwargs):
    post = kwargs["instance"]
    if post.dt_created is None:
        post.dt_created = datetime.datetime.now()


pre_save.connect(fill_dt_created, sender=Post)
post_save.connect(log_post_save, sender=Post)
post_save.connect(recount_unread_posts, sender=Post)
