# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext as _

BaseModel = models.Model


class Actuality(BaseModel):
    created = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=u'vytvořeno')
    author = models.ForeignKey("auth.User")
    text = models.TextField()

    class Meta:
        verbose_name = _(u"Actuality")
        verbose_name_plural = _(u"Actualities")
        ordering = ("created", )
        app_label = 'openode'
