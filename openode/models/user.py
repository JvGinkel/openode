# -*- coding: utf-8 -*-

import datetime
import logging
import os
import simplejson

from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse
from django.core import exceptions
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.db import models
from django.db.backends.dummy.base import IntegrityError
from django.forms import EmailField
from django.utils.encoding import smart_unicode
from django.utils.translation import ugettext as _

from sorl.thumbnail.helpers import ThumbnailError
from sorl.thumbnail.shortcuts import get_thumbnail

from openode import const
from openode.forms import DomainNameField
from openode.utils import functions
from openode.utils.forms import email_is_allowed
from openode.utils.path import sanitize_file_name
from openode.utils.slug import slugify

from django.conf import settings

################################################################################


class ResponseAndMentionActivityManager(models.Manager):
    def get_query_set(self):
        response_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
        response_types += (const.TYPE_ACTIVITY_MENTION, )
        return super(
                    ResponseAndMentionActivityManager,
                    self
                ).get_query_set().filter(
                    activity_type__in=response_types
                )


class ActivityManager(models.Manager):
    def get_all_origin_posts(self):
        #todo: redo this with query sets
        origin_posts = set()
        for m in self.all():
            post = m.content_object
            if post and hasattr(post, 'get_origin_post'):
                origin_posts.add(post.get_origin_post())
            else:
                logging.debug(
                            'method get_origin_post() not implemented for %s' \
                            % unicode(post)
                        )
        return list(origin_posts)

    def create_new_mention(
                self,
                mentioned_by=None,
                mentioned_whom=None,
                mentioned_at=None,
                mentioned_in=None,
                reported=None
            ):

        #todo: automate this using python inspect module
        kwargs = dict()

        kwargs['activity_type'] = const.TYPE_ACTIVITY_MENTION

        if mentioned_at:
            #todo: handle cases with rich lookups here like __lt
            kwargs['active_at'] = mentioned_at

        if mentioned_by:
            kwargs['user'] = mentioned_by

        if mentioned_in:
            if functions.is_iterable(mentioned_in):
                raise NotImplementedError('mentioned_in only works for single items')
            else:
                post_content_type = ContentType.objects.get_for_model(mentioned_in)
                kwargs['content_type'] = post_content_type
                kwargs['object_id'] = mentioned_in.id

        if reported == True:
            kwargs['is_auditted'] = True
        else:
            kwargs['is_auditted'] = False

        mention_activity = Activity(**kwargs)
        mention_activity.question = mentioned_in.get_origin_post()
        mention_activity.save()

        if mentioned_whom:
            assert(isinstance(mentioned_whom, User))
            mention_activity.add_recipients([mentioned_whom])
            mentioned_whom.update_response_counts()

        return mention_activity

    def get_mentions(
                self,
                mentioned_by=None,
                mentioned_whom=None,
                mentioned_at=None,
                mentioned_in=None,
                reported=None,
                mentioned_at__lt=None,
            ):
        """extract mention-type activity objects
        todo: implement better rich field lookups
        """

        kwargs = dict()

        kwargs['activity_type'] = const.TYPE_ACTIVITY_MENTION

        if mentioned_at:
            #todo: handle cases with rich lookups here like __lt, __gt and others
            kwargs['active_at'] = mentioned_at
        elif mentioned_at__lt:
            kwargs['active_at__lt'] = mentioned_at__lt

        if mentioned_by:
            kwargs['user'] = mentioned_by

        if mentioned_whom:
            if functions.is_iterable(mentioned_whom):
                kwargs['recipients__in'] = mentioned_whom
            else:
                kwargs['recipients__in'] = (mentioned_whom,)

        if mentioned_in:
            if functions.is_iterable(mentioned_in):
                it = iter(mentioned_in)
                raise NotImplementedError('mentioned_in only works for single items')
            else:
                post_content_type = ContentType.objects.get_for_model(mentioned_in)
                kwargs['content_type'] = post_content_type
                kwargs['object_id'] = mentioned_in.id

        if reported == True:
            kwargs['is_auditted'] = True
        else:
            kwargs['is_auditted'] = False

        return self.filter(**kwargs)


class ActivityAuditStatus(models.Model):
    """bridge "through" relation between activity and users"""
    STATUS_NEW = 0
    STATUS_SEEN = 1
    STATUS_CHOICES = (
        (STATUS_NEW, 'new'),
        (STATUS_SEEN, 'seen')
    )
    user = models.ForeignKey(User)
    activity = models.ForeignKey('Activity')
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_NEW)

    class Meta:
        unique_together = ('user', 'activity')
        app_label = 'openode'
        db_table = 'openode_activityauditstatus'

    def is_new(self):
        return (self.status == self.STATUS_NEW)


