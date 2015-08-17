import re
# import logging
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
# from django.conf import settings
from openode.models.base import BaseQuerySetManager
from openode.conf import settings as openode_settings


def delete_tags(tags):
    """deletes tags in the list"""
    tag_ids = [tag.id for tag in tags]
    Tag.objects.filter(id__in=tag_ids).delete()


def get_tags_by_names(tag_names):
    """returns query set of tags
    and a set of tag names that were not found
    """
    tags = Tag.objects.filter(name__in=tag_names)
    #if there are brand new tags, create them
    #and finalize the added tag list
    if tags.count() < len(tag_names):
        found_tag_names = set([tag.name for tag in tags])
        new_tag_names = set(tag_names) - found_tag_names
    else:
        new_tag_names = set()

    return tags, new_tag_names


def filter_tags_by_status(tags, status=None):
    """returns a list or a query set of tags which are accepted"""
    if isinstance(tags, models.query.QuerySet):
        return tags.filter(status=status)
    else:
        return [tag for tag in tags if tag.status == status]


def filter_accepted_tags(tags):
    return filter_tags_by_status(tags, status=Tag.STATUS_ACCEPTED)


def filter_suggested_tags(tags):
    return filter_tags_by_status(tags, status=Tag.STATUS_SUGGESTED)


def is_preapproved_tag_name(tag_name):
    """true if tag name is in the category tree
    or any other container of preapproved tags"""
    #get list of preapproved tags, to make exceptions for
    return False


def separate_unused_tags(tags):
    """returns two lists::
    * first where tags whose use counts are >0
    * second - with use counts == 0
    """
    used = list()
    unused = list()
    for tag in tags:
        if tag.used_count == 0:
            unused.append(tag)
        else:
            assert(tag.used_count > 0)
            used.append(tag)
    return used, unused


def tags_match_some_wildcard(tag_names, wildcard_tags):
    """Same as
    :meth:`~openode.models.tag.TagQuerySet.tags_match_some_wildcard`
    except it works on tag name strings
    """
    for tag_name in tag_names:
        for wildcard_tag in sorted(wildcard_tags):
            if tag_name.startswith(wildcard_tag[:-1]):
                return True
    return False


class TagQuerySet(models.query.QuerySet):

    def get_all_valid_tags(self):
        return self.all().filter(
            deleted=False
        ).exclude(
            used_count=0
        ).order_by("-id")

    def get_valid_tags(self, page_size):
        return self.get_all_valid_tags()[:page_size]

    def update_use_counts(self, tags):
        """Updates the given Tags with their current use counts."""
        for tag in tags:
            tag.used_count = tag.threads.count()
            tag.save()

    def mark_undeleted(self):
        """removes deleted(+at/by) marks"""
        self.update(# undelete them
            deleted=False,
            deleted_by=None,
            deleted_at=None
        )

    def tags_match_some_wildcard(self, wildcard_tags=None):
        """True if any one of the tags in the query set
        matches a wildcard

        :arg:`wildcard_tags` is an iterable of wildcard tag strings

        todo: refactor to use :func:`tags_match_some_wildcard`
        """
        for tag in self.all():
            for wildcard_tag in sorted(wildcard_tags):
                if tag.name.startswith(wildcard_tag[:-1]):
                    return True
        return False

    def get_by_wildcards(self, wildcards=None):
        """returns query set of tags that match the wildcard tags
        wildcard tag is guaranteed to end with an asterisk and has
        at least one character preceding the the asterisk. and there
        is only one asterisk in the entire name
        """
        if wildcards is None or len(wildcards) == 0:
            return self.none()
        first_tag = wildcards.pop()
        tag_filter = models.Q(name__startswith=first_tag[:-1])
        for next_tag in wildcards:
            tag_filter |= models.Q(name__startswith=next_tag[:-1])
        return self.filter(tag_filter)

    def get_related_to_search(self, threads, ignored_tag_names):
        """Returns at least tag names, along with use counts"""
        tags = self.filter(threads__in=threads).annotate(local_used_count=models.Count('id')).order_by('-local_used_count', 'name')
        if ignored_tag_names:
            tags = tags.exclude(name__in=ignored_tag_names)
        tags = tags.exclude(deleted=True)
        return list(tags[:50])


