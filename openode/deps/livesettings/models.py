from django.conf import settings
from django.db import models
from django.db.models import loading
from keyedcache import cache_key, cache_get, cache_set, NotCachedError
from keyedcache.models import CachedObjectMixin
import logging

log = logging.getLogger('configuration.models')

__all__ = ['SettingNotSet', 'Setting', 'LongSetting', 'find_setting']


def find_setting(group, key):
    """Get a setting or longsetting by group and key, cache and return it."""

    setting = None
    use_db, overrides = (True, {})
    ck = cache_key('Setting', group, key)

    grp = overrides.get(group, None)

    if grp and key in grp:
        val = grp[key]
        setting = ImmutableSetting(key=key, group=group, value=val)
        log.debug('Returning overridden: %s', setting)
    elif use_db:
        try:
            setting = cache_get(ck)

        except NotCachedError, nce:
            if loading.app_cache_ready():
                try:
                    setting = Setting.objects.get(key__exact=key, group__exact=group)

                except Setting.DoesNotExist:
                    # maybe it is a "long setting"
                    try:
                        setting = LongSetting.objects.get(key__exact=key, group__exact=group)

                    except LongSetting.DoesNotExist:
                        pass

                cache_set(ck, value=setting)

    else:
        grp = overrides.get(group, None)
        if grp and grp.has_key(key):
            val = grp[key]
            setting = ImmutableSetting(key=key, group=group, value=val)
            log.debug('Returning overridden: %s', setting)

    if not setting:
        raise SettingNotSet(key, cachekey=ck)

    return setting


class SettingNotSet(Exception):
    def __init__(self, k, cachekey=None):
        self.key = k
        self.cachekey = cachekey
        self.args = [self.key, self.cachekey]


class ImmutableSetting(object):

    def __init__(self, group="", key="", value=""):
        self.group = group
        self.key = key
        self.value = value

    def cache_key(self, *args, **kwargs):
        return cache_key('OverrideSetting', self.group, self.key)

    def delete(self):
        pass

    def save(self, *args, **kwargs):
        pass

    def __repr__(self):
        return "ImmutableSetting: %s.%s=%s" % (self.group, self.key, self.value)


class Setting(models.Model, CachedObjectMixin):
    group = models.CharField(max_length=100, blank=False, null=False)
    key = models.CharField(max_length=100, blank=False, null=False)
    value = models.CharField(max_length=255, blank=True)

    def __nonzero__(self):
        return self.id is not None

    def cache_key(self, *args, **kwargs):
        return cache_key('Setting', self.group, self.key)

    def delete(self):
        self.cache_delete()
        super(Setting, self).delete()

    def save(self, force_insert=False, force_update=False):
        super(Setting, self).save(force_insert=force_insert, force_update=force_update)

        self.cache_set()

    def cache_set(self, *args, **kwargs):
        val = kwargs.pop('value', self)
        key = self.cache_key(*args, **kwargs)
        #TODO: fix this with Django's > 1.3 CACHE dict setting support
        length = getattr(settings, 'LIVESETTINGS_CACHE_TIMEOUT', settings.CACHE_TIMEOUT)
        cache_set(key, value=val, length=length)

    class Meta:
        unique_together = ('group', 'key')


class LongSetting(models.Model, CachedObjectMixin):
    """A Setting which can handle more than 255 characters"""
    group = models.CharField(max_length=100, blank=False, null=False)
    key = models.CharField(max_length=100, blank=False, null=False)
    value = models.TextField(blank=True)

    def __nonzero__(self):
        return self.id is not None

    def cache_key(self, *args, **kwargs):
        # note same cache pattern as Setting.  This is so we can look up in one check.
        # they can't overlap anyway, so this is moderately safe.  At the worst, the
        # Setting will override a LongSetting.
        return cache_key('Setting', self.group, self.key)

    def delete(self):
        self.cache_delete()
        super(LongSetting, self).delete()

    def save(self, force_insert=False, force_update=False):
        super(LongSetting, self).save(force_insert=force_insert, force_update=force_update)
        self.cache_set()

    def cache_set(self, *args, **kwargs):
        val = kwargs.pop('value', self)
        key = self.cache_key(*args, **kwargs)
        #TODO: fix this with Django's > 1.3 CACHE dict setting support
        length = getattr(settings, 'LIVESETTINGS_CACHE_TIMEOUT', settings.CACHE_TIMEOUT)
        cache_set(key, value=val, length=length)

    class Meta:
        unique_together = ('group', 'key')