class Activity(models.Model):
    """
    We keep some history data for user activities
    """
    user = models.ForeignKey(User)
    recipients = models.ManyToManyField(User, through=ActivityAuditStatus, related_name='incoming_activity')
    activity_type = models.SmallIntegerField(choices=const.TYPE_ACTIVITY)
    active_at = models.DateTimeField(default=datetime.datetime.now)
    content_type = models.ForeignKey(ContentType, blank=True)
    object_id = models.PositiveIntegerField(blank=True)
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    data = models.TextField(null=True, blank=True)

    #todo: remove this denorm question field when Post model is set up
    question = models.ForeignKey('Post', null=True)

    is_auditted = models.BooleanField(default=False)
    #add summary field.
    summary = models.TextField(default='')

    objects = ActivityManager()
    responses_and_mentions = ResponseAndMentionActivityManager()

    def __unicode__(self):
        return u'[%s] was active at %s' % (self.user.username, self.active_at)

    class Meta:
        app_label = 'openode'
        db_table = u'activity'

        permissions = (("resolve_flag_offensive", "Can resolve flag offensive"),
                    ("resolve_organization_joining", "Can resolve organization joining"),
                    ("resolve_node_joining", "Can resolve node joining"),
                )

    def render_data(self, template_string):
        try:
            data = simplejson.loads(self.data)
            print data
        except Exception:
            return ""
        else:
            return template_string % data

    def add_recipients(self, recipients):
        """have to use a special method, because django does not allow
        auto-adding to M2M with "through" model
        """
        for recipient in recipients:
            #todo: may optimize for bulk addition
            aas = ActivityAuditStatus(user=recipient, activity=self)
            aas.save()

    def get_mentioned_user(self):
        assert(self.activity_type == const.TYPE_ACTIVITY_MENTION)
        user_qs = self.recipients.all()
        user_count = len(user_qs)
        if user_count == 0:
            return None
        assert(user_count == 1)
        return user_qs[0]

    def get_snippet(self, max_length=120):
        return self.content_object.get_snippet(max_length)

    def get_absolute_url(self):
        return self.content_object.get_absolute_url()


class EmailFeedSettingManager(models.Manager):
    def filter_subscribers(
                        self,
                        potential_subscribers=None,
                        feed_type=None,
                        frequency=None
                    ):
        """returns set of users who have matching subscriptions
        and if potential_subscribers is not none, search will
        be limited to only potential subscribers,

        otherwise search is unrestricted

        todo: when EmailFeedSetting is merged into user table
        this method may become unnecessary
        """
        matching_feeds = self.filter(
                                        feed_type=feed_type,
                                        frequency=frequency
                                    )
        if potential_subscribers is not None:
            matching_feeds = matching_feeds.filter(
                            subscriber__in=potential_subscribers
                        )
        subscriber_set = set()
        for feed in matching_feeds:
            subscriber_set.add(feed.subscriber)

        return subscriber_set


