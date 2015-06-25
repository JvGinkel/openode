# -*- coding: utf-8 -*-

import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import signals, Sum
from django.utils.html import escape, strip_tags
from django.utils.translation import ugettext as _
from mptt.models import MPTTModel, TreeForeignKey

from openode import const
from openode.models.fields import WysiwygField
from openode.models.post import Post
from openode.models.slots.node import (
    post_delete_node_user,
    post_save_node,
    post_save_node_user,
    )
from openode.models.fields import SlugField

################################################################################
################################################################################


class Node(MPTTModel):
    """
    Node model
    """

    dt_created = models.DateTimeField(auto_now_add=True, verbose_name=_(u"Create date"))
    dt_changed = models.DateTimeField(auto_now=True, verbose_name=_(u"Change date"))

    title = models.CharField(max_length=300)
    slug = SlugField(
        slug_from='title',
        slug_unique=True,
        max_length=300
    )
    style = models.CharField(max_length=64, choices=const.NODE_STYLE, default=const.NODE_STYLE_REGULAR)

    parent = TreeForeignKey('self', null=True, related_name='children', blank=True)

    long_title = models.CharField(max_length=1000, default='', blank=True, null=True)

    description = models.OneToOneField(
        Post,
        related_name='described_node',
        null=True,
        blank=True,
        editable=False
    )

    display_opened = models.BooleanField(default=False, verbose_name=_(u'Display node opened'),
        help_text=_(u"Show node openen on homepage.")
        )

    is_question_flow_enabled = models.BooleanField(default=False, verbose_name=_('Is question flow enabled'))

    users = models.ManyToManyField(User, through='NodeUser', related_name='nodes')

    followed_count = models.PositiveIntegerField(default=0, editable=False)

    followed_by = models.ManyToManyField(User, through='FollowedNode', related_name='followed_nodes')
    subscribed_by = models.ManyToManyField(User, through='SubscribedNode', related_name='subscribed_nodes', blank=True, editable=False)

    module_qa = models.BooleanField(default=False)
    module_forum = models.BooleanField(default=False)
    module_library = models.BooleanField(default=False)

    module_qa_readonly = models.BooleanField(default=False)
    module_forum_readonly = models.BooleanField(default=False)
    module_library_readonly = models.BooleanField(default=False)

    module_annotation = models.BooleanField(default=False)
    default_module = models.CharField(max_length=255, blank=True, choices=const.NODE_MODULE_CHOICES, default='')

    perex_node = WysiwygField(blank=True, verbose_name=_(u'Node perex'))
    perex_qa = WysiwygField(blank=True, verbose_name=_(u'Q&A perex'))
    perex_forum = WysiwygField(blank=True, verbose_name=_(u'Forum perex'))
    perex_annotation = WysiwygField(blank=True, verbose_name=_(u'Annotation perex'))
    perex_library = WysiwygField(blank=True, verbose_name=_(u'Library perex'))

    perex_node_important = models.BooleanField(default=False, verbose_name=_(u'Node perex important'))
    perex_qa_important = models.BooleanField(default=False, verbose_name=_(u'Q&A perex important'))
    perex_forum_important = models.BooleanField(default=False, verbose_name=_(u'Forum perex important'))
    perex_annotation_important = models.BooleanField(default=False, verbose_name=_(u'Annotation perex important'))
    perex_library_important = models.BooleanField(default=False, verbose_name=_(u'Library perex important'))

    readonly = models.BooleanField(default=False, db_index=True)

    closed = models.BooleanField(default=False, db_index=True)
    closed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.TextField(blank=True)

    deleted = models.BooleanField(default=False, db_index=True)

    visibility = models.CharField(max_length=30, db_index=True, default=const.NODE_VISIBILITY_PUBLIC, choices=const.NODE_VISIBILITY_CHOICES)

    ###################################
    # denormalized
    ###################################

    last_activity_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_activity_by = models.ForeignKey(User, null=True, blank=True, editable=False, related_name='nodes_by_latest_activity', on_delete=models.SET_NULL)

    WYSIWYG_FIELDS = [
        "perex_qa",
        "perex_node",
        "perex_forum",
        "perex_library",
        "perex_annotation",
    ]

    class Meta:
        app_label = 'openode'
        db_table = 'openode_node'

    def __unicode__(self):
        return self.title

    def full_title(self):
        long_title = self.long_title
        if long_title:
            return u'%s – %s' % (self.title, long_title)

        return escape(self.title)

    def full_title_with_status(self, style='plain'):
        style_str = self.title_status(style)
        if style_str:
            return u'%s %s' % (self.full_title(), style_str)

        return self.full_title()

    def title_with_status(self, style='plain'):
        style_str = self.title_status(style)
        if style_str:
            return u'%s %s' % (escape(self.title), style_str)

        return escape(self.title)

    def title_status(self, style='plain'):
        # allowed styles are: 'html', 'plain'
        if not style in ('html', 'plain'):
            raise ValueError('Unknown style, valid values are \'plain\' (default) and \'html\'.')

        TXT_TPL = u'[%s]'
        HTML_TPL = u'<span class="status">%s</span>'

        DELETED_STR = _('DELETED')
        CLOSED_STR = _('CLOSED')
        PRIVATE_STR = _('PRIVATE')
        PUBLIC_STR = _('PUBLIC')
        REGISTERED_STR = _('REGISTERED ONLY')

        status_list = []

        TPL_CONST = '%s'  # no TPL set
        if style == 'plain':
            TPL_CONST = TXT_TPL
        if style == 'html':
            TPL_CONST = HTML_TPL

        if self.visibility in (const.NODE_VISIBILITY_PRIVATE, const.NODE_VISIBILITY_SEMIPRIVATE):
            status_list.append(TPL_CONST % PRIVATE_STR)
        # elif self.visibility == const.NODE_VISIBILITY_REGISTRED_USERS:
        #     status_list.append(TPL_CONST % REGISTERED_STR)
        elif self.visibility == const.NODE_VISIBILITY_PUBLIC:
            status_list.append(TPL_CONST % PUBLIC_STR)
        if self.closed:
            status_list.append(TPL_CONST % CLOSED_STR)
        if self.deleted:
            status_list.append(TPL_CONST % DELETED_STR)

        return u' '.join(status_list)

    def save(self, *args, **kwargs):

        # Remove all from perex_<module>, if is perex, except html tags, empty.
        for module, xxx in const.NODE_MODULE_CHOICES + [("node", None)]:
            attr = "perex_%s" % module
            html = getattr(self, attr)
            text = strip_tags(html).strip()
            if (len(text) == 0) and (html != text):
                setattr(self, attr, "")

        return super(Node, self).save(*args, **kwargs)

    def get_children_for_user(self, user, with_closed=False):
        """
            @return node's subnodes mptt queryset filtered by user permission and closed status
            @param user: User instance
            @param with_closed: bool, attribite for filtering queryset
        """
        qs = self.get_children().filter(deleted=False)

        if with_closed:
            pass  # for better condition read
        else:
            qs = qs.filter(closed=False)

        # "return" iterator
        for child in qs:
            if user.has_openode_perm('node_show', child):
                yield child

        # for case of returning queryset
        #return qs.filter(pk__in=[child.pk for child in qs if user.has_openode_perm('node_show', child)])

    def is_leaf_node_for_user(self, user, with_closed):
        if self.is_leaf_node():
            return True
        else:
            return not any(self.get_children_for_user(user, with_closed))

            # for case of returning queryset by method get_children_for_user
            #return not self.get_children_for_user(user, with_closed).exists()

    def is_followed_by(self, user=None):
        """True if node is followed by user"""
        if user and user.is_authenticated():
            return self.followed_by.filter(id=user.id).exists()
        return False

    def is_subscribed_by(self, user=None):
        """True if node is followed by user"""
        if user and user.is_authenticated():
            return self.subscribed_by.filter(id=user.id).exists()
        return False

    def is_module_enabled(self, module_name):
        return getattr(self, "module_%s" % module_name, False)

    ###################################

    def update_latest(self):
        """
            update denormalized latest at/by activity
        """
        latest = self.threads.order_by('-last_activity_at')[0]
        if not latest:
            return

        # store to instance
        self.last_activity_at = latest.last_activity_at
        self.last_activity_by = latest.last_activity_by

        # store to db
        self.__class__.objects.filter(pk=self.pk).update(
            last_activity_at=self.last_activity_at,
            last_activity_by=self.last_activity_by
            )

    def get_last_activity_at(self):
        """
            return denormalized value from node's threads
        """
        return self.last_activity_at
        # # TODO change to attribute - update even if manager actions are performed (node settings, perexes, etc...)
        # try:
        #     return self.threads.order_by('-last_activity_at')[0].last_activity_at
        # except IndexError:
        #     return None

    def get_last_activity_by(self):
        """
            return denormalized value from node's threads
        """
        return self.last_activity_by
        # try:
        #     return self.threads.order_by('-last_activity_at')[0].last_activity_by
        # except IndexError:
        #     return None

    ###################################
    @property
    def users_count(self):
        return self.users.count()

    @property
    def sum_of_all_views(self):
        children = self.get_children().filter(deleted=False)
        children_sum = sum([child.sum_of_all_views for child in children]) or 0

        n_of_threads = self.threads.filter(is_deleted=False).aggregate(all_views=Sum('view_count'))['all_views'] or 0
        return n_of_threads + children_sum

    def is_category(self):
        return self.style == const.NODE_STYLE_CATEGORY

    def get_responsible_persons(self):
        return self.users.filter(is_active=True, nodeuser__is_responsible=True)

    def get_role_for_user(self, user):
        if user.is_anonymous():
            return None
        try:
            cu = NodeUser.objects.get(user=user, node=self)
            return cu.get_role_display()
        except NodeUser.DoesNotExist:
            return None

    def user_is_manager(self, user):
        if user.is_anonymous():
            return False
        try:
            return bool(NodeUser.objects.get(user=user, node=self, role=const.NODE_USER_ROLE_MANAGER))
        except NodeUser.DoesNotExist:
            return False

    def get_module(self, module_abbr):
        return dict([(i[0], i[1]) for i in const.NODE_MODULES]).get(module_abbr)

    def get_modules(self):
        for node_module in const.NODE_MODULES:
            if getattr(self, 'module_%s' % node_module[0], False) is True:
                yield node_module

    # def get_optional_modules(self):
    #     for node_module in const.NODE_OPTIONAL_MODULE_CHOICES:
    #         if getattr(self, 'module_%s' % node_module[0], False) is True:
    #             yield node_module

    def get_thread_modules(self):
        for node_module in self.get_modules():
            if node_module[0] in const.THREAD_TYPE_BY_NODE_MODULE:
                yield node_module

    def get_absolute_url(self, module=None):
        kwargs = {
            'node_id': self.pk,
            'node_slug': self.slug
        }
        if module:
            url_abbr = "node_module"
            kwargs["module"] = module
        else:
            url_abbr = "node"
        return reverse(url_abbr, kwargs=kwargs)

    def get_perex_data(self, module):
        """
            @return tuple:
                - perex_<module> : HtmlText
                - perex_<module>_important : Bool
                for using in templates
        """
        return getattr(self, "perex_%s" % module, None), getattr(self, "perex_%s_important" % module, None)

    def is_new_for_user(self, user):
        """
            TODO: cache it
        """
        for module in const.THREAD_TYPE_BY_NODE_MODULE.keys():
            if self.is_module_enabled(module) and self.get_unread_count(user, module) > 0:
                return True
        return False

    def get_unread_count(self, user, module):
        """
            @return visited thread's count with unread posts
            TODO: cache it
        """

        if user.is_anonymous():
            return 0

        if not self.is_module_enabled(module):
            return 0

        from openode.models.thread import ThreadView, Thread

        thread_type = const.THREAD_TYPE_BY_NODE_MODULE[module]

        if self.is_followed_by(user):
            # if user follows this node it sees all new threads (questions and documents) as unread, along with unread posts in visited threads (ThreadView exists)
            if thread_type == const.THREAD_TYPE_DISCUSSION:
                # for discussion without ThreadView, we count all as undread
                try:
                    _thread = self.threads.get(thread_type=const.THREAD_TYPE_DISCUSSION)
                    try:
                        thread_view = user.thread_views.get(thread=_thread)
                        ret = thread_view.not_view_sum_count()
                    except ThreadView.DoesNotExist:
                        ret = _thread.get_answer_count()
                except Thread.DoesNotExist:
                    return 0
            else:
                # all Threads of a module (read, updated and new together)
                th_set = Thread.objects.filter(
                    node=self,
                    is_deleted=False,
                    thread_type=thread_type
                ).values_list("pk", flat=True)

                # ThreadViews with everything read (user has seen all the content)
                tw_set = ThreadView.objects.filter(
                    user=user,
                    thread__node=self,
                    thread__is_deleted=False,
                    thread__thread_type=thread_type,
                ).exclude(
                    models.Q(not_view_post_count__gt=0)
                    | models.Q(not_view_comment_count__gt=0)
                    | models.Q(main_post_viewed=False)
                ).values_list("thread_id", flat=True)

                # substract sets to get what an user has not seen yet
                ret = len(set(th_set) - set(tw_set))

        else:
            # only posts in visited threads (where ThreadView exists) are showed as unread
            if thread_type == const.THREAD_TYPE_DISCUSSION:
                # once we have only one thread for discussion, we descent into it and count unread post instead of threads
                try:
                    _thread = self.threads.get(thread_type=const.THREAD_TYPE_DISCUSSION)
                    thread_view = user.thread_views.get(thread=_thread)
                    ret = thread_view.not_view_sum_count()
                except (Thread.DoesNotExist, ThreadView.DoesNotExist):
                    return 0
            else:
                # for questions and documents we look for unread posts only among visited threads
                ret = ThreadView.objects.filter(
                    models.Q(not_view_post_count__gt=0)
                    | models.Q(not_view_comment_count__gt=0)
                    | models.Q(main_post_viewed=False),
                    user=user,
                    thread__node=self,
                    thread__is_deleted=False,
                    thread__thread_type=thread_type
                ).count()

        # apply cut-off from settings
        if ret > const.MAX_UNREAD_POSTS_COUNT:
            ret = "%s+" % const.MAX_UNREAD_POSTS_COUNT
        return ret

    def get_threads_count_for_module(self, module):
        from openode.models.thread import Thread

        if module == const.NODE_MODULE_FORUM:
            try:
                return self.threads.get(
                    thread_type=const.THREAD_TYPE_BY_NODE_MODULE[const.NODE_MODULE_FORUM]
                ).posts.filter(
                    post_type=const.POST_TYPE_THREAD_POST,
                    deleted=False
                ).count()
            except Thread.DoesNotExist:
                return 0

        try:
            return self.get_threads_count(const.THREAD_TYPE_BY_NODE_MODULE[module])
        except KeyError:
            return 0

    def get_threads_count(self, thread_type):
        qs = self.threads.filter(
            thread_type=thread_type,
            is_deleted=False,
        )
        return qs.count()

    def get_questions_count(self):
        return self.get_threads_count(const.THREAD_TYPE_QUESTION)

    def get_documents_count(self):
        return self.get_threads_count(const.THREAD_TYPE_DOCUMENT)

    def get_discussions_count(self):
        return self.get_threads_count(const.THREAD_TYPE_DISCUSSION)

    def get_discussions_posts_count(self):
        try:
            d = self.threads.get(thread_type=const.THREAD_TYPE_DISCUSSION)
            return d.posts.filter(
                post_type=const.POST_TYPE_THREAD_POST,
                deleted=False,
            ).count()
        except ObjectDoesNotExist:
            return 0

    def update_followed_count(self):
        """
            this method updates denormalized field
        """
        #TODO how about deactivated users?
        self.followed_count = FollowedNode.objects.filter(node=self).count()
        self.save()

    def visit(self, user, timestamp=None):
        """
            record user's visit to this Node
        """
        if user.is_anonymous():
            return False

        if timestamp:
            last_visit = timestamp
        else:
            last_visit = datetime.datetime.now()

        try:
            fn = self.node_following_users.get(user=user)
            fn.last_visit = last_visit
            fn.save()
            return True
        except ObjectDoesNotExist:
            return False

