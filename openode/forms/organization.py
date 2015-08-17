# -*- coding: utf-8 -*-

from django import forms

from openode.models.user import Organization
from openode.models.post import Post
from openode.forms.widgets import Wysiwyg
from django.utils.translation import ugettext as _


class OrganizationLogoForm(forms.ModelForm):
    desc = forms.CharField(widget=Wysiwyg(mode='simple', width='800px'), required=False, label=_('description'))


    class Meta:
        fields = ("logo", )
        model = Organization


class OrganizationForm(forms.ModelForm):
    desc = forms.CharField(widget=Wysiwyg(mode='simple', width='800px'), required=False, label=_('description'))

    class Meta:
        model = Organization
        fields = ('title', 'long_title', 'desc', 'logo', 'preapproved_emails', 'preapproved_email_domains')


    def __init__(self, *args, **kwargs):
        super(OrganizationForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.description:
            self.fields['desc'].initial = self.instance.description.text

    def save(self, request, force_insert=False, force_update=False, commit=True):
        org = super(OrganizationForm, self).save(commit=True)
        org.approved = False
        description = self.cleaned_data['desc']

        request.user.post_object_description(org, body_text=description)
        org.save()
        return org
