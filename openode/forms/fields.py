# -*- coding: utf-8 -*-

import re

from django.utils.translation import ugettext_lazy as _
import HTMLParser
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape, strip_spaces_between_tags, strip_tags
from django.utils.safestring import mark_safe

from openode.utils.html import bleach_html


class WysiwygFormField(forms.CharField):
    """
        Char field with textarea wysiwyg widget
    """

    TO_REPLACE = [
            ["\r", ""],
            ["<br />", "<br>"],
            ["<hr />", "<hr>"],
        ]

    def find_diff(self, text_1, text_2):
        """
            find first diff between two texts and return sample with this first diff
        """
        out = ""
        diff = False

        for i in range(min(len(text_1), len(text_2))):
            char_1 = text_1[i]
            char_2 = text_2[i]

            if char_1 == char_2:
                out += char_1
            else:
                out += char_1
                diff = True
                break

        if diff:
            out += text_1[i + 1: i + 20]
            out = out[-50:]

        return escape(out)

    def clean(self, value):
        """
            clean raw html
        """

        value = super(WysiwygFormField, self).clean(value).strip()

        # replace html entities to unicode chars
        # &times; > ×, &amp; > & ...
        value = HTMLParser.HTMLParser().unescape(value)

        # force replacing
        for old, new in self.TO_REPLACE:
            value = value.replace(old, new)

        # update IMG tag:
        #   replace
        #   <img src="link.jpg" /> to
        #   <img src="link.jpg">
        for img in re.findall("\<img\ .+\ />+", value):
            clean_img = re.sub("\ ?/>", ">", img)
            value = value.replace(img, clean_img)

        # clean html
        cleaned = bleach_html(value)

        # remove whitespaces
        value = strip_spaces_between_tags(value)
        cleaned = strip_spaces_between_tags(cleaned)

        # diff cleaned value with 'raw' value
        space_re = re.compile(" ")
        if not (re.sub(space_re, "", cleaned) == re.sub(space_re, "", value)):
            diff = self.find_diff(value, cleaned)
            raise ValidationError(mark_safe("Not supported html: %s" % diff))

        # check and valid length
        raw_text_len = len(strip_tags(value).strip())
        if self.min_length and (raw_text_len < self.min_length):
            raise ValidationError(
                mark_safe(_(u'Text must be at least %d characters long.' % self.min_length))
            )
        if self.max_length and (raw_text_len > self.max_length):
            raise ValidationError(
                mark_safe(_(u'Text must be shorter than %d characters.' % self.min_length))
            )

        return cleaned
