# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext as _

from openode.utils.slug import slugify

from django.conf import settings

BaseModel = models.Model


################################################################################

MENU_UPPER = "upper"
MENU_FOOTER = "footer"
MENU = (
    (MENU_UPPER, _("Upper")),
    (MENU_FOOTER, _("Footer")),
)

################################################################################

# from django.conf import settings
# settings.LANGUAGES


class StaticPage(BaseModel):
    """
        static page model
    """
    language = models.CharField(max_length=32, choices=settings.LANGUAGES, verbose_name=_(u"Language"))
    title = models.CharField(max_length=255, verbose_name=_(u"Title"))
    slug = models.SlugField(max_length=255,
        help_text=_(u"Carefully, fragile! If changed, url of corresponding MenuItems has to be changed too. Allowed characters are a-z, A-Z, 0-9, \"-\" and \"_\""),
        verbose_name=_(u"Slug")
        )
    seo_title = models.CharField(max_length=255, verbose_name=_(u"Seo title"), null=True, blank=True)
    seo_description = models.CharField(max_length=512, verbose_name=_(u"Seo description"), null=True, blank=True)
    seo_keywords = models.CharField(max_length=512, verbose_name=_(u"Seo keywords"), null=True, blank=True)
    text = models.TextField(verbose_name=_(u"Text"))
    last_changed = models.DateTimeField(auto_now=True, verbose_name=_(u"Last changed"))

    class Meta:
        verbose_name = _(u"Static page")
        verbose_name_plural = _(u"Static pages")
        unique_together = ("language", "slug")
        app_label = 'openode'

    def __unicode__(self):
        return u"StaticPage %s %s" % (
            self.get_language_display(),
            self.title[:20]
        )

    def save(self, *args, **kwargs):
        if not self.slug.strip():
            self.slug = slugify(self.title).replace("_", "-").strip()
        return super(StaticPage, self).save(*args, **kwargs)

#######################################


class MenuItem(BaseModel):
    """
        Menu item model
    """
    menu = models.CharField(max_length=32, choices=MENU,
        help_text=_(u"Choose a menu that this record belongs to."),
        verbose_name=_(u"Menu")
        )
    title = models.CharField(max_length=255, verbose_name=_(u"Title"))
    language = models.CharField(max_length=32, choices=settings.LANGUAGES, verbose_name=_(u"Language"))
    position = models.IntegerField(help_text=_(u"Choose a number to be used to sort items within a menu. (in ascending order)."),
        verbose_name=_(u"Position"),
        default=0,
        )
    url = models.CharField(max_length=255,
        help_text=_("""
            Carefully, fragile! Manually filled href atribute to a link. (typically StaticPage - relative starting with /, or external link starting with http://).<br />
            For link to locale static page use: "/&lt;static-page-slug&gt;.html". <br />
            Example: Static page with slug "about" should have url "/about.html"
        """),
        verbose_name=_(u"Url")
    )

    class Meta:
        verbose_name = _(u"Menu item")
        verbose_name_plural = _(u"Menu items")
        ordering = ("language", "menu", "position")
        app_label = 'openode'

    def __unicode__(self):
        return u"MenuItem %s %s %s" % (
            self.get_language_display(),
            self.position,
            self.url
        )