class EmailFeedSetting(models.Model):
    #definitions of delays before notification for each type of notification frequency
    DELTA_TABLE = {
        'i': datetime.timedelta(minutes=5),  # instant emails are processed separately
        'd': datetime.timedelta(days=1),
        'w': datetime.timedelta(days=7),
        'n': datetime.timedelta(-1),  # Mañana, mañana - Later, maybe never .)
    }
    #definitions of feed schedule types
    FEED_TYPES = (
        'q_ask',  # questions that user asks
        'q_all',  # enture forum, tag filtered
        'q_ans',  # questions that user answers
        'q_sel',  # questions that user decides to follow
        'm_and_c'  # comments and mentions of user anywhere
    )
    #email delivery schedule when no email is sent at all
    NO_EMAIL_SCHEDULE = {
        'q_ask': 'n',
        'q_ans': 'n',
        'q_all': 'n',
        'q_sel': 'n',
        'm_and_c': 'n'
    }
    MAX_EMAIL_SCHEDULE = {
        'q_ask': 'i',
        'q_ans': 'i',
        'q_all': 'i',
        'q_sel': 'i',
        'm_and_c': 'i'
    }
    FEED_TYPE_CHOICES = (
        ('q_all', _('Entire forum')),
        ('q_ask', _('Questions that I asked')),
        ('q_ans', _('Questions that I answered')),
        ('q_sel', _('Individually selected questions')),
        ('m_and_c', _('Mentions and comment responses')),
    )
    UPDATE_FREQUENCY = (
        ('i', _('Instantly')),
        ('d', _('Daily')),
        ('w', _('Weekly')),
        ('n', _('No email')),
    )

    subscriber = models.ForeignKey(User, related_name='notification_subscriptions')
    feed_type = models.CharField(max_length=16, choices=FEED_TYPE_CHOICES)
    frequency = models.CharField(
                                max_length=8,
                                choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
                                default='n',
                            )
    added_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField(null=True)
    objects = EmailFeedSettingManager()

    class Meta:
        #added to make account merges work properly
        unique_together = ('subscriber', 'feed_type')
        app_label = 'openode'

    def __str__(self):
        if self.reported_at is None:
            reported_at = "'not yet'"
        else:
            reported_at = '%s' % self.reported_at.strftime('%d/%m/%y %H:%M')
        return 'Email feed for %s type=%s, frequency=%s, reported_at=%s' % (
                                                     self.subscriber,
                                                     self.feed_type,
                                                     self.frequency,
                                                     reported_at
                                                 )

    def save(self, *args, **kwargs):
        type = self.feed_type
        subscriber = self.subscriber
        similar = self.__class__.objects.filter(
                                            feed_type=type,
                                            subscriber=subscriber
                                        ).exclude(pk=self.id)
        if len(similar) > 0:
            raise IntegrityError('email feed setting already exists')
        super(EmailFeedSetting, self).save(*args, **kwargs)

    def get_previous_report_cutoff_time(self):
        now = datetime.datetime.now()
        return now - self.DELTA_TABLE[self.frequency]

    def should_send_now(self):
        # now = datetime.datetime.now()
        cutoff_time = self.get_previous_report_cutoff_time()
        if self.reported_at == None or self.reported_at <= cutoff_time:
            return True
        else:
            return False

    def mark_reported_now(self):
        self.reported_at = datetime.datetime.now()
        self.save()

#######################################


class OrganizationLogoStorage(FileSystemStorage):
    pass


class OrganizationManager(models.Manager):
    def get_query_set(self):
        return super(OrganizationManager, self).get_query_set().filter(approved = True)


class Organization(models.Model):
    """organization profile for openode"""
    OPEN = 0
    MODERATED = 1
    CLOSED = 2
    OPENNESS_CHOICES = (
        (OPEN, 'open'),
        (MODERATED, 'moderated'),
        (CLOSED, 'closed'),
    )

    approved = models.BooleanField(default=True, blank=True, verbose_name=_("Approved"))

    title = models.CharField(max_length=16, verbose_name=_("Title"))
    long_title = models.CharField(max_length=300, default='', blank=True, null=True, verbose_name=_("Long title"))

    def upload_to_fx(self, original_name):
        return os.path.join(
            "organization_logos",
            sanitize_file_name(original_name)
            )

    logo = models.FileField(
        upload_to=upload_to_fx,
        storage=OrganizationLogoStorage(
            location=settings.ORGANIZATION_LOGO_ROOT,
            base_url=settings.ORGANIZATION_LOGO_URL
        ),
        max_length=512,
        blank=True,
        null=True,
    )

    description = models.OneToOneField('Post',
        related_name='described_organization', null=True, blank=True, verbose_name=_("Description")
        )

    openness = models.SmallIntegerField(default=CLOSED, choices=OPENNESS_CHOICES)
    #preapproved email addresses and domain names to auto-join organizations
    #trick - the field is padded with space and all tokens are space separated
    preapproved_emails = models.TextField(null=True, blank=True, default='', verbose_name=_("Preapproved emails"))
    #only domains - without the '@' or anything before them
    preapproved_email_domains = models.TextField(null=True, blank=True, default='', verbose_name=_("Preapproved email domains"))


    # objects = OrganizationManager()
    #all_objects = models.Manager()

    class Meta:
        app_label = 'openode'

    def __unicode__(self):
        return self.title

    @property
    def logo_url(self):
        return self.logo.url if self.logo else ""

    @property
    def slug(self):
        return slugify(self.title)

    @property
    def full_title(self):
        return self.long_title or self.title

    def get_absolute_url(self):
        return reverse("organization_detail", args=[self.pk, self.slug])

    def get_logo_url(self, size=16, crop=False):
        """
            return thumbnail url for organization
        """
        GEOMETRY_STRING = "%sx%s" % (size, size)

        try:
            return get_thumbnail(
                self.logo,
                GEOMETRY_STRING,
                crop="center" if crop else None
            ).url
        except (IOError, ThumbnailError), e:
            logging.error(repr({
                "error": e,
                "method": "get_logo_url",
                "organization": self.pk,
                "logo": str(self.logo)
            }))
            return None


    def get_openness_choices(self):
        """gives answers to question
        "How can users join this organization?"
        """
        return (
            (Organization.OPEN, _('Can join when they want')),
            (Organization.MODERATED, _('Users ask permission')),
            (Organization.CLOSED, _('Moderator adds users'))
        )

    def get_openness_level_for_user(self, user):
        """returns descriptive value, because it is to be used in the
        templates. The value must match the verbose versions of the
        openness choices!!!
        """
        if user.is_anonymous():
            return 'closed'

        #todo - return 'closed' for internal per user organizations too

        if self.openness == Organization.OPEN:
            return 'open'

        #relying on a specific method of storage
        if email_is_allowed(
            user.email,
            allowed_emails=self.preapproved_emails,
            allowed_email_domains=self.preapproved_email_domains
        ):
            return 'open'

        if self.openness == Organization.MODERATED:
            return 'moderated'

        return 'closed'

    def clean(self):
        """called in `save()`
        """
        emails = functions.split_list(self.preapproved_emails)
        email_field = EmailField()
        try:
            map(lambda v: email_field.clean(v), emails)
        except exceptions.ValidationError:
            raise exceptions.ValidationError(
                _('Please give a list of valid email addresses.')
            )
        self.preapproved_emails = ' ' + '\n'.join(emails) + ' '

        domains = functions.split_list(self.preapproved_email_domains)
        domain_field = DomainNameField()
        try:
            map(lambda v: domain_field.clean(v), domains)
        except exceptions.ValidationError, e:
            raise e
        self.preapproved_email_domains = ' ' + '\n'.join(domains) + ' '

    def save(self, *args, **kwargs):
        self.clean()
        super(Organization, self).save(*args, **kwargs)