################################################################################


class FollowedNode(models.Model):
    """A followed Node of a User."""
    node = models.ForeignKey(Node, related_name='node_following_users')
    user = models.ForeignKey(User, related_name='user_followed_nodes')

    last_visit = models.DateTimeField(default=datetime.datetime.now)
    added_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'openode'
        db_table = u'followed_node'

    def __unicode__(self):
        return '[%s] followed at %s' % (self.user, self.added_at)

################################################################################


class SubscribedNode(models.Model):
    """A subscribed Node of a User."""
    node = models.ForeignKey(Node)
    user = models.ForeignKey(User, related_name='user_subscribed_nodes')

    added_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'openode'
        db_table = u'subscribed_node'

    def __unicode__(self):
        return '[%s] subscribed at %s' % (self.user, self.added_at)

################################################################################


class NodeUser(models.Model):
    user = models.ForeignKey(User)
    node = models.ForeignKey(Node, related_name='node_users')
    role = models.CharField(max_length=30, choices=const.NODE_USER_ROLES, default=const.NODE_USER_ROLE_MEMBER)
    is_responsible = models.BooleanField(default=False)

    class Meta:
        app_label = 'openode'
        db_table = u'openode_nodeuser'
        unique_together = ('user', 'node')

    def __unicode__(self, *args, **kwargs):
        return u"user=%s, role=%s" % (
            self.user, self.role
            )

################################################################################
################################################################################


# NodeUser's signals
signals.post_save.connect(post_save_node_user, sender=NodeUser)
signals.post_delete.connect(post_delete_node_user, sender=NodeUser)

# Node's signals
signals.post_save.connect(post_save_node, sender=Node)
