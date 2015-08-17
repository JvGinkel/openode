# -*- coding: utf-8 -*-

from django import forms
from django.utils.safestring import mark_safe
# from django.core.urlresolvers import reverse

from django.conf import settings

################################################################################

JS_WRAPPER = u'''
    <script type="text/javascript">
        %s
    </script>
'''


def add_class(widget, css_class, title=None):
    """
    Helper function - adds CSS class or title to widget
    """
    attrs = widget.attrs or {}
    if 'class' in attrs:
        attrs['class'] = u'%s %s' % (attrs['class'], css_class)
    else:
        attrs['class'] = css_class

    if title:
        if 'title' in attrs:
            attrs['title'] = u'%s %s' % (attrs['title'], title)
        else:
            attrs['title'] = title

    widget.attrs = attrs


class Wysiwyg(forms.Textarea):
    """
        Wysiwyg textarea widget
    """
    class Media:
        js = [
            '%sdefault/media/ckeditor/ckeditor.js' % settings.STATIC_URL,
        ]
        css = {
            "all": (
                '%sdefault/media/css/admin.css' % settings.STATIC_URL,
            )
        }

    def __init__(self, *args, **kwargs):

        # wysiwyg defaults
        self.mode = kwargs.pop("mode", "simple")
        self.upload_url = kwargs.pop("upload_url", '')
        self.width = kwargs.pop("width", "100%")

        super(Wysiwyg, self).__init__(*args, **kwargs)

    # mce_settings = dict(
    #     mode="exact",
    #     height=300
    # )

    # def update_settings(self, custom):
    #     return_dict = self.mce_settings.copy()
    #     return_dict.update(custom)
    #     self.mce_settings = return_dict
    #     return return_dict

    def render(self, name, value, attrs=None):

        mode_map = {
            "simple": settings.WYSIWYG_SETTING_SIMPLE,
            "full": settings.WYSIWYG_SETTING_FULL,
        }

        wysiwyg_conf = {
            'name': name,
            "width": self.width,
            "settings": mode_map.get(self.mode, settings.WYSIWYG_SETTING_SIMPLE),
            "upload_url": self.upload_url,
        }

        js = u"""
            CKEDITOR.replace('%(name)s', {
                filebrowserUploadUrl: '%(upload_url)s',
                removeButtons: "",
                forcePasteAsPlainText: true,
                entities: false,
                width: "%(width)s",
                toolbar: %(settings)s
            });
        """ % wysiwyg_conf

        return mark_safe("%s%s" % (
            super(Wysiwyg, self).render(name, value, attrs),
            mark_safe(JS_WRAPPER % js)
        ))