class OrganizationMembership(models.Model):
    """contains one-to-one relation to ``auth_user_organization``
    and extra membership profile fields"""

    organization = models.ForeignKey(Organization)
    user = models.ForeignKey(User)

    #note: this may hold info on when user joined, etc
    NONE = -1  # not part of the choices as for this records should be just missing
    PENDING = 0
    FULL = 1
    LEVEL_CHOICES = (  # 'none' is by absence of membership
        (PENDING, 'pending'),
        (FULL, 'full')
    )
    ALL_LEVEL_CHOICES = LEVEL_CHOICES + ((NONE, 'none'),)

    level = models.SmallIntegerField(
        default=FULL,
        choices=LEVEL_CHOICES,
    )

    class Meta:
        app_label = 'openode'
        unique_together = ('organization', 'user')

    def __unicode__(self):
        return '%s -> %s' % (self.user.screen_name, self.organization.full_title)

    @classmethod
    def get_level_value_display(cls, level):
        """returns verbose value given a numerical value
        includes the "fanthom" NONE
        """
        values_dict = dict(cls.ALL_LEVEL_CHOICES)
        return values_dict[level]


class LogManager(models.Manager):
    def log_action(self, user, obj, action, message='', object_force_pk=None):
        """
            @param user - User created some change
            @param obj - changed object
            @message - some additional message info
            @param - object_force_pk - object PK for case like logging deleting object, when object is already deleted from db (django remove object's pk)
        """
        e = self.model()
        e.user = user
        e.content_type = ContentType.objects.get(
            model=obj.__class__._meta.object_name.lower(),
            app_label=obj.__class__._meta.app_label.lower()
            )
        e.object_id = object_force_pk or smart_unicode(obj.pk)

        if hasattr(obj, 'log_repr'):
            object_repr = obj.log_repr()
        else:
            object_repr = '%s:%s' % (obj.__class__.__name__, e.object_id)
        e.object_repr = object_repr

        e.action = action
        e.message = message
        e.save()


class Log(models.Model):
    action_time = models.DateTimeField(_('action time'), auto_now=True)
    user = models.ForeignKey(User, related_name='logs')
    content_type = models.ForeignKey(ContentType, blank=True, null=True)
    object_id = models.TextField(_('object id'), blank=True, null=True)
    object_repr = models.TextField(_('object repr'), blank=True)

    action = models.PositiveIntegerField(_('action flag'), choices=const.LOG_ACTIONS)
    message = models.TextField(_('change message'), blank=True)

    objects = LogManager()

    class Meta:
        app_label = 'openode'
        permissions = (("view_other_user_log", "Can view other users logs"),)

    def get_object(self):
        "Returns the edited object represented by this log entry"
        try:
            return self.content_type.get_object_for_this_type(pk=self.object_id)
        except exceptions.ObjectDoesNotExist:
            return None
