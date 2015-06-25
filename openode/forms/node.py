# -*- coding: utf-8 -*-
from datetime import datetime

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from django_select2 import AutoModelSelect2Field, ModelSelect2Field

# from openode.forms import EditorField
from openode import const
from openode.forms.widgets import Wysiwyg
from openode.models import Node, NodeUser
from openode.models.user import Organization
from openode.utils.url_utils import reverse_lazy
#######################################


class ReadOnlyUser(forms.HiddenInput):
    def render(self, name, value, attrs=None):
        return mark_safe('%s%s' % (User.objects.get(pk=value).email, super(ReadOnlyUser, self).render(name, value, attrs)))


class NodeAnnotationEditForm(forms.Form):
    # text = EditorField()
    text = forms.CharField(widget=Wysiwyg)

    def __init__(self, *args, **kwargs):
        node = kwargs.pop("node")
        super(NodeAnnotationEditForm, self).__init__(*args, **kwargs)

        upload_url = reverse_lazy("upload_attachment_node", args=[node.pk])
        self.fields["text"].widget = Wysiwyg(
            mode="full",
            upload_url=upload_url
        )


class NodeSettingsForm(forms.ModelForm):
    class Meta:
        model = Node
        fields = (
            'title', 'long_title',
            'visibility', 'readonly',
            'closed', 'close_reason',
            # 'module_annotation',
            'module_qa', 'module_forum', 'module_library', 'default_module',
            'module_qa_readonly', 'module_forum_readonly', 'module_library_readonly',
            "is_question_flow_enabled",
        )
        widgets = {
            'close_reason': forms.TextInput,
            'visibility': forms.RadioSelect
        }

    def __init__(self, *args, **kwargs):
        super(NodeSettingsForm, self).__init__(*args, **kwargs)
        # add helptexts to radioselect labels for visibility field
        NODE_VISIBILITY_CHOICES_HELPTEXT = [(i, mark_safe(u"%s<br /><small class=\"helptext\">%s</small>" % (j, k))) for i, j, k in const.NODE_VISIBILITY]
        self.fields['visibility'].choices = NODE_VISIBILITY_CHOICES_HELPTEXT
        self.fields['batch_add_users_role'] = forms.CharField(widget=forms.Select(choices=const.NODE_USER_ROLES), required=False)
        self.fields['batch_add_users_emails'] = forms.CharField(widget=forms.Textarea, required=False)

    def clean_batch_add_users_emails(self):
        batch_add_users_emails = self.cleaned_data["batch_add_users_emails"]
        not_valid_emails = []
        existed_customer_users = []
        not_existed_user = []
        error_msgs = []
        self.batch_add_users = []
        for email in batch_add_users_emails.split(';'):
            email = email.strip()
            try:
                validate_email(email)
            except ValidationError:
                not_valid_emails.append(email)
                continue
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                not_existed_user.append(email)
                continue
            if self.instance.users.filter(pk=user.pk).exists():
                existed_customer_users.append(email)
                continue
            self.batch_add_users.append(user)

        if any(not_valid_emails):
            if len(not_valid_emails) == 1:
                error_msgs.append(_('%s is not valid email.') % not_valid_emails[0])
            else:
                error_msgs.append(_('%s are not valid emails.') % ', '.join(not_valid_emails))
        if any(not_existed_user):
            if len(not_existed_user) == 1:
                error_msgs.append(_('%s is not existing user.') % not_existed_user[0])
            else:
                error_msgs.append(_('%s are not existing users.') % ', '.join(not_existed_user))
        if any(existed_customer_users):
            if len(existed_customer_users) == 1:
                error_msgs.append(_('%s is already user with role in node.') % existed_customer_users[0])
            else:
                error_msgs.append(_('%s are already users with role in node.') % ', '.join(existed_customer_users))
        if error_msgs:
            self._errors['batch_add_users_emails'] = self.error_class(error_msgs)

        return batch_add_users_emails

    def save(self, *args, **kwargs):
        user = kwargs.pop('user')
        old_instance = Node.objects.get(pk=self.instance.pk)
        if not old_instance.closed and self.instance.closed:
            self.instance.closed_by = user
            self.instance.closed_at = datetime.now()
        elif not self.instance.closed:
            self.instance.close_reason = ''

        batch_add_users_role = self.cleaned_data["batch_add_users_role"]
        for user in self.batch_add_users:
            cu = NodeUser(user=user, node=self.instance)
            cu.role = batch_add_users_role
            cu.save()

        return super(NodeSettingsForm, self).save(*args, **kwargs)


class NodeUserChoices(AutoModelSelect2Field):
    queryset = User.objects.filter(is_active=True)
    search_fields = ['display_name__icontains', 'last_name__icontains', 'first_name__icontains', 'email__icontains']


class NodeUserForm(forms.ModelForm):
    class Meta:
        model = NodeUser

    def __init__(self, *args, **kwargs):
        super(NodeUserForm, self).__init__(*args, **kwargs)
        if not self.instance.pk is None:
            self.fields['user'].widget = ReadOnlyUser()
        else:
            self.fields['user'] = NodeUserChoices()


class NodeUserAdminForm(forms.ModelForm):
    class Meta:
        model = NodeUser

    def __init__(self, *args, **kwargs):
        super(NodeUserAdminForm, self).__init__(*args, **kwargs)
        if not self.instance.pk is None:
            self.fields['user'].widget = ReadOnlyUser()
        else:
            self.fields['user'] = ModelSelect2Field(queryset=User.objects.filter(is_active=True))


class PerexesEditForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(PerexesEditForm, self).__init__(*args, **kwargs)
        upload_url = reverse_lazy("upload_attachment_node", args=[self.instance.pk])

        for key in Node.WYSIWYG_FIELDS:
            if key not in self.fields:
                continue
            self.fields[key].widget = Wysiwyg(
                mode="full",
                upload_url=upload_url
            )


class AskToCreateNodeForm(forms.Form):
    name = forms.CharField(label=_('Name'), max_length=300)
    note = forms.CharField(label=_('Note'), widget=forms.Textarea)
