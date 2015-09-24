# -*- coding: utf-8 -*-

from openode import startup_procedures
startup_procedures.run()

from django.contrib.auth.models import User, AnonymousUser
#set up a possibility for the users to follow others
try:
    import followit
    followit.register(User)
except ImportError:
    pass

import collections
import datetime
import hashlib
import logging
import urllib
import uuid

# from celery import states
from celery.task import task

from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.auth.models import _user_has_perm
from django.db.models import signals as django_signals, Q
from django.template import Context
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.db import models
from django.conf import settings as django_settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import cache
from django.core import exceptions as django_exceptions


from openode import exceptions as openode_exceptions
from openode import const
from openode.const.message_keys import get_i18n_message
from openode.conf import settings as openode_settings
from openode.models.thread import Thread
from openode.skins import utils as skin_utils

from openode.models.actuality import Actuality
from openode.models.cms import StaticPage, MenuItem
from openode.models.thread import ThreadView, AnonymousQuestion
from openode.models.thread import DraftQuestion
from openode.models.thread import FollowedThread, SubscribedThread
from openode.models.node import Node, FollowedNode, SubscribedNode, NodeUser
from openode.models.tag import Tag, MarkedTag

from openode.models.tag import get_organization_names
from openode.models.tag import get_organizations
from openode.models.user import EmailFeedSetting, ActivityAuditStatus, Activity, Organization, OrganizationMembership, Log
from openode.models.post import Post, PostRevision
from openode.models.post import PostFlagReason, AnonymousAnswer
from openode.models.post import DraftAnswer
from openode.models.reply_by_email import ReplyAddress
from openode.models import signals
from openode.models.repute import Vote
from openode import auth
from openode.utils.decorators import auto_now_timestamp
from openode.utils.slug import slugify
from openode.utils.html import bleach_html
from openode.utils.diff import textDiff as htmldiff
from openode.utils.url_utils import strip_path
from openode.utils.notify_users import immediately_notify_users
from openode import mail

from openode.models.slots.user import set_membership


def get_model(model_name):
    """a shortcut for getting model for an openode app"""
    return models.get_model('openode', model_name)


def get_users_by_text_query(search_query, users_query_set=None):
    """Runs text search in user names and profile.
    For postgres, search also runs against user organization names.
    """
    if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):  # HEYSTACK DEPRECATED
        from openode.search.haystack import OpenodeSearchQuerySet
        qs = OpenodeSearchQuerySet().filter(content=search_query).models(User).get_django_queryset(User)
        return qs
    else:
        import openode
        if users_query_set is None:
            users_query_set = User.objects.all()
        if 'postgresql_psycopg2' in openode.get_database_engine_name():
            from openode.search import postgresql
            return postgresql.run_full_text_search(users_query_set, search_query)
        else:
            return users_query_set.filter(
                models.Q(username__icontains=search_query) |
                models.Q(about__icontains=search_query)
            )
        #if openode.get_database_engine_name().endswith('mysql') \
        #    and mysql.supports_full_text_search():
        #    return User.objects.filter(
        #        models.Q(username__search = search_query) |
        #        models.Q(about__search = search_query)
        #    )


def get_users_with_perm(perm):
    groups = Permission.objects.get(codename=perm).group_set.all()
    users_pks = []
    for group in groups:
        users_pks += [u.pk for u in group.user_set.filter(is_active=True)]
    users = Permission.objects.get(codename=perm).user_set.filter(is_active=True)
    users_pks += [u.pk for u in users]
    users_pks += [u.pk for u in User.objects.filter(is_superuser=True, is_active=True)]
    return User.objects.filter(pk__in=set(users_pks), is_active=True)

User.add_to_class(
    'organizations',
    models.ManyToManyField(
        Organization,
        through=OrganizationMembership,
        blank=True, related_name='users'
    )
)

User.add_to_class(
    'description',
    models.OneToOneField(Post,
        related_name='described_user', null=True, blank=True
    )
)

User.add_to_class(
    'status',
    models.CharField(
        max_length=2,
        default=const.DEFAULT_USER_STATUS,
        choices=const.USER_STATUS_CHOICES
    )
)

User.add_to_class('email_isvalid', models.BooleanField(default=False))  # @UndefinedVariable
User.add_to_class('email_key', models.CharField(max_length=32, null=True))
#hardcoded initial reputaion of 1, no setting for this one
User.add_to_class('gravatar', models.CharField(max_length=32))
#User.add_to_class('has_custom_avatar', models.BooleanField(default=False))
User.add_to_class(
    'avatar_type',
    models.CharField(max_length=1,
        choices=const.AVATAR_STATUS_CHOICE,
        default='n')
)
# User.add_to_class('gold', models.SmallIntegerField(default=0))
# User.add_to_class('silver', models.SmallIntegerField(default=0))
# User.add_to_class('bronze', models.SmallIntegerField(default=0))
User.add_to_class(
    'questions_per_page', # TODO: remove me and const.QUESTIONS_PER_PAGE_USER_CHOICES, we're no longer used!
    models.SmallIntegerField(
        choices=const.QUESTIONS_PER_PAGE_USER_CHOICES,
        default=10
    )
)
User.add_to_class('last_seen',
                  models.DateTimeField(default=datetime.datetime.now))
User.add_to_class('display_name', models.CharField(max_length=100, blank=True, default=''))

User.add_to_class('privacy_email_form', models.BooleanField(default=True))
User.add_to_class('privacy_show_followed', models.BooleanField(default=True))
# User.add_to_class('website', models.URLField(max_length=200, blank=True))
#location field is actually city
# User.add_to_class('location', models.CharField(max_length=100, blank=True))
# User.add_to_class('country', CountryField(blank=True))
# User.add_to_class('show_country', models.BooleanField(default=False))

# User.add_to_class('date_of_birth', models.DateField(null=True, blank=True))

#interesting tags and ignored tags are to store wildcard tag selections only
User.add_to_class('interesting_tags', models.TextField(blank=True))
User.add_to_class('ignored_tags', models.TextField(blank=True))
User.add_to_class('subscribed_tags', models.TextField(blank=True))
User.add_to_class('email_signature', models.TextField(blank=True))
User.add_to_class('change_password_key', models.CharField(max_length=255, blank=True, default=''))

User.add_to_class(
    'email_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES,
        default=const.EXCLUDE_IGNORED
    )
)
User.add_to_class(
    'display_tag_filter_strategy',
    models.SmallIntegerField(
        choices=const.TAG_EMAIL_FILTER_STRATEGY_CHOICES,
        default=const.INCLUDE_ALL
    )
)

User.add_to_class('new_response_count', models.IntegerField(default=0))
User.add_to_class('seen_response_count', models.IntegerField(default=0))
User.add_to_class('consecutive_days_visit_count', models.IntegerField(default=0))

# used for show/hide user on front site of web
User.add_to_class('is_hidden', models.BooleanField(default=False))

GRAVATAR_TEMPLATE = "https://www.gravatar.com/avatar/%(gravatar)s?s=%(size)d&amp;d=%(type)s&amp;r=PG"


def user_get_gravatar_url(self, size):
    """returns gravatar url
    """
    return GRAVATAR_TEMPLATE % {
        'gravatar': self.gravatar,
        'type': openode_settings.GRAVATAR_TYPE,
        'size': size,
    }


def user_get_default_avatar_url(self, size):
    """returns default avatar url
    """
    return skin_utils.get_media_url(openode_settings.DEFAULT_AVATAR_URL)


def user_get_avatar_url(self, size):
    """returns avatar url - by default - gravatar,
    but if application django-avatar is installed
    it will use avatar provided through that app
    """
    if 'avatar' in django_settings.INSTALLED_APPS:
        if self.avatar_type == 'n':
            # import avatar
            if openode_settings.ENABLE_GRAVATAR:  # avatar.settings.AVATAR_GRAVATAR_BACKUP:
                return self.get_gravatar_url(size)
            else:
                return self.get_default_avatar_url(size)
        elif self.avatar_type == 'a':
            kwargs = {'user_id': self.id, 'size': size}
            try:
                return reverse('avatar_render_primary', kwargs=kwargs)
            except NoReverseMatch:
                message = 'Please, make sure that avatar urls are in the urls.py '\
                          'or update your django-avatar app, '\
                          'currently it is impossible to serve avatars.'
                logging.critical(message)
                raise django_exceptions.ImproperlyConfigured(message)
        else:
            return self.get_gravatar_url(size)
    else:
        if openode_settings.ENABLE_GRAVATAR:
            return self.get_gravatar_url(size)
        else:
            return self.get_default_avatar_url(size)

User.add_to_class('get_avatar_url', user_get_avatar_url)


def user_update_avatar_type(self):
    """counts number of custom avatars
    and if zero, sets avatar_type to False,
    True otherwise. The method is called only if
    avatar application is installed.
    Saves the object.
    """

    if 'avatar' in django_settings.INSTALLED_APPS:
        if self.avatar_set.count() > 0:
            self.avatar_type = 'a'
        else:
            self.avatar_type = _check_gravatar(self.gravatar)
    else:
            self.avatar_type = _check_gravatar(self.gravatar)
    self.save()


def user_strip_email_signature(self, text):
    """strips email signature from the end of the text"""
    if self.email_signature.strip() == '':
        return text

    text = '\n'.join(text.splitlines())  # normalize the line endings
    while text.endswith(self.email_signature):
        text = text[0:-len(self.email_signature)]
    return text


def _check_gravatar(gravatar):
    gravatar_url = "https://www.gravatar.com/avatar/%s?d=404" % gravatar
    # code = urllib.urlopen(gravatar_url).getcode()
    if urllib.urlopen(gravatar_url).getcode() != 404:
        return 'g'  # gravatar
    else:
        return 'n'  # none


def user_get_old_vote_for_post(self, post):
    """returns previous vote for this post
    by the user or None, if does not exist

    raises assertion_error is number of old votes is > 1
    which is illegal
    """
    try:
        return Vote.objects.get(user=self, voted_post=post)
    except Vote.DoesNotExist:
        return None
    except Vote.MultipleObjectsReturned:
        raise AssertionError


def user_get_marked_tags(self, reason):
    """reason is a type of mark: good, bad or subscribed"""
    assert(reason in ('good', 'bad', 'subscribed'))
    if reason == 'subscribed':
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED == False:
            return Tag.objects.none()

    return Tag.objects.filter(
        user_selections__user=self,
        user_selections__reason=reason
    )

MARKED_TAG_PROPERTY_MAP = {
    'good': 'interesting_tags',
    'bad': 'ignored_tags',
    'subscribed': 'subscribed_tags'
}


def user_get_marked_tag_names(self, reason):
    """returns list of marked tag names for a give
    reason: good, bad, or subscribed
    will add wildcard tags as well, if used
    """
    if reason == 'subscribed':
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED == False:
            return list()

    tags = self.get_marked_tags(reason)
    tag_names = list(tags.values_list('name', flat=True))

    if openode_settings.USE_WILDCARD_TAGS:
        attr_name = MARKED_TAG_PROPERTY_MAP[reason]
        wildcard_tags = getattr(self, attr_name).split()
        tag_names.extend(wildcard_tags)

    return tag_names


def user_has_affinity_to_question(self, question=None, affinity_type=None):
    """returns True if number of tag overlap of the user tag
    selection with the question is 0 and False otherwise
    affinity_type can be either "like" or "dislike"
    """
    if affinity_type == 'like':
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            tag_selection_type = 'subscribed'
            wildcards = self.subscribed_tags.split()
        else:
            tag_selection_type = 'good'
            wildcards = self.interesting_tags.split()
    elif affinity_type == 'dislike':
        tag_selection_type = 'bad'
        wildcards = self.ignored_tags.split()
    else:
        raise ValueError('unexpected affinity type %s' % str(affinity_type))

    question_tags = question.thread.tags.all()
    intersecting_tag_selections = self.tag_selections.filter(
                                                tag__in=question_tags,
                                                reason=tag_selection_type
                                            )
    #count number of overlapping tags
    if intersecting_tag_selections.count() > 0:
        return True
    elif openode_settings.USE_WILDCARD_TAGS == False:
        return False

    #match question tags against wildcards
    for tag in question_tags:
        for wildcard in wildcards:
            if tag.name.startswith(wildcard[:-1]):
                return True
    return False


def user_has_ignored_wildcard_tags(self):
    """True if wildcard tags are on and
    user has some"""
    return (
        openode_settings.USE_WILDCARD_TAGS \
        and self.ignored_tags != ''
    )


def user_has_interesting_wildcard_tags(self):
    """True in wildcard tags aro on and
    user has nome interesting wildcard tags selected
    """
    return (
        openode_settings.USE_WILDCARD_TAGS \
        and self.interesting_tags != ''
    )


def user_can_create_tags(self):
    """true if user can create tags"""
    if openode_settings.ENABLE_TAG_MODERATION:
        return self.is_admin('openode.add_tag')
    else:
        return True