class TagManager(BaseQuerySetManager):
    """chainable custom filter query set manager
    for :class:``~openode.models.Tag`` objects
    """
    def get_query_set(self):
        return TagQuerySet(self.model)

    def valid_tags(self):
        return super(TagManager, self).get_query_set().filter(threads__is_deleted=False).distinct()

    def get_content_tags(self):
        """temporary function that filters out the organization tags"""
        return self.all()

    def create(self, name=None, created_by=None, **kwargs):
        """Creates a new tag"""
        if created_by.can_create_tags() or is_preapproved_tag_name(name):
            status = Tag.STATUS_ACCEPTED
        else:
            status = Tag.STATUS_SUGGESTED

        kwargs['created_by'] = created_by
        kwargs['name'] = name
        kwargs['status'] = status

        return super(TagManager, self).create(**kwargs)

    def create_suggested_tag(self, tag_names=None, user=None):
        """This function is not used, and will probably need
        to be retired. In the previous version we were sending
        email to admins when the new tags were created,
        now we have a separate page where new tags are listed.
        """
        #todo: stuff below will probably go after
        #tag moderation actions are implemented
        from openode import mail
        from openode.mail import messages
        body_text = messages.notify_admins_about_new_tags(
                                tags=tag_names,
                                user=user,
                                thread=self
                            )
        site_name = openode_settings.APP_SHORT_NAME
        subject_line = _('New tags added to %s') % site_name
        mail.mail_moderators(
            subject_line,
            body_text,
            headers={'Reply-To': user.email}
        )

        msg = _(
            'Tags %s are new and will be submitted for the '
            'moderators approval'
        ) % ', '.join(tag_names)
        user.message_set.create(message=msg)

    def create_in_bulk(self, tag_names=None, user=None):
        """creates tags by names. If user can create tags,
        then they are set status ``STATUS_ACCEPTED``,
        otherwise the status will be set to ``STATUS_SUGGESTED``.

        One exception: if suggested tag is in the category tree
        and source of tags is category tree - then status of newly
        created tag is ``STATUS_ACCEPTED``
        """

        #load suggested tags
        pre_suggested_tags = self.filter(
            name__in=tag_names, status=Tag.STATUS_SUGGESTED
        )

        #deal with suggested tags
        if user.can_create_tags():
            #turn previously suggested tags into accepted
            pre_suggested_tags.update(status=Tag.STATUS_ACCEPTED)
        else:
            #increment use count and add user to "suggested_by"
            for tag in pre_suggested_tags:
                tag.times_used += 1
                tag.suggested_by.add(user)
                tag.save()

        created_tags = list()
        pre_suggested_tag_names = list()
        for tag in pre_suggested_tags:
            pre_suggested_tag_names.append(tag.name)
            created_tags.append(tag)

        for tag_name in set(tag_names) - set(pre_suggested_tag_names):
            #status for the new tags is automatically set within the create()
            new_tag = Tag.objects.create(name=tag_name, created_by=user)
            created_tags.append(new_tag)

            if new_tag.status == Tag.STATUS_SUGGESTED:
                new_tag.suggested_by.add(user)

        return created_tags


def clean_organization_name(name):
    """organization names allow spaces,
    tag names do not, so we use this method
    to replace spaces with dashes"""
    return re.sub('\s+', '-', name.strip())


class Tag(models.Model):
    #a couple of status constants
    STATUS_SUGGESTED = 0
    STATUS_ACCEPTED = 1

    name = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(User, related_name='created_tags')

    suggested_by = models.ManyToManyField(
        User, related_name='suggested_tags',
        help_text='Works only for suggested tags for tag moderation'
    )

    status = models.SmallIntegerField(default=STATUS_ACCEPTED)

    # Denormalised data
    used_count = models.PositiveIntegerField(default=0)

    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, related_name='deleted_tags')

    tag_description = models.OneToOneField(
                                'Post',
                                null=True,
                                related_name='described_tag'
                            )

    objects = TagManager()

    class Meta:
        app_label = 'openode'
        db_table = u'tag'
        ordering = ('-used_count', 'name')
        permissions = (("frontend_retag", "Can retag posts on frontend"),)
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')

    def __unicode__(self):
        """
        str repr method replaces '_' for spaces
        """
        return self.name


class MarkedTag(models.Model):
    TAG_MARK_REASONS = (
        ('good', _('interesting')),
        ('bad', _('ignored')),
        ('subscribed', _('subscribed')),
    )
    tag = models.ForeignKey('Tag', related_name='user_selections')
    user = models.ForeignKey(User, related_name='tag_selections')
    reason = models.CharField(max_length=16, choices=TAG_MARK_REASONS)

    class Meta:
        app_label = 'openode'


def get_organizations():
    from openode.models import Organization
    return Organization.objects.all()


def get_organization_names():
    #todo: cache me
    return get_organizations().values_list('name', flat=True)
