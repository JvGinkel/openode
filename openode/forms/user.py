# -*- coding: utf-8 -*-
import logging
from django import forms
# from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User

from openode.forms import CleanCharField
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


class QuestionFlowNodeResponsibleUsers(forms.Form):

    responsible_users = forms.ModelChoiceField(queryset=User.objects.none())
    question = forms.ModelChoiceField(queryset=Thread.objects.none())

    def __init__(self, *args, **kwargs):
        question = kwargs.pop("question", None)
        super(QuestionFlowNodeResponsibleUsers, self).__init__(*args, **kwargs)
        if question is not None:
            self.fields["responsible_users"].queryset = question.node.get_responsible_persons()
            self.fields["question"].queryset = Thread.objects.filter(pk=question.pk)
            self.fields["question"].initial = question.pk
            self.fields["question"].widget = forms.HiddenInput()