def user_can_have_strong_url(self):
    """True if user's homepage url can be
    followed by the search engine crawlers"""
    return True


def user_can_post_by_email(self):
    """True, if reply by email is enabled
    and user has sufficient reputatiton"""
    return openode_settings.REPLY_BY_EMAIL


def user_notify_users(
    self, notification_type=None, recipients=None, content_object=None
):
    """A utility function that creates instance
    of :class:`Activity` and adds recipients
    * `notification_type` - value should be one of TYPE_ACTIVITY_...
    * `recipients` - an iterable of user objects
    * `content_object` - any object related to the notification

    todo: possibly add checks on the content_object, depending on the
    notification_type
    """
    activity = Activity(
                user=self,
                activity_type=notification_type,
                content_object=content_object
            )
    activity.save()
    activity.add_recipients(recipients)


def user_get_notifications(self, notification_types=None, **kwargs):
    """returns query set of activity audit status objects"""
    return ActivityAuditStatus.objects.filter(
                        user=self,
                        activity__activity_type__in=notification_types,
                        **kwargs
                    )


def _assert_user_can(
                        user=None,
                        post=None, # related post (may be parent)
                        admin_or_moderator_required=False,
                        owner_can=False,
                        suspended_owner_cannot=False,
                        blocked_error_message=None,
                        suspended_error_message=None,
                        general_error_message=None
                    ):
    """generic helper assert for use in several
    User.assert_can_XYZ() calls regarding changing content

    user is required and at least one error message

    if assertion fails, method raises exception.PermissionDenied
    with appropriate text as a payload
    """
    if blocked_error_message and not user.is_active:
        error_message = blocked_error_message
    elif post and owner_can and user == post.get_owner():
        if suspended_owner_cannot and not user.is_active:
            if suspended_error_message:
                error_message = suspended_error_message
            else:
                error_message = general_error_message
            assert(error_message is not None)
            raise django_exceptions.PermissionDenied(error_message)
        else:
            return
        return
    elif suspended_error_message and not user.is_active:
        error_message = suspended_error_message
    elif user.is_admin():
        return
    else:
        if admin_or_moderator_required == False:
            return

    #if admin or moderator is required, then substitute the message
    if admin_or_moderator_required:
        error_message = general_error_message
    assert(error_message is not None)
    raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_approve_post_revision(self, post_revision=None):
    _assert_user_can(
        user=self,
        admin_or_moderator_required=True
    )


def user_assert_can_unaccept_best_answer(self, answer=None):
    assert getattr(answer, 'post_type', '') == 'answer'

    if not self.has_openode_perm('question_answer_accept', answer.thread):
        raise django_exceptions.PermissionDenied(
            _('Sorry, but you don\'t have permission to accept answer.')
        )


def user_assert_can_accept_best_answer(self, answer=None):
    assert getattr(answer, 'post_type', '') == 'answer'
    self.assert_can_unaccept_best_answer(answer)


def user_assert_can_vote_for_post(
                                self,
                                post=None,
                                direction=None,
                            ):
    """raises exceptions.PermissionDenied exception
    if user can't in fact upvote

    :param:direction can be 'up' or 'down'
    :param:post can be instance of question or answer
    """
    if self == post.author:
        raise django_exceptions.PermissionDenied(
            _('Sorry, you cannot vote for your own posts')
        )

    blocked_error_message = _(
                'Sorry your account appears to be blocked ' +
                'and you cannot vote - please contact the ' +
                'site administrator to resolve the issue'
            ),
    suspended_error_message = _(
                'Sorry your account appears to be suspended ' +
                'and you cannot vote - please contact the ' +
                'site administrator to resolve the issue'
            )

    assert(direction in ('up', 'down'))

    _assert_user_can(
        user=self,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message
    )


def user_assert_can_upload_file(request_user):

    # blocked_error_message = _('Sorry, blocked users cannot upload files')
    suspended_error_message = _('Sorry, suspended users cannot upload files')

    _assert_user_can(
        user=request_user,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_post_question(self):
    """raises exceptions.PermissionDenied with
    text that has the reason for the denial
    """

    blocked_message = get_i18n_message('BLOCKED_USERS_CANNOT_POST')
    suspended_message = get_i18n_message('SUSPENDED_USERS_CANNOT_POST')

    _assert_user_can(
            user=self,
            blocked_error_message=blocked_message,
            suspended_error_message=suspended_message
    )


def user_assert_can_post_answer(self, thread=None):
    """same as user_can_post_question
    """
    limit_answers = openode_settings.LIMIT_ONE_ANSWER_PER_USER and thread.thread_type == const.THREAD_TYPE_QUESTION
    if limit_answers and thread.has_answer_by_user(self):
        message = _(
            'Sorry, you already gave an answer, please edit it instead.'
        )
        raise openode_exceptions.AnswerAlreadyGiven(message)

    self.assert_can_post_question()


def user_assert_can_edit_comment(self, comment=None):
    """raises exceptions.PermissionDenied if user
    cannot edit comment with the reason given as message

    only owners, moderators or admins can edit comments
    """
    if self.is_administrator() or self.is_moderator():
        return
    else:
        if comment.author == self:
            if openode_settings.USE_TIME_LIMIT_TO_EDIT_COMMENT:
                now = datetime.datetime.now()
                delta_seconds = 60 * openode_settings.MINUTES_TO_EDIT_COMMENT
                if now - comment.added_at > datetime.timedelta(0, delta_seconds):
                    if comment.is_last():
                        return
                    error_message = ungettext(
                        'Sorry, comments (except the last one) are editable only '
                        'within %(minutes)s minute from posting',
                        'Sorry, comments (except the last one) are editable only '
                        'within %(minutes)s minutes from posting',
                        openode_settings.MINUTES_TO_EDIT_COMMENT
                    ) % {'minutes': openode_settings.MINUTES_TO_EDIT_COMMENT}
                    raise django_exceptions.PermissionDenied(error_message)
                return
            else:
                return

    error_message = _(
        'Sorry, but only post owners or moderators can edit comments'
    )
    raise django_exceptions.PermissionDenied(error_message)


def user_can_post_comment(self, parent_post=None):
    """a simplified method to test ability to comment
    """
    if parent_post and self == parent_post.author:
        return True
    if self.is_administrator_or_moderator():
        return True
    return False


def user_assert_can_post_comment(self, parent_post=None):
    """raises exceptions.PermissionDenied if
    user cannot post comment

    the reason will be in text of exception
    """
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can comment only your own posts'
            )
    blocked_message = get_i18n_message('BLOCKED_USERS_CANNOT_POST')


def user_assert_can_see_deleted_post(self, post=None):

    """attn: this assertion is independently coded in
    Question.get_answers call
    """

    error_message = _(
                        'This post has been deleted and can be seen only '
                        'by post owners, site administrators and moderators'
                    )
    _assert_user_can(
        user=self,
        post=post,
        admin_or_moderator_required=True,
        owner_can=True,
        general_error_message=error_message
    )


def user_assert_can_edit_deleted_post(self, post=None):
    assert(post.deleted == True)
    try:
        self.assert_can_see_deleted_post(post)
    except django_exceptions.PermissionDenied:
        error_message = _(
                    'Sorry, only moderators, site administrators '
                    'and post owners can edit deleted posts'
                )
        raise django_exceptions.PermissionDenied(error_message)


