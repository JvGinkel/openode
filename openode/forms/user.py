# -*- coding: utf-8 -*-

import logging

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from openode import const
from openode.forms import CleanCharField
# from openode.forms.node import NodeUserChoices
from openode.forms.widgets import Wysiwyg


class UserEmailForm(forms.Form):
    subject = forms.CharField(required=True)
    text = forms.CharField(widget=forms.Textarea, required=True)


class EditUserForm(forms.Form):
    # email = forms.EmailField(
    #     label=u'Email',
    #     required=True,
    #     max_length=255,
    #     widget=forms.TextInput(attrs={'size': 35})
    # )

    first_name = CleanCharField(
        required=True,
        max_length=30,
        widget=forms.TextInput()
    )

    last_name = CleanCharField(
        required=True,
        max_length=30,
        widget=forms.TextInput()
    )

    display_name = CleanCharField(
        required=False,
        max_length=25,
        widget=forms.TextInput()
    )

    user_description = forms.CharField(
        required=False,
        widget=Wysiwyg(mode='simple')
    )

    privacy_email_form = forms.BooleanField(required=False)
    privacy_show_followed = forms.BooleanField(required=False)

    def __init__(self, user, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        logging.debug('initializing the form')
        # self.fields['email'].initial = user.email
        self.fields['first_name'].initial = user.first_name
        self.fields['last_name'].initial = user.last_name
        self.fields['display_name'].initial = user.display_name
        self.fields['user_description'].initial = user.description.text if user.description else ''
        self.fields['privacy_email_form'].initial = user.privacy_email_form
        self.fields['privacy_show_followed'].initial = user.privacy_show_followed
        self.user = user

    # def clean_email(self):
    #     """For security reason one unique email in database"""
    #     if self.user.email != self.cleaned_data['email']:
    #         #todo dry it, there is a similar thing in openidauth
    #         if openode_settings.EMAIL_UNIQUE is True:
    #             if 'email' in self.cleaned_data:
    #                 try:
    #                     User.objects.get(email=self.cleaned_data['email'])
    #                 except User.DoesNotExist:
    #                     return self.cleaned_data['email']
    #                 except User.MultipleObjectsReturned:
    #                     raise forms.ValidationError(_(
    #                         'this email has already been registered, '
    #                         'please use another one')
    #                     )
    #                 raise forms.ValidationError(_(
    #                     'this email has already been registered, '
    #                     'please use another one')
    #                 )
    #     return self.cleaned_data['email']


from openode.models.thread import Thread
from django_select2 import AutoModelSelect2Field


class UserChoicesField(AutoModelSelect2Field):

    search_fields = [
        'display_name__icontains',
        'last_name__icontains',
        'first_name__icontains',
        'email__icontains'
    ]


class FilteredUserChoicesField(UserChoicesField):
    '''http://django-select2.readthedocs.org/en/latest/ref_fields.html#class-diagram
    This needs to be subclassed. The first instance of a class (sub-class) is
    used to serve all incoming json query requests for that type (class).
    '''
    pass


class QuestionFlowNodeResponsibleUsersForm(forms.Form):

    question = forms.ModelChoiceField(queryset=Thread.objects.none())

    def __init__(self, *args, **kwargs):

        self.question = kwargs.pop("question", None)

        super(QuestionFlowNodeResponsibleUsersForm, self).__init__(*args, **kwargs)

        if self.question is not None:
            if self.question.node.visibility in [const.NODE_VISIBILITY_SEMIPRIVATE, const.NODE_VISIBILITY_PRIVATE]:
                self.fields[self._get_responsible_users_field_name()] = FilteredUserChoicesField(
                    label=_("Responsible users"),
                    queryset=self.question.node.get_responsible_persons()
                )

            else:
                self.fields[self._get_responsible_users_field_name()] = UserChoicesField(
                    label=_("Responsible users"),
                    queryset=User.objects.filter(is_active=True)
                )

            self.fields["question"].queryset = Thread.objects.filter(pk=self.question.pk)
            self.fields["question"].initial = self.question.pk
            self.fields["question"].widget = forms.HiddenInput()

    def _get_responsible_users_field_name(self):
        """Select2 must have unique html id on page.
        """
        if self.question.node.visibility in [const.NODE_VISIBILITY_SEMIPRIVATE, const.NODE_VISIBILITY_PRIVATE]:
            return "responsible_users"
        else:
            return "responsible_users_%s" % self.question.pk
