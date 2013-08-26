# -*- coding: utf-8 -*-

from django import forms

from openode.models.user import Organization


class OrganizationLogoForm(forms.ModelForm):
    class Meta:
        fields = ("logo", )
        model = Organization