def user_assert_can_edit_post(self, post=None):
    """assertion that raises exceptions.PermissionDenied
    when user is not authorised to edit this post
    """

    if post.deleted == True:
        self.assert_can_edit_deleted_post(post)
        return

    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot edit posts'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can edit only your own posts'
            )

    _assert_user_can(
        user=self,
        post=post,
        owner_can=True,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_edit_thread(self, thread=None):
    assert getattr(thread, 'thread_type', '') in ('question', 'discussion', "document")
    self.assert_can_edit_post(thread._main_post())


def user_assert_can_edit_answer(self, answer=None):
    assert getattr(answer, 'post_type', '') == 'answer'
    self.assert_can_edit_post(answer)


def user_assert_can_delete_post(self, post=None):
    post_type = getattr(post, 'post_type', '')

    if post_type in ('question', 'discussion', "document"):
        self.assert_can_delete_question(question=post)

    elif post_type == 'answer':
        self.assert_can_delete_answer(answer=post)

    elif post_type == 'comment':
        self.assert_can_delete_comment(comment=post)

    else:
        raise ValueError('Invalid post_type!')


def user_assert_can_restore_post(self, post=None):
    """can_restore_rule is the same as can_delete
    """
    self.assert_can_delete_post(post=post)


def user_assert_can_delete_question(self, question=None):
    """rules are the same as to delete answer,
    except if question has answers already, when owner
    cannot delete unless s/he is and adinistrator or moderator
    """

    #cheating here. can_delete_answer wants argument named
    #"question", so the argument name is skipped
    self.assert_can_delete_answer(question)
    if self == question.get_owner():
        #if there are answers by other people,
        #then deny, unless user in admin or moderator
        answer_count = question.thread.all_answers().exclude(
            author=self
        ).exclude(
            points__lte=0
        ).count()

        if answer_count > 0:
            if self.is_administrator() or self.is_moderator():
                return
            else:
                msg = ungettext(
                    'Sorry, cannot delete your question since it '
                    'has an upvoted answer posted by someone else',
                    'Sorry, cannot delete your question since it '
                    'has some upvoted answers posted by other users',
                    answer_count
                )
                raise django_exceptions.PermissionDenied(msg)


def user_assert_can_delete_answer(self, answer=None):
    """intentionally use "post" word in the messages
    instead of "answer", because this logic also applies to
    assert on deleting question (in addition to some special rules)
    """
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot delete posts'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can delete only your own posts'
            )

    _assert_user_can(
        user=self,
        post=answer,
        owner_can=True,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_close_thread(self, thread=None):
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot close questions'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you cannot close questions'
            )

    _assert_user_can(
        user=self,
        post=thread._main_post(),
        owner_can=True,
        suspended_owner_cannot=True,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_reopen_thread(self, thread=None):

    general_error_message = _(
                        'Sorry, only administrators, moderators '
                        'or post owners'
                        'can reopen questions.'
                    )

    blocked_error_message = _(
            'Sorry, you cannot reopen questions '
            'because your account is blocked'
        )

    suspended_error_message = _(
            'Sorry, you cannot reopen questions '
            'because your account is suspended'
        )

    _assert_user_can(
        user=self,
        post=thread._main_post(),
        owner_can=True,
        suspended_owner_cannot=True,
        general_error_message=general_error_message,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message
    )


def user_assert_can_flag_offensive(self, post=None):

    assert(post is not None)

    double_flagging_error_message = _(
        'You have flagged this question before and '
        'cannot do it more than once'
    )

    if self.get_flags_for_post(post).count() > 0:
        raise openode_exceptions.DuplicateCommand(double_flagging_error_message)

    blocked_error_message = _(
        'Sorry, since your account is blocked '
        'you cannot flag posts as offensive'
    )

    suspended_error_message = _(
        'Sorry, your account appears to be suspended and you cannot make new posts '
        'until this issue is resolved. You can, however edit your existing posts. '
        'Please contact the forum administrator to reach a resolution.'
    )

    _assert_user_can(
        user=self,
        post=post,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return
    else:
        flag_count_today = self.get_flag_count_posted_today()
        if flag_count_today >= openode_settings.MAX_FLAGS_PER_USER_PER_DAY:
            flags_exceeded_error_message = _(
                'Sorry, you have exhausted the maximum number of '
                '%(max_flags_per_day)s offensive flags per day.'
            ) % {
                    'max_flags_per_day': \
                    openode_settings.MAX_FLAGS_PER_USER_PER_DAY
                }
            raise django_exceptions.PermissionDenied(flags_exceeded_error_message)


def user_assert_can_remove_flag_offensive(self, post=None):

    assert(post is not None)

    non_existing_flagging_error_message = _('cannot remove non-existing flag')

    if self.get_flags_for_post(post).count() < 1:
        raise django_exceptions.PermissionDenied(non_existing_flagging_error_message)

    blocked_error_message = _(
        'Sorry, since your account is blocked you cannot remove flags'
    )

    suspended_error_message = _(
        'Sorry, your account appears to be suspended and you cannot remove flags. '
        'Please contact the forum administrator to reach a resolution.'
    )

    _assert_user_can(
        user=self,
        post=post,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return


def user_assert_can_remove_all_flags_offensive(self, post=None):
    assert(post is not None)
    permission_denied_message = _("you don't have the permission to remove all flags")
    non_existing_flagging_error_message = _('no flags for this entry')

    # Check if the post is flagged by anyone
    post_content_type = ContentType.objects.get_for_model(post)
    all_flags = Activity.objects.filter(
                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                        content_type=post_content_type, object_id=post.id
                    )
    if all_flags.count() < 1:
        raise django_exceptions.PermissionDenied(non_existing_flagging_error_message)
    #one extra assertion
    if self.is_administrator() or self.is_moderator():
        return
    else:
        raise django_exceptions.PermissionDenied(permission_denied_message)


def user_assert_can_retag_question(self, question=None):

    # TODO: use Thread.can_retag method
    if not self.has_perm('openode.change_tag'):
        raise django_exceptions.PermissionDenied(_('You don\'t have permission to retag anything.'))

    if question.deleted == True:
        try:
            self.assert_can_edit_deleted_post(question)
        except django_exceptions.PermissionDenied:
            error_message = _(
                            'Sorry, only question owners, '
                            'site administrators and moderators '
                            'can retag deleted questions'
                        )
            raise django_exceptions.PermissionDenied(error_message)

    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot retag questions'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can retag only your own questions'
            )

    _assert_user_can(
        user=self,
        post=question,
        owner_can=True,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_delete_comment(self, comment=None):
    blocked_error_message = _(
                'Sorry, since your account is blocked '
                'you cannot delete comment'
            )
    suspended_error_message = _(
                'Sorry, since your account is suspended '
                'you can delete only your own comments'
            )

    _assert_user_can(
        user=self,
        post=comment,
        owner_can=True,
        blocked_error_message=blocked_error_message,
        suspended_error_message=suspended_error_message,
    )


def user_assert_can_revoke_old_vote(self, vote):
    """raises exceptions.PermissionDenied if old vote
    cannot be revoked due to age of the vote
    """
    if (datetime.datetime.now().day - vote.voted_at.day) \
        >= openode_settings.MAX_DAYS_TO_CANCEL_VOTE:
        raise django_exceptions.PermissionDenied(
            _('sorry, but older votes cannot be revoked')
        )


def user_get_unused_votes_today(self):
    """returns number of votes that are
    still available to the user today
    """
    today = datetime.date.today()
    one_day_interval = (today, today + datetime.timedelta(1))

    used_votes = Vote.objects.filter(
                                user=self,
                                voted_at__range=one_day_interval
                            ).count()

    available_votes = openode_settings.MAX_VOTES_PER_USER_PER_DAY - used_votes
    return max(0, available_votes)


def user_post_comment(
                    self,
                    parent_post=None,
                    body_text=None,
                    timestamp=None,
                    by_email=False
                ):
    """post a comment on behalf of the user
    to parent_post
    """

    if body_text is None:
        raise ValueError('body_text is required to post comment')
    if parent_post is None:
        raise ValueError('parent_post is required to post comment')
    if timestamp is None:
        timestamp = datetime.datetime.now()

    self.assert_can_post_comment(parent_post=parent_post)

    comment = parent_post.add_comment(
                    user=self,
                    comment=body_text,
                    added_at=timestamp,
                    by_email=by_email
                )

    if parent_post.post_type == const.POST_TYPE_THREAD_POST:
        self.log(comment, const.LOG_ACTION_COMMENT_ANSWER)
    elif parent_post.post_type == const.POST_TYPE_QUESTION:
        self.log(comment, const.LOG_ACTION_COMMENT_QUESTION)

    parent_post.thread.invalidate_cached_data()
    immediately_notify_users(comment)
    return comment


def user_post_object_description(
                    self,
                    obj=None,
                    body_text=None,
                    timestamp=None
                ):
    """Creates an object description post and assigns it
    to the given object. Returns the newly created post"""
    if isinstance(obj, Organization):
        post_type = 'organization_description'
    elif isinstance(obj, User):
        post_type = 'user_description'
    else:
        raise NotImplementedError()

    description_post = Post.objects.create_new_description(
                                            post_type=post_type,
                                            author=self,
                                            text=body_text
                                        )
    obj.description = description_post
    obj.save()
    return description_post


def user_post_anonymous_openode_content(user, session_key):
    """posts any posts added just before logging in
    the posts are identified by the session key, thus the second argument

    this function is used by the signal handler with a similar name
    """
    aq_list = AnonymousQuestion.objects.filter(session_key=session_key)
    aa_list = AnonymousAnswer.objects.filter(session_key=session_key)
    #from openode.conf import settings as openode_settings
    if openode_settings.EMAIL_VALIDATION == True:  # add user to the record
        for aq in aq_list:
            aq.author = user
            aq.save()
        for aa in aa_list:
            aa.author = user
            aa.save()
        #maybe add pending posts message?
    else:
        if user.is_blocked():
            msg = get_i18n_message('BLOCKED_USERS_CANNOT_POST')
            user.message_set.create(message=msg)
        elif user.is_suspended():
            msg = get_i18n_message('SUSPENDED_USERS_CANNOT_POST')
            user.message_set.create(message=msg)
        else:
            for aq in aq_list:
                aq.publish(user)
            for aa in aa_list:
                aa.publish(user)


def user_mark_tags(
            self,
            tagnames=None,
            wildcards=None,
            reason=None,
            action=None
        ):
    """subscribe for or ignore a list of tags

    * ``tagnames`` and ``wildcards`` are lists of
      pure tags and wildcard tags, respectively
    * ``reason`` - either "good" or "bad"
    * ``action`` - eitrer "add" or "remove"
    """
    cleaned_wildcards = list()
    assert(action in ('add', 'remove'))
    if action == 'add':
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            assert(reason in ('good', 'bad', 'subscribed'))
        else:
            assert(reason in ('good', 'bad'))
    if wildcards:
        cleaned_wildcards = self.update_wildcard_tag_selections(
            action=action,
            reason=reason,
            wildcards=wildcards
        )
    if tagnames is None:
        tagnames = list()

    #below we update normal tag selections
    marked_ts = MarkedTag.objects.filter(
                                    user=self,
                                    tag__name__in=tagnames
                                )
    #Marks for "good" and "bad" reasons are exclusive,
    #to make it impossible to "like" and "dislike" something at the same time
    #but the subscribed set is independent - e.g. you can dislike a topic
    #and still subscribe for it.
    if reason == 'subscribed':
        #don't touch good/bad marks
        marked_ts = marked_ts.filter(reason='subscribed')
    else:
        #and in this case don't touch subscribed tags
        marked_ts = marked_ts.exclude(reason='subscribed')

    #todo: use the user api methods here instead of the straight ORM
    cleaned_tagnames = list()  # those that were actually updated
    if action == 'remove':
        logging.debug('deleting tag marks: %s' % ','.join(tagnames))
        marked_ts.delete()
    else:
        marked_names = marked_ts.values_list('tag__name', flat=True)
        if len(marked_names) < len(tagnames):
            unmarked_names = set(tagnames).difference(set(marked_names))
            ts = Tag.objects.filter(name__in=unmarked_names)
            new_marks = list()
            for tag in ts:
                MarkedTag(
                    user=self,
                    reason=reason,
                    tag=tag
                ).save()
                new_marks.append(tag.name)
            cleaned_tagnames.extend(marked_names)
            cleaned_tagnames.extend(new_marks)
        else:
            if reason in ('good', 'bad'):  # to maintain exclusivity of 'good' and 'bad'
                marked_ts.update(reason=reason)
            cleaned_tagnames = tagnames

    return cleaned_tagnames, cleaned_wildcards


@auto_now_timestamp
def user_retag_question(
                    self,
                    question=None,
                    tags=None,
                    timestamp=None,
                    silent=False
                ):
    self.assert_can_retag_question(question)
    question.thread.retag(
        retagged_by=self,
        retagged_at=timestamp,
        tagnames=tags,
        silent=silent
    )
    question.thread.invalidate_cached_data()


@auto_now_timestamp
def user_accept_best_answer(self, answer=None, timestamp=None, cancel=False, force=False):
    if cancel:
        return self.unaccept_best_answer(
            answer=answer,
            timestamp=timestamp,
            force=force
        )

    if force == False:
        self.assert_can_accept_best_answer(answer)

    if answer.accepted() == True:
        return

    prev_accepted_answer = answer.thread.accepted_answer
    if prev_accepted_answer:
        auth.onAnswerAcceptCanceled(prev_accepted_answer, self)

    auth.onAnswerAccept(answer, self, timestamp=timestamp)


@auto_now_timestamp
def user_unaccept_best_answer(
                self, answer=None,
                timestamp=None,
                force=False
            ):
    if force == False:
        self.assert_can_unaccept_best_answer(answer)
    if not answer.accepted():
        return
    auth.onAnswerAcceptCanceled(answer, self)


@auto_now_timestamp
def user_delete_comment(
                    self,
                    comment=None,
                    timestamp=None
                ):
    self.assert_can_delete_comment(comment=comment)
    #todo: we want to do this
    #comment.deleted = True
    #comment.deleted_by = self
    #comment.deleted_at = timestamp
    #comment.save()
    comment.delete()
    comment.thread.invalidate_cached_data()


@auto_now_timestamp
def user_delete_answer(
                    self,
                    answer=None,
                    timestamp=None
                ):
    self.assert_can_delete_answer(answer=answer)
    answer.deleted = True
    answer.deleted_by = self
    answer.deleted_at = timestamp
    answer.save()

    answer.thread.update_answer_count()
    answer.thread.invalidate_cached_data()
    logging.debug('updated answer count to %d' % answer.thread.answer_count)

    signals.delete_question_or_answer.send(
        sender=answer.__class__,
        instance=answer,
        delete_by=self
    )


@auto_now_timestamp
def user_delete_question(
                    self,
                    question=None,
                    timestamp=None
                ):
    self.assert_can_delete_question(question=question)

    question.deleted = True
    question.deleted_by = self
    question.deleted_at = timestamp
    question.save()

    for tag in list(question.thread.tags.all()):
        if tag.used_count == 1:
            tag.deleted = True
            tag.deleted_by = self
            tag.deleted_at = timestamp
        else:
            tag.used_count = tag.used_count - 1
        tag.save()

    signals.delete_question_or_answer.send(
        sender=question.__class__,
        instance=question,
        delete_by=self
    )


@auto_now_timestamp
def user_close_thread(self, thread=None, reason=None, timestamp=None):
    self.assert_can_close_thread(thread)
    thread.set_closed_status(closed=True, closed_by=self, closed_at=timestamp, close_reason=reason)
    if thread.is_question():
        self.log(thread, const.LOG_ACTION_CLOSE_QUESTION)
    elif thread.is_discussion():
        self.log(thread, const.LOG_ACTION_CLOSE_DISCUSSION)


@auto_now_timestamp
def user_reopen_thread(self, thread=None, timestamp=None):
    self.assert_can_reopen_thread(thread)
    thread.set_closed_status(closed=False, closed_by=self, closed_at=timestamp, close_reason=None)
    if thread.is_question():
        self.log(thread, const.LOG_ACTION_REOPEN_QUESTION)
    elif thread.is_discussion():
        self.log(thread, const.LOG_ACTION_REOPEN_DISCUSSION)


@auto_now_timestamp
def user_delete_post(self, post=None, timestamp=None):
    """generic delete method for all kinds of posts

    if there is no use cases for it, the method will be removed
    """
    if post.post_type == 'comment':
        self.delete_comment(comment=post, timestamp=timestamp)
    elif post.is_answer():
        self.delete_answer(answer=post, timestamp=timestamp)
    elif post.post_type in ('question', 'discussion', "document"):
        self.delete_question(question=post, timestamp=timestamp)
    else:
        raise TypeError('either Comment, Question or Answer expected')
    post.thread.invalidate_cached_data()


def user_restore_post(self, post=None, timestamp=None):
    #here timestamp is not used, I guess added for consistency

    self.assert_can_restore_post(post)

    if post.post_type in ('question', "discussion", 'answer', "document"):
        post.deleted = False
        post.deleted_by = None
        post.deleted_at = None
        post.save()
        post.thread.invalidate_cached_data()
        if post.is_answer():
            post.thread.update_answer_count()
        else:
            #todo: make sure that these tags actually exist
            #some may have since been deleted for good
            #or merged into others
            for tag in list(post.thread.tags.all()):
                if tag.used_count == 1 and tag.deleted:
                    tag.deleted = False
                    tag.deleted_by = None
                    tag.deleted_at = None
                    tag.save()
    else:
        raise NotImplementedError()


def user_post_thread(
        self, title=None, body_text='', tags='', timestamp=None, by_email=False,
        email_address=None, node=None, thread_type=None, category=None, external_access=None,
        ):
    """makes an assertion whether user can post the post
    then posts it and returns the post object"""

    self.assert_can_post_question()

    if body_text == '':  # a hack to allow bodyless post
        body_text = ' '

    if title is None:
        raise ValueError('Title is required to post post')
    if timestamp is None:
        timestamp = datetime.datetime.now()

    #todo: split this into "create thread" + "add queston", if text exists
    #or maybe just add a blank post post anyway
    thread = Thread.objects.create_new(
        author=self,
        title=title,
        text=body_text,
        tagnames=tags,
        added_at=timestamp,
        by_email=by_email,
        email_address=email_address,
        node=node,
        thread_type=thread_type,
        category=category,
        external_access=external_access
    )
    post = thread._main_post()

    if post.thread.can_retag(self):
        # create tags
        post.thread.update_tags(
            timestamp=timestamp,
            tagnames=tags,
            user=self,
        )

    if post.author != self:
        raise ValueError('question.author != self')
    post.author = self  # HACK: Some tests require that post.author IS exactly the same object as self-user (kind of identity map which Django doesn't provide),
                            #       because they set some attributes for that instance and expect them to be changed also for question.author

    if thread_type == const.THREAD_TYPE_QUESTION:
        self.log(thread, const.LOG_ACTION_ASK_QUESTION)
    elif thread_type == const.THREAD_TYPE_DOCUMENT:
        self.log(thread, const.LOG_ACTION_CREATE_DOCUMENT)
    elif thread_type == const.THREAD_TYPE_DISCUSSION:
        self.log(thread, const.LOG_ACTION_CREATE_DISCUSSION)
    immediately_notify_users(post)
    return post


def user_has_perm(self, perm, obj=None):
    """
        The best point to bypass any django.auth perm
    """

    # TAG PERMS BYPASS
    if perm == "openode.change_tag" and self.is_authenticated():
        return True

    ###################################

    elif perm == "can_answer_in_question_flow":
        if not self.is_authenticated():
            return False

        if self.has_perm('can_solve_question_flow'):
            return True

        if obj:
            return self.question_flow_interviewee_threads.filter(pk=obj.pk).exists()
        else:
            return self.question_flow_interviewee_threads.exists()

    ###################################

    elif perm == "can_solve_question_flow":
        return bool(
            self.is_authenticated()
            and
            NodeUser.objects.filter(
                    user=self,
                    node__is_question_flow_enabled=True,
                ).filter(
                    Q(role__in=[const.NODE_USER_ROLE_MEMBER, const.NODE_USER_ROLE_MANAGER])
                    |
                    Q(is_responsible=True)
                ).exists()
        )

    ###################################

    elif perm == "can_accept_answer":
        answer = obj

        return bool(
            self.is_authenticated()
            and
            (
                not answer.thread.node.is_question_flow_enabled
                or
                answer.thread.node.node_users.filter(role=const.NODE_USER_ROLE_MANAGER, user=self).exists()
                or
                answer.thread.node.node_users.filter(is_responsible=True, user=self).exists()
            )
        )

    return _user_has_perm(self, perm, obj=obj)


@auto_now_timestamp
def user_edit_comment(
                    self,
                    comment_post=None,
                    body_text=None,
                    timestamp=None,
                    by_email=False
                ):
    """apply edit to a comment, the method does not
    change the comments timestamp and no signals are sent
    todo: see how this can be merged with edit_post
    todo: add timestamp
    """
    self.assert_can_edit_comment(comment_post)
    comment_post.apply_edit(text=body_text, edited_at=timestamp, edited_by=self,
        by_email=by_email)
    comment_post.thread.invalidate_cached_data()
    immediately_notify_users(comment_post)


def user_edit_post(self,
                post=None,
                body_text=None,
                revision_comment=None,
                timestamp=None,
                by_email=False
            ):
    """a simple method that edits post body
    todo: unify it in the style of just a generic post
    this requires refactoring of underlying functions
    because we cannot bypass the permissions checks set within
    """
    if post.is_comment():
        self.edit_comment(
                comment_post=post,
                body_text=body_text,
                by_email=by_email
            )
    elif post.is_answer():
        self.edit_answer(
            answer=post,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email
        )
    elif post.is_question() or post.is_discussion():
        self.edit_thread(
            thread=post.thread,
            body_text=body_text,
            timestamp=timestamp,
            revision_comment=revision_comment,
            by_email=by_email
        )
    elif post.is_organization_description() or post.is_user_description():
        post.apply_edit(
            edited_at=timestamp,
            edited_by=self,
            text=body_text,
            #todo: summary name clash in question and question revision
            comment=revision_comment,
            by_email=False
        )
    else:
        raise NotImplementedError()


@auto_now_timestamp
def user_edit_thread(
                self,
                thread=None,
                title=None,
                body_text=None,
                revision_comment=None,
                tags=None,
                timestamp=None,
                force=False,  # if True - bypass the assert
                by_email=False
            ):
    if force == False:
        self.assert_can_edit_thread(thread)

    thread._main_post().apply_edit(
        edited_at=timestamp,
        edited_by=self,
        title=title,
        text=body_text,
        #todo: summary name clash in question and question revision
        comment=revision_comment,
        tags=tags,
        by_email=by_email
    )

    thread.invalidate_cached_data()
    immediately_notify_users(thread._main_post())


@auto_now_timestamp
def user_edit_answer(
                    self,
                    answer=None,
                    body_text=None,
                    revision_comment=None,
                    timestamp=None,
                    force=False,   # if True - bypass the assert
                    by_email=False
                ):
    if force == False:
        self.assert_can_edit_answer(answer)

    answer.apply_edit(
        edited_at=timestamp,
        edited_by=self,
        text=body_text,
        comment=revision_comment,
        by_email=by_email
    )
    if answer.thread:
        answer.thread.invalidate_cached_data()
    immediately_notify_users(answer)
    self.log(answer, const.LOG_ACTION_UPDATE_ANSWER)


@auto_now_timestamp
def user_create_post_reject_reason(
    self, title=None, details=None, timestamp=None
):
    """creates and returs the post reject reason"""
    reason = PostFlagReason(
        title=title,
        added_at=timestamp,
        author=self
    )

    #todo - need post_object.create_new() method
    details = Post(
        post_type='reject_reason',
        author=self,
        added_at=timestamp,
        text=details
    )
    details.parse_and_save(author=self)
    details.add_revision(
        author=self,
        revised_at=timestamp,
        text=details,
        comment=const.POST_STATUS['default_version']
    )

    reason.details = details
    reason.save()
    return reason


@auto_now_timestamp
def user_edit_post_reject_reason(
    self, reason, title=None, details=None, timestamp=None
):
    reason.title = title
    reason.save()
    reason.details.apply_edit(
        edited_by=self,
        edited_at=timestamp,
        text=details
    )


def user_post_answer(self, question=None, body_text=None, follow=False, timestamp=None, by_email=False):

    # todo: move this to assertion - user_assert_can_post_answer

    if self == question.author and not self.is_administrator():

        # check date and rep required to post answer to own question

        delta = datetime.timedelta(openode_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION)

        now = datetime.datetime.now()
        asked = question.added_at
        #todo: this is an assertion, must be moved out
        if now - asked < delta:
            diff = asked + delta - now
            days = diff.days
            hours = int(diff.seconds / 3600)
            minutes = int(diff.seconds / 60)

            if days > 2:
                if asked.year == now.year:
                    date_token = asked.strftime("%b %d")
                else:
                    date_token = asked.strftime("%b %d '%y")
                left = _('on %(date)s') % {'date': date_token}
            elif days == 2:
                left = _('in two days')
            elif days == 1:
                left = _('tomorrow')
            elif minutes >= 60:
                left = ungettext('in %(hr)d hour', 'in %(hr)d hours', hours) % {'hr': hours}
            else:
                left = ungettext('in %(min)d min', 'in %(min)d mins', minutes) % {'min': minutes}
            day = ungettext('%(days)d day', '%(days)d days', openode_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION) % {'days': openode_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION}
            error_message = _(
                'New users must wait %(days)s before answering their own question. '
                ' You can post an answer %(left)s'
                ) % {'days': day, 'left': left}
            assert(error_message is not None)
            raise django_exceptions.PermissionDenied(error_message)

    self.assert_can_post_answer(thread=question.thread)

    if getattr(question, 'post_type', '') not in ('question', 'discussion'):
        raise TypeError('question argument must be provided')
    if body_text is None:
        raise ValueError('Body text is required to post answer')
    if timestamp is None:
        timestamp = datetime.datetime.now()

    answer_post = Post.objects.create_new_answer(
        thread=question.thread,
        author=self,
        text=body_text,
        added_at=timestamp,
        email_notify=follow,
        by_email=by_email
    )

    # print 40 * "-"
    # print question.thread.is_question()
    # print question.thread.node.is_question_flow_enabled
    # print question.thread.question_flow_state

    # if question.thread.is_question() \
    #     and question.thread.node.is_question_flow_enabled:

    #     question.thread.question_flow_state = const.QUESTION_FLOW_STATE_ANSWERED
    #     question.thread.save()

    if question.thread.thread_type == const.THREAD_TYPE_QUESTION:
        self.log(answer_post, const.LOG_ACTION_ANSWER)
    elif question.thread.thread_type == const.THREAD_TYPE_DISCUSSION:
        self.log(answer_post, const.LOG_ACTION_DISCUSSION_POST)

    answer_post.thread.invalidate_cached_data()
    immediately_notify_users(answer_post)
    return answer_post


def user_visit_thread(self, thread=None, timestamp=None):
    """create a ThreadView record
    on behalf of the user represented by the self object
    and mark it as taking place at timestamp time

    and remove pending on-screen notifications about anything in
    the post - question, answer or comments

    DEPRECATED: use Thread.visit !!!

    """
    if timestamp is None:
        timestamp = datetime.datetime.now()

    try:
        ThreadView.objects.filter(
            user=self,
            thread=thread
        ).update(
            last_visit=timestamp
        )
    except ThreadView.DoesNotExist:
        ThreadView(
            user=self,
            thread=thread,
            last_visit=timestamp
        ).save()

    #filter memo objects on response activities directed to the qurrent user
    #that refer to the children of the currently
    #viewed question and clear them for the current user
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    audit_records = ActivityAuditStatus.objects.filter(
            user=self,
            status=ActivityAuditStatus.STATUS_NEW,
            activity__question=thread._main_post()
        )

    cleared_record_count = audit_records.filter(
            activity__activity_type__in=ACTIVITY_TYPES
        ).update(
            status=ActivityAuditStatus.STATUS_SEEN
        )

    if cleared_record_count > 0:
        self.update_response_counts()

    #finally, mark admin memo objects if applicable
    #the admin response counts are not denormalized b/c they are easy to obtain
    if self.is_moderator() or self.is_administrator():
        audit_records.filter(
            activity__activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE
        ).update(
            status=ActivityAuditStatus.STATUS_SEEN
        )


def user_is_username_taken(cls, username):
    try:
        cls.objects.get(username=username)
        return True
    except cls.MultipleObjectsReturned:
        return True
    except cls.DoesNotExist:
        return False


def user_is_administrator(self):
    """checks whether user in the forum site administrator
    the admin must be both superuser and staff member
    the latter is because staff membership is required
    to access the live settings"""
    return (self.is_superuser and self.is_staff)


def user_remove_admin_status(self):
    self.is_staff = False
    self.is_superuser = False


def user_set_admin_status(self):
    self.is_staff = True
    self.is_superuser = True


def user_add_missing_openode_subscriptions(self):
    from openode import forms  # need to avoid circular dependency
    form = forms.EditUserEmailFeedsForm()
    need_feed_types = form.get_db_model_subscription_type_names()
    have_feed_types = EmailFeedSetting.objects.filter(
        subscriber=self
    ).values_list(
        'feed_type', flat=True
    )
    missing_feed_types = set(need_feed_types) - set(have_feed_types)
    for missing_feed_type in missing_feed_types:
        attr_key = 'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_%s' % missing_feed_type.upper()
        freq = getattr(openode_settings, attr_key)
        feed_setting = EmailFeedSetting(
            subscriber=self,
            feed_type=missing_feed_type,
            frequency=freq
        )
        feed_setting.save()


def user_is_moderator(self):
    return True


def user_is_administrator_or_moderator(self):
    return (self.is_administrator() or self.is_moderator())


def user_is_suspended(self):
    #DEPRECATED
    return not self.is_active


def user_is_blocked(self):
    #DEPRECATED
    return not self.is_active


def user_is_watched(self):
    #DEPRECATED
    return not self.is_active


def user_is_approved(self):
    #DEPRECATED
    return not self.is_active


def user_is_owner_of(self, obj):
    """True if user owns object
    False otherwise
    """
    if isinstance(obj, Post) and obj.is_question():
        return self == obj.author
    else:
        raise NotImplementedError()


def get_name_of_anonymous_user():
    """Returns name of the anonymous user
    either comes from the live settings or the language
    translation

    very possible that this function does not belong here
    """
    if openode_settings.NAME_OF_ANONYMOUS_USER:
        return openode_settings.NAME_OF_ANONYMOUS_USER
    else:
        return _('Anonymous')


def user_get_anonymous_name(self):
    """Returns name of anonymous user
    - convinience method for use in the template
    macros that accept user as parameter
    """
    return get_name_of_anonymous_user()


def user_set_status(self, new_status):
    """sets new status to user

    this method understands that administrator status is
    stored in the User.is_superuser field, but
    everything else in User.status field

    there is a slight aberration - administrator status
    can be removed, but not added yet

    if new status is applied to user, then the record is
    committed to the database
    """
    #d - administrator
    #m - moderator
    #s - suspended
    #b - blocked
    #w - watched
    #a - approved (regular user)
    assert(new_status in ('d', 'm', 's', 'b', 'w', 'a'))
    if new_status == self.status:
        return

    #clear admin status if user was an administrator
    #because this function is not dealing with the site admins

    if new_status == 'd':
        #create a new admin
        self.set_admin_status()
    else:
        #This was the old method, kept in the else clause when changing
        #to admin, so if you change the status to another thing that
        #is not Administrator it will simply remove admin if the user have
        #that permission, it will mostly be false.
        if self.is_administrator():
            self.remove_admin_status()

    #when toggling between blocked and non-blocked status
    #we need to invalidate question page caches, b/c they contain
    #user's url, which must be hidden in the blocked state
    if 'b' in (new_status, self.status) and new_status != self.status:
        threads = Thread.objects.get_for_user(self)
        for thread in threads:
            thread.invalidate_cached_post_data()

    self.status = new_status
    self.save()


def user_get_status_display(self, soft=False):
    if self.is_administrator():
        return _('Site Adminstrator')
    elif self.is_moderator():
        return _('Forum Moderator')
    elif self.is_suspended():
        return _('Suspended User')
    elif self.is_blocked():
        return _('Blocked User')
    elif soft == True:
        return _('Registered User')
    elif self.is_watched():
        return _('Watched User')
    elif self.is_approved():
        return _('Approved User')
    else:
        raise ValueError('Unknown user status')


def user_can_moderate_user(self, other):
    if self.is_administrator():
        return True
    elif self.is_moderator():
        if other.is_moderator() or other.is_administrator():
            return False
        else:
            return True
    else:
        return False


def user_get_followed_question_alert_frequency(self):
    feed_setting, created = EmailFeedSetting.objects.get_or_create(
                                    subscriber=self,
                                    feed_type='q_sel'
                                )
    return feed_setting.frequency


def user_subscribe_for_followed_question_alerts(self):
    """turns on daily subscription for selected questions
    otherwise does nothing

    Returns ``True`` if the subscription was turned on and
    ``False`` otherwise
    """
    feed_setting, created = EmailFeedSetting.objects.get_or_create(
                                                        subscriber=self,
                                                        feed_type='q_sel'
                                                    )
    if feed_setting.frequency == 'n':
        feed_setting.frequency = 'd'
        feed_setting.save()
        return True
    return False


def user_get_tag_filtered_questions(self, questions=None):
    """Returns a query set of questions, tag filtered according
    to the user choices. Parameter ``questions`` can be either ``None``
    or a starting query set.
    """
    if questions is None:
        questions = Post.objects.get_questions()

    if self.email_tag_filter_strategy == const.EXCLUDE_IGNORED:

        ignored_tags = Tag.objects.filter(
                                user_selections__reason='bad',
                                user_selections__user=self
                            )

        wk = self.ignored_tags.strip().split()
        ignored_by_wildcards = Tag.objects.get_by_wildcards(wk)

        return questions.exclude(
                        thread__tags__in=ignored_tags
                    ).exclude(
                        thread__tags__in=ignored_by_wildcards
                    ).distinct()
    elif self.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            reason = 'subscribed'
            wk = self.subscribed_tags.strip().split()
        else:
            reason = 'good'
            wk = self.interesting_tags.strip().split()

        selected_tags = Tag.objects.filter(
                                user_selections__reason=reason,
                                user_selections__user=self
                            )

        selected_by_wildcards = Tag.objects.get_by_wildcards(wk)

        tag_filter = models.Q(thread__tags__in=list(selected_tags)) \
                    | models.Q(thread__tags__in=list(selected_by_wildcards))

        return questions.filter(tag_filter).distinct()
    else:
        return questions


def get_messages(self):
    messages = []
    for m in self.message_set.all():
        messages.append(m.message)
    return messages


def delete_messages(self):
    self.message_set.all().delete()


#todo: find where this is used and replace with get_absolute_url
def get_profile_url(self):
    """Returns the URL for this User's profile."""
    return reverse(
                'user_profile',
                kwargs={'id': self.id}
            )


def user_get_absolute_url(self):
    return self.get_profile_url()

User.add_to_class('get_absolute_url', user_get_absolute_url)


def user_get_organizations(self):
    """returns a query set of organizations to which user belongs"""
    #todo: maybe cache this query
    return self.organizations.filter(organizationmembership__level=1)


def user_get_foreign_organizations(self):
    """returns a query set of organizations to which user does not belong"""
    #todo: maybe cache this query
    user_organization_ids = self.get_organizations().values_list('id', flat=True)
    return get_organizations().exclude(id__in=user_organization_ids)


def user_get_organization_membership(self, organization):
    """returns a organization membership object or None
    if it is not there
    """
    try:
        return OrganizationMembership.objects.get(user=self, organization=organization)
    except OrganizationMembership.DoesNotExist:
        return None


def user_get_organizations_membership_info(self, organizations):
    """returns a defaultdict with values that are
    dictionaries with the following keys and values:
    * key: acceptance_level, value: 'closed', 'moderated', 'open'
    * key: membership_level, value: 'none', 'pending', 'full'

    ``organizations`` is a organization tag query set
    """
    organization_ids = organizations.values_list('id', flat=True)
    memberships = OrganizationMembership.objects.filter(
                                user__id=self.id,
                                organization__id__in=organization_ids
                            )

    info = collections.defaultdict(
        lambda: {'acceptance_level': 'closed', 'membership_level': 'none'}
    )
    for membership in memberships:
        membership_level = membership.get_level_display()
        info[membership.organization_id]['membership_level'] = membership_level

    for organization in organizations:
        info[organization.id]['acceptance_level'] = organization.get_openness_level_for_user(self)

    return info


#series of methods for user vote-type commands
#same call signature func(self, post, timestamp=None, cancel=None)
#note that none of these have business logic checks internally
#these functions are used by the openode app and
#by the data importer jobs from say stackexchange, where internal rules
#may be different
#maybe if we do use business rule checks here - we should add
#some flag allowing to bypass them for things like the data importers
def toggle_followed_thread(
                        self, thread,
                        timestamp=None,
                        cancel=False,
                        force=False  # this parameter is not used yet
                    ):
    """cancel has no effect here, but is important for the SE loader
    it is hoped that toggle will work and data will be consistent
    but there is no guarantee, maybe it's better to be more strict
    about processing the "cancel" option
    another strange thing is that this function unlike others below
    returns a value
    """
    try:
        fave = FollowedThread.objects.get(thread=thread, user=self)
        fave.delete()
        result = False
        thread.update_followed_count()
    except FollowedThread.DoesNotExist:
        if timestamp is None:
            timestamp = datetime.datetime.now()
        fave = FollowedThread(
            thread=thread,
            user=self,
            added_at=timestamp,
        )
        fave.save()
        result = True
        thread.update_followed_count()

    if thread.thread_type == const.THREAD_TYPE_QUESTION:
        if result:
            self.log(thread, const.LOG_ACTION_FOLLOW_QUESTION)
        else:
            self.log(thread, const.LOG_ACTION_UNFOLLOW_QUESTION)
    elif thread.thread_type == const.THREAD_TYPE_DISCUSSION:
        if result:
            self.log(thread, const.LOG_ACTION_FOLLOW_DISCUSSION)
        else:
            self.log(thread, const.LOG_ACTION_UNFOLLOW_DISCUSSION)

    return result

VOTES_TO_EVENTS = {
    (Vote.VOTE_UP, 'answer'): 'upvote_answer',
    (Vote.VOTE_UP, 'question'): 'upvote_question',
    (Vote.VOTE_DOWN, 'question'): 'downvote',
    (Vote.VOTE_DOWN, 'answer'): 'downvote',
    (Vote.VOTE_UP, 'comment'): 'upvote_comment',
}


@auto_now_timestamp
def _process_vote(user, post, timestamp=None, cancel=False, vote_type=None):
    """"private" wrapper function that applies post upvotes/downvotes
    and cancelations
    """
    #get or create the vote object
    #return with noop in some situations
    try:
        vote = Vote.objects.get(user=user, voted_post=post)
    except Vote.DoesNotExist:
        vote = None
    if cancel:
        if vote == None:
            return
        elif vote.is_opposite(vote_type):
            return
        else:
            #we would call vote.delete() here
            #but for now all that is handled by the
            #legacy openode.auth functions
            #vote.delete()
            pass
    else:
        if vote == None:
            vote = Vote(
                    user=user,
                    voted_post=post,
                    vote=vote_type,
                    voted_at=timestamp,
                )
        elif vote.is_opposite(vote_type):
            vote.vote = vote_type
        else:
            return

    #do the actual work
    if vote_type == Vote.VOTE_UP:
        if cancel:
            auth.onUpVotedCanceled(vote, post, user, timestamp)
        else:
            auth.onUpVoted(vote, post, user, timestamp)
    elif vote_type == Vote.VOTE_DOWN:
        if cancel:
            auth.onDownVotedCanceled(vote, post, user, timestamp)
        else:
            auth.onDownVoted(vote, post, user, timestamp)

    post.thread.invalidate_cached_data()

    if post.is_question():
        #denormalize the question post score on the thread
        post.thread.points = post.points
        post.thread.save()
        post.thread.update_summary_html()

    if cancel:
        return None

    event = VOTES_TO_EVENTS.get((vote_type, post.post_type), None)
    return vote


def user_unfollow_thread(self, thread=None):
    self.followed_threads.remove(thread)


def user_follow_thread(self, thread=None):
    self.followed_threads.add(thread)


def user_is_following_thread(user, thread):
    """True if user is following a question"""
    return thread.followed_by.filter(id=user.id).exists()


def user_unsubscribe_thread(self, thread=None):
    SubscribedThread.objects.filter(user=self, thread=thread).delete()


def user_subscribe_thread(self, thread=None):
    st, created = SubscribedThread.objects.get_or_create(user=self, thread=thread)


def user_is_subscribing_thread(user, thread):
    """True if user is following a question"""
    return thread.subscribed_by.filter(id=user.id).exists()


def upvote(self, post, timestamp=None, cancel=False, force=False):
    #force parameter not used yet
    return _process_vote(
        self,
        post,
        timestamp=timestamp,
        cancel=cancel,
        vote_type=Vote.VOTE_UP
    )


def downvote(self, post, timestamp=None, cancel=False, force=False):
    #force not used yet
    return _process_vote(
        self,
        post,
        timestamp=timestamp,
        cancel=cancel,
        vote_type=Vote.VOTE_DOWN
    )


@auto_now_timestamp
def user_approve_post_revision(user, post_revision, timestamp=None):
    """approves the post revision and, if necessary,
    the parent post and threads"""
    user.assert_can_approve_post_revision()

    post_revision.approved = True
    post_revision.approved_by = user
    post_revision.approved_at = timestamp

    post_revision.save()

    post = post_revision.post
    post.approved = True
    post.save()

    if post_revision.post.is_question():
        thread = post.thread
        thread.approved = True
        thread.save()
    post.thread.invalidate_cached_data()

    #send the signal of published revision
    signals.post_revision_published.send(
        None, revision=post_revision, was_approved=True
    )


@auto_now_timestamp
def flag_post(
        user, post, timestamp=None, cancel=False, cancel_all=False, force=False
    ):
    if cancel_all:
        # remove all flags
        if force == False:
            user.assert_can_remove_all_flags_offensive(post=post)
        post_content_type = ContentType.objects.get_for_model(post)
        all_flags = Activity.objects.filter(
                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                        content_type=post_content_type,
                        object_id=post.id
                    )
        for flag in all_flags:
            auth.onUnFlaggedItem(post, flag.user, timestamp=timestamp)

    elif cancel:  # todo: can't unflag?
        if force == False:
            user.assert_can_remove_flag_offensive(post=post)
        auth.onUnFlaggedItem(post, user, timestamp=timestamp)

    else:
        if force == False:
            user.assert_can_flag_offensive(post=post)
        auth.onFlaggedItem(post, user, timestamp=timestamp)


def user_get_flags(self):
    """return flag Activity query set
    for all flags set by te user"""
    return Activity.objects.filter(
        user=self,
        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE
    )


def user_get_flag_count_posted_today(self):
    """return number of flags the user has posted
    within last 24 hours"""
    today = datetime.date.today()
    time_frame = (today, today + datetime.timedelta(1))
    flags = self.get_flags()
    return flags.filter(active_at__range=time_frame).count()


def user_get_flags_for_post(self, post):
    """return query set for flag Activity items
    posted by users for a given post obeject
    """
    post_content_type = ContentType.objects.get_for_model(post)
    flags = self.get_flags()
    return flags.filter(content_type=post_content_type, object_id=post.id)


def user_update_response_counts(user):
    """Recount number of responses to the user.
    """
    ACTIVITY_TYPES = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
    ACTIVITY_TYPES += (const.TYPE_ACTIVITY_MENTION,)

    user.new_response_count = ActivityAuditStatus.objects.filter(
                                    user=user,
                                    status=ActivityAuditStatus.STATUS_NEW,
                                    activity__activity_type__in=ACTIVITY_TYPES
                                ).count()
    user.seen_response_count = ActivityAuditStatus.objects.filter(
                                    user=user,
                                    status=ActivityAuditStatus.STATUS_SEEN,
                                    activity__activity_type__in=ACTIVITY_TYPES
                                ).count()
    user.save()


def user_update_wildcard_tag_selections(
                                    self,
                                    action=None,
                                    reason=None,
                                    wildcards=None,
                                ):
    """updates the user selection of wildcard tags
    and saves the user object to the database
    """
    if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
        assert reason in ('good', 'bad', 'subscribed')
    else:
        assert reason in ('good', 'bad')

    new_tags = set(wildcards)
    interesting = set(self.interesting_tags.split())
    ignored = set(self.ignored_tags.split())
    subscribed = set(self.subscribed_tags.split())

    if reason == 'good':
        target_set = interesting
        other_set = ignored
    elif reason == 'bad':
        target_set = ignored
        other_set = interesting
    elif reason == 'subscribed':
        target_set = subscribed
        other_set = None
    else:
        assert(action == 'remove')

    if action == 'add':
        target_set.update(new_tags)
        if reason in ('good', 'bad'):
            other_set.difference_update(new_tags)
    else:
        target_set.difference_update(new_tags)
        if reason in ('good', 'bad'):
            other_set.difference_update(new_tags)

    self.interesting_tags = ' '.join(interesting)
    self.ignored_tags = ' '.join(ignored)
    self.subscribed_tags = ' '.join(subscribed)
    self.save()
    return new_tags


def user_edit_organization_membership(self, user=None, organization=None, action=None):
    """allows one user to add another to a organization
    or remove user from organization.

    If when adding, the organization does not exist, it will be created
    the delete function is not symmetric, the organization will remain
    even if it becomes empty

    returns instance of OrganizationMembership (if action is "add") or None
    """
    if action == 'add':
        #calculate new level
        openness = organization.get_openness_level_for_user(user)

        if openness == 'open':
            level = OrganizationMembership.FULL
        elif openness == 'moderated':
            level = OrganizationMembership.PENDING
        elif openness == 'closed':
            raise django_exceptions.PermissionDenied()

        membership, created = OrganizationMembership.objects.get_or_create(
                        user=user, organization=organization, level=level
                    )
        return membership

    elif action == 'remove':
        OrganizationMembership.objects.get(user=user, organization=organization).delete()
        return None
    else:
        raise ValueError('invalid action')


def user_join_organization(self, organization):
    return self.edit_organization_membership(organization=organization, user=self, action='add')


def user_leave_organization(self, organization):
    self.edit_organization_membership(organization=organization, user=self, action='remove')


def user_is_organization_member(self, organization=None):
    """True if user is member of organization,
    where organization can be instance of organization
    or name of organization as string
    """
    if isinstance(organization, str):
        return OrganizationMembership.objects.filter(
                user=self, organization__name=organization
            ).count() == 1
    else:
        return OrganizationMembership.objects.filter(
                                user=self, organization=organization
                            ).count() == 1


def user_log(self, obj, action_type, message='', object_force_pk=None):
    Log.objects.log_action(
        self,
        obj,
        action_type,
        message=message,
        object_force_pk=object_force_pk
        )
User.add_to_class('log', user_log)


def user_has_openode_perm(self, perm, obj):
    '''
    resolve permission to object
    '''
    def eval_perm(perm_dict, perm, access):
        if perm not in perm_dict:
            return access
        access_override = perm_dict[perm]
        if access_override is None:
            return access
        else:
            return access_override

    def eval_perm_for_rule(rule, perm, access):
        return eval_perm(const.RULES[rule], perm, access)

    if isinstance(obj, Node):
        node = obj
        thread = None
    elif isinstance(obj, Thread):
        node = obj.node
        thread = obj
    else:
        return False

    #shortcut and check for perm
    if thread:
        if not perm.startswith('%s_' % thread.thread_type) and not perm.startswith('node_'):
            perm = '%s_%s' % (thread.thread_type, perm)
    elif node:
        for start in zip(('node',), *const.THREAD_TYPES)[0]:  # is this really necessary? same as: [tt[0] for tt in const.THREAD_TYPES] + ['node', ]
            if perm.startswith('%s_' % start):
                break
        else:
            perm = 'node_%s' % perm

    access = False

    if self.is_anonymous():
        node_user = None
    else:
        try:
            node_user = NodeUser.objects.get(user=self, node=node)
        except NodeUser.DoesNotExist:
            node_user = None

    if node.visibility == const.NODE_VISIBILITY_PUBLIC:
        access = eval_perm_for_rule('node_visibility_public', perm, access)

    if node.visibility == const.NODE_VISIBILITY_REGISTRED_USERS:
        access = eval_perm_for_rule('node_visibility_registered_users', perm, access)

    if self.is_authenticated():
        access = eval_perm_for_rule('user_loggedin', perm, access)

    if node.visibility == const.NODE_VISIBILITY_PRIVATE:
        access = eval_perm_for_rule('node_visibility_private', perm, access)

    if node.visibility == const.NODE_VISIBILITY_SEMIPRIVATE:
        access = eval_perm_for_rule('node_visibility_semiprivate', perm, access)

    if thread and thread.external_access:
        access = eval_perm_for_rule('thread_external_access', perm, access)

    #members role
    if node_user:
        access = eval_perm(const.MEMBERS_RULES[node_user.role], perm, access)
    #

    if thread and thread.closed:
        access = eval_perm_for_rule('thread_is_closed', perm, access)

    if node.module_qa_readonly:
        access = eval_perm_for_rule('node_qa_is_readonly', perm, access)
    if node.module_forum_readonly:
        access = eval_perm_for_rule('node_forum_is_readonly', perm, access)
    if node.module_library_readonly:
        access = eval_perm_for_rule('node_library_is_readonly', perm, access)

    if node.closed:
        access = eval_perm_for_rule('node_is_closed', perm, access)

    if node.deleted:
        access = eval_perm_for_rule('node_is_deleted', perm, access)

    return access

User.add_to_class('has_openode_perm', user_has_openode_perm)
AnonymousUser.has_openode_perm = user_has_openode_perm


def user_is_admin(self, perm=''):

    if self.is_superuser:
        return True

    if self.is_authenticated() and self.is_staff:
        if perm:
            return self.has_perm(perm)
        else:
            return True
    else:
        return False

User.add_to_class('is_admin', user_is_admin)
AnonymousUser.is_admin = user_is_admin


def user_get_moderation_items(self):
    """returns a dictionary with
    counts of new and seen moderation items.
    if user doesnt have a permission, returns None
    """
    if self.is_anonymous():
        return None

    if not self.has_perm('openode.resolve_flag_offensive'):
        return None

    content_types = (
        const.TYPE_ACTIVITY_MARK_OFFENSIVE,
    )

    messages = ActivityAuditStatus.objects.filter(
        activity__activity_type__in=content_types,
        user=self
    )

    seen_count = messages.filter(
                    status=ActivityAuditStatus.STATUS_SEEN
                ).count()
    new_count = messages.filter(
                    status=ActivityAuditStatus.STATUS_NEW
                ).count()
    return {
        'seen_count': seen_count,
        'new_count': new_count
    }

################################################################################


def user_get_managed_nodes_count(self):
    return self.nodes.filter(node_users__role=const.NODE_USER_ROLE_MANAGER).count
User.add_to_class('get_managed_nodes_count', user_get_managed_nodes_count)


def user_get_unread_followed_thread_count(self, thread_type):
    qs = self.user_followed_threads.filter(
        thread__thread_type=thread_type
    ).only(
        "thread"
    )

    return len([
        True
        for followed_thread in qs.iterator()
        if followed_thread.thread.has_unread_posts_for_user(self)
    ])
User.add_to_class('_get_unread_followed_thread_count', user_get_unread_followed_thread_count)


def user_get_unread_followed_questions_count(self):
    return self._get_unread_followed_thread_count(const.THREAD_TYPE_QUESTION)
User.add_to_class('get_unread_followed_questions_count', user_get_unread_followed_questions_count)


def user_get_unread_followed_discussions_count(self):
    return self._get_unread_followed_thread_count(const.THREAD_TYPE_DISCUSSION)
User.add_to_class('get_unread_followed_discussions_count', user_get_unread_followed_discussions_count)


def user_get_unread_followed_nodes_count(self):
    return len([
        True
        for f_node in self.user_followed_nodes.all()
        if f_node.node.is_new_for_user(self)
    ])
User.add_to_class('get_unread_followed_nodes_count', user_get_unread_followed_nodes_count)

################################################################################


@property
def user_get_screen_name(self):
    return self.display_name or ('%s %s' % (self.first_name, self.last_name))
User.add_to_class('screen_name', user_get_screen_name)


def user_has_user_perm(self, perm, user):
    if perm == 'can_see_followed_nodes':
        return self.is_authenticated() \
            and (self == user or user.privacy_show_followed or self.has_perm('openode.change_followed_node'))

    if perm == 'can_see_managed_nodes':
        return self.is_authenticated() and (self == user)

    elif perm == 'can_see_followed_threads':
        return self.is_authenticated() \
            and (self == user or user.privacy_show_followed or self.has_perm('openode.change_followed_thread'))

    return False
User.add_to_class('has_user_perm', user_has_user_perm)
AnonymousUser.has_user_perm = user_has_user_perm


def user_log_repr(self):
    return self.screen_name
User.add_to_class('log_repr', user_log_repr)


User.add_to_class('get_moderation_items', user_get_moderation_items)
AnonymousUser.get_moderation_items = user_get_moderation_items

User.add_to_class('add_missing_openode_subscriptions', user_add_missing_openode_subscriptions)
User.add_to_class('is_username_taken', classmethod(user_is_username_taken))
User.add_to_class('get_followed_question_alert_frequency', user_get_followed_question_alert_frequency)
User.add_to_class('subscribe_for_followed_question_alerts', user_subscribe_for_followed_question_alerts)
User.add_to_class('get_default_avatar_url', user_get_default_avatar_url)
User.add_to_class('get_gravatar_url', user_get_gravatar_url)
User.add_to_class('get_marked_tags', user_get_marked_tags)
User.add_to_class('get_marked_tag_names', user_get_marked_tag_names)
User.add_to_class('get_organizations', user_get_organizations)
User.add_to_class('get_foreign_organizations', user_get_foreign_organizations)
User.add_to_class('get_organization_membership', user_get_organization_membership)
User.add_to_class('get_notifications', user_get_notifications)
User.add_to_class('strip_email_signature', user_strip_email_signature)
User.add_to_class('get_organizations_membership_info', user_get_organizations_membership_info)
User.add_to_class('get_anonymous_name', user_get_anonymous_name)
User.add_to_class('update_avatar_type', user_update_avatar_type)
User.add_to_class('post_thread', user_post_thread)
User.add_to_class('edit_thread', user_edit_thread)
User.add_to_class('retag_question', user_retag_question)
User.add_to_class('post_answer', user_post_answer)
User.add_to_class('edit_answer', user_edit_answer)
User.add_to_class('edit_post', user_edit_post)
User.add_to_class('post_anonymous_openode_content', user_post_anonymous_openode_content)
User.add_to_class('post_comment', user_post_comment)
User.add_to_class('edit_comment', user_edit_comment)
User.add_to_class('create_post_reject_reason', user_create_post_reject_reason)
User.add_to_class('edit_post_reject_reason', user_edit_post_reject_reason)
User.add_to_class('delete_post', user_delete_post)
User.add_to_class('post_object_description', user_post_object_description)
User.add_to_class('visit_thread', user_visit_thread)
User.add_to_class('upvote', upvote)
User.add_to_class('downvote', downvote)
User.add_to_class('flag_post', flag_post)
User.add_to_class('get_flags', user_get_flags)
User.add_to_class('get_flag_count_posted_today', user_get_flag_count_posted_today)
User.add_to_class('get_flags_for_post', user_get_flags_for_post)
User.add_to_class('get_profile_url', get_profile_url)
User.add_to_class('get_tag_filtered_questions', user_get_tag_filtered_questions)
User.add_to_class('get_messages', get_messages)
User.add_to_class('delete_messages', delete_messages)
User.add_to_class('toggle_followed_thread', toggle_followed_thread)
User.add_to_class('follow_thread', user_follow_thread)
User.add_to_class('unfollow_thread', user_unfollow_thread)
User.add_to_class('is_following_thread', user_is_following_thread)
User.add_to_class('subscribe_thread', user_subscribe_thread)
User.add_to_class('unsubscribe_thread', user_unsubscribe_thread)
User.add_to_class('is_subscribing_thread', user_is_subscribing_thread)
User.add_to_class('mark_tags', user_mark_tags)
User.add_to_class('update_response_counts', user_update_response_counts)
User.add_to_class('can_create_tags', user_can_create_tags)
User.add_to_class('can_have_strong_url', user_can_have_strong_url)
User.add_to_class('can_post_by_email', user_can_post_by_email)
User.add_to_class('can_post_comment', user_can_post_comment)
User.add_to_class('is_administrator', user_is_administrator)
User.add_to_class('is_administrator_or_moderator', user_is_administrator_or_moderator)
User.add_to_class('set_admin_status', user_set_admin_status)
User.add_to_class('edit_organization_membership', user_edit_organization_membership)
User.add_to_class('join_organization', user_join_organization)
User.add_to_class('leave_organization', user_leave_organization)
User.add_to_class('is_organization_member', user_is_organization_member)
User.add_to_class('remove_admin_status', user_remove_admin_status)
User.add_to_class('is_moderator', user_is_moderator)
User.add_to_class('is_approved', user_is_approved)
User.add_to_class('is_watched', user_is_watched)
User.add_to_class('is_suspended', user_is_suspended)
User.add_to_class('is_blocked', user_is_blocked)
User.add_to_class('is_owner_of', user_is_owner_of)
User.add_to_class('has_interesting_wildcard_tags', user_has_interesting_wildcard_tags)
User.add_to_class('has_ignored_wildcard_tags', user_has_ignored_wildcard_tags)
User.add_to_class('can_moderate_user', user_can_moderate_user)
User.add_to_class('has_affinity_to_question', user_has_affinity_to_question)
User.add_to_class('set_status', user_set_status)
User.add_to_class('get_status_display', user_get_status_display)
User.add_to_class('get_old_vote_for_post', user_get_old_vote_for_post)
User.add_to_class('get_unused_votes_today', user_get_unused_votes_today)
User.add_to_class('delete_comment', user_delete_comment)
User.add_to_class('delete_question', user_delete_question)
User.add_to_class('delete_answer', user_delete_answer)
User.add_to_class('restore_post', user_restore_post)
User.add_to_class('close_thread', user_close_thread)
User.add_to_class('reopen_thread', user_reopen_thread)
User.add_to_class('accept_best_answer', user_accept_best_answer)
User.add_to_class('unaccept_best_answer', user_unaccept_best_answer)
User.add_to_class('update_wildcard_tag_selections', user_update_wildcard_tag_selections)
User.add_to_class('approve_post_revision', user_approve_post_revision)
User.add_to_class('notify_users', user_notify_users)
User.add_to_class('has_perm', user_has_perm)

#assertions
User.add_to_class('assert_can_vote_for_post', user_assert_can_vote_for_post)
User.add_to_class('assert_can_revoke_old_vote', user_assert_can_revoke_old_vote)
User.add_to_class('assert_can_upload_file', user_assert_can_upload_file)
User.add_to_class('assert_can_post_question', user_assert_can_post_question)
User.add_to_class('assert_can_post_answer', user_assert_can_post_answer)
User.add_to_class('assert_can_post_comment', user_assert_can_post_comment)
User.add_to_class('assert_can_edit_post', user_assert_can_edit_post)
User.add_to_class('assert_can_edit_deleted_post', user_assert_can_edit_deleted_post)
User.add_to_class('assert_can_see_deleted_post', user_assert_can_see_deleted_post)
User.add_to_class('assert_can_edit_thread', user_assert_can_edit_thread)
User.add_to_class('assert_can_edit_answer', user_assert_can_edit_answer)
User.add_to_class('assert_can_close_thread', user_assert_can_close_thread)
User.add_to_class('assert_can_reopen_thread', user_assert_can_reopen_thread)
User.add_to_class('assert_can_flag_offensive', user_assert_can_flag_offensive)
User.add_to_class('assert_can_remove_flag_offensive', user_assert_can_remove_flag_offensive)
User.add_to_class('assert_can_remove_all_flags_offensive', user_assert_can_remove_all_flags_offensive)
User.add_to_class('assert_can_retag_question', user_assert_can_retag_question)
#todo: do we need assert_can_delete_post
User.add_to_class('assert_can_delete_post', user_assert_can_delete_post)
User.add_to_class('assert_can_restore_post', user_assert_can_restore_post)
User.add_to_class('assert_can_delete_comment', user_assert_can_delete_comment)
User.add_to_class('assert_can_edit_comment', user_assert_can_edit_comment)
User.add_to_class('assert_can_delete_answer', user_assert_can_delete_answer)
User.add_to_class('assert_can_delete_question', user_assert_can_delete_question)
User.add_to_class('assert_can_accept_best_answer', user_assert_can_accept_best_answer)
User.add_to_class('assert_can_unaccept_best_answer', user_assert_can_unaccept_best_answer)
User.add_to_class('assert_can_approve_post_revision', user_assert_can_approve_post_revision)


#todo: move this to openode/mail ?
def format_instant_notification_email(
                                        to_user=None,
                                        from_user=None,
                                        post=None,
                                        reply_address=None,
                                        alt_reply_address=None,
                                        update_type=None,
                                        template=None,
                                    ):
    """
    returns text of the instant notification body
    and subject line

    that is built when post is updated
    only update_types in const.RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES
    are supported
    """
    site_url = openode_settings.APP_URL
    origin_post = post.get_origin_post()
    #todo: create a better method to access "sub-urls" in user views
    user_subscriptions_url = site_url + \
                                reverse(
                                    'user_subscriptions',
                                    kwargs={
                                        'id': to_user.id,
                                        'slug': slugify(to_user.username)
                                    }
                                )

    if update_type == 'question_comment':
        assert(isinstance(post, Post) and post.is_comment())
        assert(post.parent and post.parent.is_question())
    elif update_type == 'answer_comment':
        assert(isinstance(post, Post) and post.is_comment())
        assert(post.parent and post.parent.is_answer())
    elif update_type == 'answer_update':
        assert(isinstance(post, Post) and post.is_answer())
    elif update_type == 'new_answer':
        assert(isinstance(post, Post) and post.is_answer())
    elif update_type == 'question_update':
        assert(isinstance(post, Post) and post.is_question())
    elif update_type == 'new_question':
        assert(isinstance(post, Post) and post.is_question())
    elif update_type == 'post_shared':
        pass
    else:
        raise ValueError('unexpected update_type %s' % update_type)

    if update_type.endswith('update'):
        assert('comment' not in update_type)
        revisions = post.revisions.all()[:2]
        assert(len(revisions) == 2)
        content_preview = htmldiff(
                bleach_html(revisions[1].html),
                bleach_html(revisions[0].html),
                ins_start='<b><u style="background-color:#cfc">',
                ins_end='</u></b>',
                del_start='<del style="color:#600;background-color:#fcc">',
                del_end='</del>'
            )
        #todo: remove hardcoded style
    else:
        content_preview = post.format_for_email(is_leaf_post=True)

    #add indented summaries for the parent posts
    content_preview += post.format_for_email_as_parent_thread_summary()

    content_preview += '<p>======= Full thread summary =======</p>'

    content_preview += post.thread.format_for_email(user=to_user)

    if update_type == 'post_shared':
        user_action = _('%(user)s shared a %(post_link)s.')
    elif post.is_comment():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited a %(post_link)s.')
        else:
            user_action = _('%(user)s posted a %(post_link)s')
    elif post.is_answer():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited an %(post_link)s.')
        else:
            user_action = _('%(user)s posted an %(post_link)s.')
    elif post.is_question():
        if update_type.endswith('update'):
            user_action = _('%(user)s edited a %(post_link)s.')
        else:
            user_action = _('%(user)s posted a %(post_link)s.')
    else:
        raise ValueError('unrecognized post type')

    post_url = strip_path(site_url) + post.get_absolute_url()
    user_url = strip_path(site_url) + from_user.get_absolute_url()
    user_action = user_action % {
        'user': '<a href="%s">%s</a>' % (user_url, from_user.username),
        'post_link': '<a href="%s">%s</a>' % (post_url, _(post.post_type))
        #'post_link': '%s <a href="%s">>>></a>' % (_(post.post_type), post_url)
    }

    can_reply = to_user.can_post_by_email()

    if can_reply:
        reply_separator = const.SIMPLE_REPLY_SEPARATOR_TEMPLATE % \
                    _('To reply, PLEASE WRITE ABOVE THIS LINE.')
        if post.is_question() and alt_reply_address:
            data = {
                'addr': alt_reply_address,
                'subject': urllib.quote(
                        ('Re: ' + post.thread.title).encode('utf-8')
                    )
            }
            reply_separator += '<p>' + \
                const.REPLY_WITH_COMMENT_TEMPLATE % data
            reply_separator += '</p>'
        else:
            reply_separator = '<p>%s</p>' % reply_separator

        reply_separator += user_action
    else:
        reply_separator = user_action

    update_data = {
        'update_author_name': from_user.username,
        'receiving_user_name': to_user.username,
        'can_reply': can_reply,
        'content_preview': content_preview, # post.get_snippet()
        'update_type': update_type,
        'post_url': post_url,
        'origin_post_title': origin_post.thread.title,
        'user_subscriptions_url': user_subscriptions_url,
        'reply_separator': reply_separator,
        'reply_address': reply_address
    }
    subject_line = _('"%(title)s"') % {'title': origin_post.thread.title}

    content = template.render(Context(update_data))

    return subject_line, content


def get_reply_to_addresses(user, post):
    """Returns one or two email addresses that can be
    used by a given `user` to reply to the `post`
    the first address - always a real email address,
    the second address is not ``None`` only for "question" posts.

    When the user is notified of a new question -
    i.e. `post` is a "quesiton", he/she
    will need to choose - whether to give a question or a comment,
    thus we return the second address - for the comment reply.

    When the post is a "question", the first email address
    is for posting an "answer", and when post is either
    "comment" or "answer", the address will be for posting
    a "comment".
    """
    #these variables will contain return values
    primary_addr = django_settings.DEFAULT_FROM_EMAIL
    secondary_addr = None
    if user.can_post_by_email():

        reply_args = {
            'post': post,
            'user': user,
            'reply_action': 'post_comment'
        }
        if post.post_type in ('answer', 'comment'):
            reply_args['reply_action'] = 'post_comment'
        elif post.is_question():
            reply_args['reply_action'] = 'post_answer'

        primary_addr = ReplyAddress.objects.create_new(
                                                **reply_args
                                            ).as_email_address()

        if post.is_question():
            reply_args['reply_action'] = 'post_comment'
            secondary_addr = ReplyAddress.objects.create_new(
                                                **reply_args
                                            ).as_email_address()
    return primary_addr, secondary_addr


# DEPRECATED
#todo: action
# @task()
# def send_instant_notifications_about_activity_in_post(
#                                                 update_activity=None,
#                                                 post=None,
#                                                 recipients=None,
#                                             ):
#     #reload object from the database
#     post = Post.objects.get(id=post.id)

#     if recipients is None:
#         return

#     acceptable_types = const.RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS

#     if update_activity.activity_type not in acceptable_types:
#         return

#     #calculate some variables used in the loop below
#     from openode.skins.loaders import get_template
#     update_type_map = const.RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES
#     update_type = update_type_map[update_activity.activity_type]
#     origin_post = post.get_origin_post()
#     headers = mail.thread_headers(
#                             post,
#                             origin_post,
#                             update_activity.activity_type
#                         )

#     logger = logging.getLogger()
#     if logger.getEffectiveLevel() <= logging.DEBUG:
#         log_id = uuid.uuid1()
#         message = 'email-alert %s, logId=%s' % (post.get_absolute_url(), log_id)
#         logger.debug(message)
#     else:
#         log_id = None

#     for user in recipients:
#         if user.is_blocked():
#             continue

#         reply_address, alt_reply_address = get_reply_to_addresses(user, post)

#         subject_line, body_text = format_instant_notification_email(
#                             to_user=user,
#                             from_user=update_activity.user,
#                             post=post,
#                             reply_address=reply_address,
#                             alt_reply_address=alt_reply_address,
#                             update_type=update_type,
#                             template=get_template('email/instant_notification.html')
#                         )

#         headers['Reply-To'] = reply_address
#         try:
#             mail.send_mail(
#                 subject_line=subject_line,
#                 body_text=body_text,
#                 recipient_list=[user.email],
#                 related_object=origin_post,
#                 activity_type=const.TYPE_ACTIVITY_EMAIL_UPDATE_SENT,
#                 headers=headers,
#                 raise_on_failure=True
#             )
#         except openode_exceptions.EmailNotSent, error:
#             logger.debug(
#                 '%s, error=%s, logId=%s' % (user.email, error, log_id)
#             )
#         else:
#             logger.debug('success %s, logId=%s' % (user.email, log_id))


#todo: move to utils
def calculate_gravatar_hash(instance, **kwargs):
    """Calculates a User's gravatar hash from their email address."""
    if kwargs.get('raw', False):
        return
    clean_email = instance.email.strip().lower()
    instance.gravatar = hashlib.md5(clean_email).hexdigest()


# DEPRECATED
# def record_post_update_activity(
#         post,
#         newly_mentioned_users=None,
#         updated_by=None,
#         timestamp=None,
#         created=False,
#         diff=None,
#         **kwargs
#     ):
#     """called upon signal openode.models.signals.post_updated
#     which is sent at the end of save() method in posts

#     this handler will set notifications about the post
#     """

#     assert(timestamp != None)
#     assert(updated_by != None)
#     if newly_mentioned_users is None:
#         newly_mentioned_users = list()

#     from openode import tasks

#     tasks.record_post_update_celery_task.delay(
#         post_id=post.id,
#         post_content_type_id=ContentType.objects.get_for_model(post).id,
#         newly_mentioned_user_id_list=[u.id for u in newly_mentioned_users],
#         updated_by_id=updated_by.id,
#         timestamp=timestamp,
#         created=created,
#         diff=diff,
#     )


def record_answer_accepted(instance, created, **kwargs):
    """
    when answer is accepted, we record this for question author
    - who accepted it.
    """
    if instance.post_type != 'answer':
        return

    question = instance.thread._main_post()

    if not created and instance.accepted():
        activity = Activity(
                        user=question.author,
                        active_at=datetime.datetime.now(),
                        content_object=question,
                        activity_type=const.TYPE_ACTIVITY_MARK_ANSWER,
                        question=question
                    )
        activity.save()
        recipients = instance.get_author_list(
                                    exclude_list=[question.author]
                                )
        activity.add_recipients(recipients)


def record_user_visit(user, timestamp, **kwargs):
    """
    when user visits any pages, we update the last_seen and
    consecutive_days_visit_count
    """
    prev_last_seen = user.last_seen or datetime.datetime.now()
    user.last_seen = timestamp
    if (user.last_seen - prev_last_seen).days == 1:
        user.consecutive_days_visit_count += 1

    #somehow it saves on the query as compared to user.save()
    User.objects.filter(id=user.id).update(last_seen=timestamp)


def record_vote(instance, created, **kwargs):
    """
    when user have voted
    """
    if created:
        if instance.vote == 1:
            vote_type = const.TYPE_ACTIVITY_VOTE_UP
        else:
            vote_type = const.TYPE_ACTIVITY_VOTE_DOWN

        activity = Activity(
                        user=instance.user,
                        active_at=instance.voted_at,
                        content_object=instance,
                        activity_type=vote_type
                    )
        #todo: problem cannot access receiving user here
        activity.save()


def record_cancel_vote(instance, **kwargs):
    """
    when user canceled vote, the vote will be deleted.
    """
    activity = Activity(
                    user=instance.user,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_CANCEL_VOTE
                )
    #todo: same problem - cannot access receiving user here
    activity.save()


#todo: weird that there is no record delete answer or comment
#is this even necessary to keep track of?
def record_delete_question(instance, delete_by, **kwargs):
    """
    when user deleted the question
    """
    if instance.is_question():
        activity_type = const.TYPE_ACTIVITY_DELETE_QUESTION
    elif instance.is_answer():
        activity_type = const.TYPE_ACTIVITY_DELETE_ANSWER
    else:
        return

    activity = Activity(
                    user=delete_by,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=activity_type,
                    question=instance.get_origin_post()
                )
    #no need to set receiving user here
    activity.save()


def record_flag_offensive(instance, mark_by, **kwargs):
    activity = Activity(
                    user=mark_by,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                    question=instance.get_origin_post()
                )
    activity.save()
    activity.add_recipients(get_users_with_perm('resolve_flag_offensive'))


def remove_flag_offensive(instance, mark_by, **kwargs):
    "Remove flagging activity"
    content_type = ContentType.objects.get_for_model(instance)

    activity = Activity.objects.filter(
                    user=mark_by,
                    content_type=content_type,
                    object_id=instance.id,
                    activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                    question=instance.get_origin_post()
                )
    activity.delete()


def record_update_tags(thread, tags, user, timestamp, **kwargs):
    """
    This function sends a signal on each updated tag
    that respond to the 'ta
    """
    question = thread._main_post()

    activity = Activity(
                    user=user,
                    active_at=datetime.datetime.now(),
                    content_object=question,
                    activity_type=const.TYPE_ACTIVITY_UPDATE_TAGS,
                    question=question
                )
    activity.save()


def record_followed_thread(instance, created, **kwargs):
    """
    when user add the question in him followed questions list.
    """
    if created:
        activity = Activity(
                        user=instance.user,
                        active_at=datetime.datetime.now(),
                        content_object=instance,
                        activity_type=const.TYPE_ACTIVITY_FOLLOWED,
                        question=instance.thread._main_post()
                    )
        activity.save()
        recipients = instance.thread._main_post().get_author_list(
                                            exclude_list=[instance.user]
                                        )
        activity.add_recipients(recipients)


def record_user_full_updated(instance, **kwargs):
    activity = Activity(
                    user=instance,
                    active_at=datetime.datetime.now(),
                    content_object=instance,
                    activity_type=const.TYPE_ACTIVITY_USER_FULL_UPDATED
                )
    activity.save()


# def send_respondable_email_validation_message(
#     user=None, subject_line=None, data=None, template_name=None
# ):
#     """sends email validation message to the user

#     We validate email by getting user's reply
#     to the validation message by email, which also gives
#     an opportunity to extract user's email signature.
#     """
#     reply_address = ReplyAddress.objects.create_new(
#                                     user=user,
#                                     reply_action='validate_email'
#                                 )
#     data['email_code'] = reply_address.address

#     from openode.skins.loaders import get_template
#     template = get_template(template_name)
#     body_text = template.render(Context(data))

#     reply_to_address = 'welcome-%s@%s' % (
#                             reply_address.address,
#                             openode_settings.REPLY_BY_EMAIL_HOSTNAME
#                         )

#     mail.send_mail(
#         subject_line=subject_line,
#         body_text=body_text,
#         recipient_list=[user.email, ],
#         activity_type=const.TYPE_ACTIVITY_VALIDATION_EMAIL_SENT,
#         headers={'Reply-To': reply_to_address}
#     )


def greet_new_user(user, **kwargs):
    """sends welcome email to the newly created user

    todo: second branch should send email with a simple
    clickable link.
    """
    # if openode_settings.NEW_USER_GREETING:
    #     user.message_set.create(message=openode_settings.NEW_USER_GREETING)
    user.message_set.create(message=_('Your registration is complete! To get desired content use our smart search field or simply browse around.'))

    # if openode_settings.REPLY_BY_EMAIL:  # with this on we also collect signature
    #     template_name = 'email/welcome_lamson_on.html'
    # else:
    #     template_name = 'email/welcome_lamson_off.html'

    # data = {
    #     'site_name': openode_settings.APP_SHORT_NAME
    # }
    # send_respondable_email_validation_message(
    #     user=user,
    #     subject_line=_('Welcome to %(site_name)s') % data,
    #     data=data,
    #     template_name=template_name
    # )

    subject = _("Your registration is complete")
    data = {
        'site_name': openode_settings.APP_SHORT_NAME,
        'site_url': openode_settings.APP_URL
    }
    from openode.skins.loaders import get_template
    template = get_template('email/welcome.html')
    message = template.render(data)
    mail.send_mail(subject, message, django_settings.DEFAULT_FROM_EMAIL, [user.email], raise_on_failure=True)


def complete_pending_tag_subscriptions(sender, request, *args, **kwargs):
    """save pending tag subscriptions saved in the session"""
    if 'subscribe_for_tags' in request.session:
        (pure_tag_names, wildcards) = request.session.pop('subscribe_for_tags')
        if openode_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            reason = 'subscribed'
        else:
            reason = 'good'
        request.user.mark_tags(
                    pure_tag_names,
                    wildcards,
                    reason=reason,
                    action='add'
                )
        request.user.message_set.create(
            message=_('Your tag subscription was saved, thanks!')
        )


def add_missing_subscriptions(sender, instance, created, **kwargs):
    """``sender`` is instance of ``User``. When the ``User``
    is created, any required email subscription settings will be
    added by this handler"""
    if created:
        instance.add_missing_openode_subscriptions()


def post_anonymous_openode_content(
                                sender,
                                request,
                                user,
                                session_key,
                                signal,
                                *args,
                                **kwargs):
    """signal handler, unfortunately extra parameters
    are necessary for the signal machinery, even though
    they are not used in this function"""
    user.post_anonymous_openode_content(session_key)


def set_user_avatar_type_flag(instance, created, **kwargs):
    instance.user.update_avatar_type()


def update_user_avatar_type_flag(instance, **kwargs):
    instance.user.update_avatar_type()


def make_admin_if_first_user(instance, **kwargs):
    """first user automatically becomes an administrator
    the function is run only once in the interpreter session
    """
    import sys
    #have to check sys.argv to satisfy the test runner
    #which fails with the cache-based skipping
    #for real the setUp() code in the base test case must
    #clear the cache!!!
    if 'test' not in sys.argv and cache.cache.get('admin-created'):
        #no need to hit the database every time!
        return
    user_count = User.objects.all().count()
    if user_count == 0:
        instance.set_admin_status()
    cache.cache.set('admin-created', True)


def moderate_organization_joining(sender, instance=None, created=False, **kwargs):
    if created and instance.level == OrganizationMembership.PENDING:
        user = instance.user
        organization = instance.organization
        user.notify_users(
                notification_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_ORGANIZATION,
                recipients=get_users_with_perm('resolve_organization_joining'),
                content_object=organization
            )

#signal for User model save changes
django_signals.pre_save.connect(make_admin_if_first_user, sender=User)
django_signals.pre_save.connect(calculate_gravatar_hash, sender=User)
django_signals.post_save.connect(add_missing_subscriptions, sender=User)
django_signals.post_save.connect(set_membership, sender=User)

django_signals.post_save.connect(record_answer_accepted, sender=Post)
django_signals.post_save.connect(record_vote, sender=Vote)
django_signals.post_save.connect(record_followed_thread, sender=FollowedThread)
django_signals.post_save.connect(moderate_organization_joining, sender=OrganizationMembership)

if 'avatar' in django_settings.INSTALLED_APPS:
    from avatar.models import Avatar
    django_signals.post_save.connect(set_user_avatar_type_flag, sender=Avatar)
    django_signals.post_delete.connect(update_user_avatar_type_flag, sender=Avatar)

django_signals.post_delete.connect(record_cancel_vote, sender=Vote)

#change this to real m2m_changed with Django1.2
signals.delete_question_or_answer.connect(record_delete_question, sender=Post)
signals.flag_offensive.connect(record_flag_offensive, sender=Post)
signals.remove_flag_offensive.connect(remove_flag_offensive, sender=Post)
signals.tags_updated.connect(record_update_tags)
signals.user_registered.connect(greet_new_user)
signals.user_updated.connect(record_user_full_updated, sender=User)
signals.user_logged_in.connect(complete_pending_tag_subscriptions)  # todo: add this to fake onlogin middleware
signals.user_logged_in.connect(post_anonymous_openode_content)

# inbox and activity is replaced by follow
# signals.post_updated.connect(record_post_update_activity)

#probably we cannot use post-save here the point of this is
#to tell when the revision becomes publicly visible, not when it is saved
signals.site_visited.connect(record_user_visit)

################################################################################

# This is ugly hack, sorry.
User._meta.get_field("username").max_length = 255
User._meta.get_field("email").max_length = 255

################################################################################

from rosetta.signals import post_save as rosetta_post_save
from openode.models.slots import restart_server

rosetta_post_save.connect(restart_server, sender=None)


################################################################################

class ProxyUser(User):
    class Meta:
        proxy = True
        #if app_label is "openode", the permissions are not functional in admin.
        app_label = 'auth'

__all__ = [
        'signals',

        'Thread',

        "Actuality",
        "StaticPage",
        "MenuItem",

        'ThreadView',
        'AnonymousQuestion',
        'DraftQuestion',

        'AnonymousAnswer',
        'DraftAnswer',

        'Post',
        'PostRevision',

        'Node',
        'NodeUser',
        'Tag',
        'Vote',
        'PostFlagReason',
        'MarkedTag',

        'FollowedThread',
        'FollowedNode',
        'SubscribedNode',

        'Activity',
        'ActivityAuditStatus',
        'EmailFeedSetting',
        'OrganizationMembership',
        "Organization",
        'Log',

        'User',

        'ReplyAddress',

        'get_model',
        'get_organization_names',
        'get_organizations'
]


class ProxyUserManagerStatusManager(models.Manager):
    def get_query_set(self):
        return super(ProxyUserManagerStatusManager, self).get_query_set().filter(nodeuser__role='manager').distinct()


class ProxyUserManagerStatus(ProxyUser):
    objects = ProxyUserManagerStatusManager()

    class Meta:
        proxy = True
        app_label = 'auth'
        verbose_name = "Proxy users - managers only"
        verbose_name_plural = "Proxy users - managers only"
