# -*- coding: utf-8 -*-
"""
:synopsis: connector to standard Django admin interface

To make more models accessible in the Django admin interface, add more classes subclassing ``django.contrib.admin.Model``

Names of the classes must be like `SomeModelAdmin`, where `SomeModel` must
exactly match name of the model used in the project
"""
from django import forms

from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.widgets import FilteredSelectMultiple

from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.translation import ugettext as _
from django.utils.text import capfirst

from mptt.admin import MPTTModelAdmin

from openode import const
from openode import models

from openode.forms.admin import NodeMoveForm, NodeAdminForm, BaseAdminModelForm
from openode.forms.node import NodeUserAdminForm

from openode.models.thread import Thread

from openode.forms.widgets import Wysiwyg

#######################################


class BaseAdminAuthenticationForm(AdminAuthenticationForm):
    """
    A custom authentication form used in the admin app.

    """

    username = forms.CharField(label=_("Email"), max_length=30)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        message = _("Please enter a correct email and password. "
                              "Note that both fields are case-sensitive.")

        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(message)
            elif not self.user_cache.is_active or not self.user_cache.is_staff:
                raise forms.ValidationError(message)
        self.check_for_test_cookie()
        return self.cleaned_data


AdminSite.login_form = BaseAdminAuthenticationForm
AdminSite.login_template = 'admin/common/login.html'


class BaseAdmin(admin.ModelAdmin):
    """
        base admin class
    """

    form = BaseAdminModelForm

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = self.form.formfield_for_dbfield(
            super(BaseAdmin, self).formfield_for_dbfield,
            db_field,
            **kwargs
            )
        return formfield

#######################################


class TagAdmin(BaseAdmin):
    """Tag admin class"""
    list_display = ("name", "used_count", "created_by")
    fields = (
        'name', 'created_by',
    )


class VoteAdmin(BaseAdmin):
    """  admin class"""


class PostRevisionAdmin(BaseAdmin):
    """  admin class"""


class ActivityAdmin(BaseAdmin):
    """  admin class"""

#######################################


class NodeUserInline(admin.TabularInline):
    model = models.NodeUser
    form = NodeUserAdminForm


class NodeAdmin(BaseAdmin, MPTTModelAdmin):
    """Node admin
    """
    list_display = (
        "title", "style",
        # "module_annotation",
        "module_qa", "module_forum", "module_library", "default_module",
        "visibility", 'readonly', "closed", "deleted",
        "display_opened",
        "tree_move",
    )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("dt_created", "dt_changed",)
    fields = (
        'parent', 'title', 'long_title', 'slug',

        'style', 'display_opened',
        'visibility',

        # 'module_annotation',
        'module_qa',
        'module_forum',
        'module_library',
        'default_module',
        # 'readonly',
        'deleted',
        'closed', 'closed_by', 'closed_at', 'close_reason',

        "perex_node_important",
        "perex_node",

        "perex_annotation_important",
        "perex_annotation",

        "perex_qa_important",
        "perex_qa",

        "perex_forum_important",
        "perex_forum",

        "perex_library_important",
        "perex_library",

        "dt_created", "dt_changed",
    )

    inlines = [
        NodeUserInline,
    ]

    form = NodeAdminForm

    def tree_move(self, obj):
        return "<a href='%s'>%s</a>" % (
            reverse("admin:move_node", args=[obj.pk]),
            _(u"Move")
            )
    tree_move.allow_tags = True
    tree_move.short_description = _(u"Move")

    # admin views

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        return patterns('',
            url(r'^(?P<obj_pk>\d+)/move/$', self.admin_site.admin_view(self.move), name='move_node'),
        ) + super(NodeAdmin, self).get_urls()

    def move(self, request, obj_pk):
        """
            Reorg. view, for changes in MTPP tree
        """
        obj = get_object_or_404(self.model, pk=obj_pk)
        if request.method == "POST":
            form = NodeMoveForm(request.POST, instance=obj)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(reverse("admin:openode_node_changelist"))
        else:
            form = NodeMoveForm(instance=obj)

        return render(
            request,
            'admin/common/move.html',
            {'form': form,
             "obj": obj,
             'app_label': self.opts.app_label,
             'verbose_name_plural': self.opts.verbose_name_plural
            })

#######################################

# TODO check!


class ActualityAdminForm(BaseAdminModelForm):
    class Meta:
        widgets = {
            'text': Wysiwyg(mode='full', width="800px")
        }


class ActualityAdmin(BaseAdmin):
    """
        Actuality admin
    """
    readonly_fields = ("author", "created")
    list_display = ("admin_text", "author", "created")
    form = ActualityAdminForm

    def admin_text(self, obj):
        return u"%s%s" % (
            obj.text[:20],
            " ..." if obj.text[20:] else ""
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super(ActualityAdmin, self).save_model(request, obj, form, change)

    admin_text.short_description = _(u"Text")


class MenuItemAdmin(BaseAdmin):
    """
        MenuItem admin
    """
    list_filter = (
        "menu",
        "language",
        )
    list_display = ("title", "language", "menu", "position", "url")


class StaticPageAdminForm(BaseAdminModelForm):
    class Meta:
        widgets = {
            'text': Wysiwyg(mode='full', width="800px")
        }


class StaticPageAdmin(BaseAdmin):
    """
        StaticPage admin
    """
    list_filter = ("language",)
    list_display = (
        "title",
        "slug",
        "last_changed",
        "language",
    )
    prepopulated_fields = {"slug": ("title",)}
    form = StaticPageAdminForm


class PostAdmin(BaseAdmin):
    '''
        Post admin
    '''
    list_display = ("thread", "author", "admin__node", "post_type", "added_at")
    readonly_fields = (
        "dt_created",
        "dt_changed",
        "parent",
        "thread",
        )
    list_filter = (
        "author__email",
        "post_type",
        "thread__node__title",
    )
    date_hierarchy = "added_at"

    def admin__node(self, obj):
        return obj.thread.node


class FollowedThreadAdmin(BaseAdmin):
    pass


class FollowedNodeAdmin(BaseAdmin):
    pass


class SubscribedThreadAdmin(BaseAdmin):
    pass


class SubscribedNodeAdmin(BaseAdmin):
    pass


class OrganizationAdminForm(BaseAdminModelForm):
    class Meta:
        fields = ('approved', 'title', 'long_title', 'logo', 'desc', 'openness', 'preapproved_emails', 'preapproved_email_domains',)

    desc = forms.CharField(widget=Wysiwyg(mode='simple', width='800px'), required=False, label=_('description'))

    def __init__(self, *args, **kwargs):
        super(OrganizationAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.description:
            self.fields['desc'].initial = self.instance.description.text


class OrganizationAdmin(BaseAdmin):
    form = OrganizationAdminForm

    # def queryset(self, request):
    #      return self.model.all_objects
    #
    def save_model(self, request, obj, form, change):
        super(OrganizationAdmin, self).save_model(request, obj, form, change)
        description = form.cleaned_data['desc']

        if obj.description:
            request.user.edit_post(obj.description, body_text=description)
        else:
            request.user.post_object_description(obj, body_text=description)


class OrganizationMembershipInline(admin.TabularInline):
    model = models.OrganizationMembership
    extra = 0


# Proxy user
class NodeProxyUserInline(admin.TabularInline):
    model = models.NodeUser


class ProxyUserAdminForm(BaseAdminModelForm):
    class Meta:
        fields = ('first_name', 'last_name', 'display_name', 'email', 'password_1', 'password_2', 'desc', 'is_active', 'is_staff', 'is_hidden', 'groups')
        model = models.ProxyUser

    desc = forms.CharField(widget=Wysiwyg(mode='simple'), required=False, label=capfirst(_('description')))
    password_1 = forms.CharField(widget=forms.PasswordInput, label=_('Password'), min_length=const.PASSWORD_MIN_LENGTH)
    password_2 = forms.CharField(widget=forms.PasswordInput, label=_('Password retyped'))

    def __init__(self, *args, **kwargs):
        super(ProxyUserAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.description:
            self.fields['desc'].initial = self.instance.description.text
        self.fields['email'].required = True
        self.fields['groups'].help_text = _('Don\'t forget to activate Staff status field.')
        self.fields['groups'].widget = FilteredSelectMultiple(self.fields['groups'].label, False, attrs=self.fields['groups'].widget.attrs, choices=self.fields['groups'].widget.choices)
        self.fields['password_1'].required = not bool(self.instance)
        self.fields['password_1'].widget = forms.PasswordInput()
        self.fields['password_2'].required = not bool(self.instance)

    def clean(self):
        cl_data = super(ProxyUserAdminForm, self).clean()

        email = cl_data.get('email')
        if email:
            if self.instance:
                qs = User.objects.exclude(pk=self.instance.pk)
            else:
                qs = User.objects.all()

            if qs.filter(email=email).exists():
                raise forms.ValidationError(_('Account with this email already exists.'))

        if cl_data.get('password_1') and cl_data.get('password_2'):
            if cl_data['password_1'] != cl_data['password_2']:
                raise forms.ValidationError(_('Passwords did not match'))
        return cl_data

    def save(self, commit=True):
        instance = super(ProxyUserAdminForm, self).save(commit=False)
        ''' set password '''
        cl_data = self.cleaned_data
        if cl_data.get('password_1') and cl_data['password_1'] != '':
            instance.set_password(cl_data['password_1'])

        ''' username is the same as email '''
        instance.username = cl_data['email']

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class ProxyUserAdmin(BaseAdmin):
    form = ProxyUserAdminForm

    search_fields = ('email', 'first_name', 'last_name', 'display_name')

    list_display = (
        'email', 'first_name', 'last_name', 'display_name', 'is_active',
         # 'email_isvalid',
        'is_staff', 'is_hidden', 'date_joined', 'last_login', 'last_seen'
    )

    list_filter = (
        'is_active',
        # 'email_isvalid',
        'is_staff'
    )

    inlines = [
        OrganizationMembershipInline,
        NodeProxyUserInline,
    ]

    def get_actions(self, request):
        return []

    def queryset(self, request):
        """
        Returns a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = User._default_manager.get_query_set()

        # TODO: this should be handled by some parameter to the ChangeList.
        ordering = self.ordering or ()  # otherwise we might try to *None, which is bad ;)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def save_model(self, request, obj, form, change):
        super(ProxyUserAdmin, self).save_model(request, obj, form, change)
        description = form.cleaned_data['desc']

        if obj.description:
            request.user.edit_post(obj.description, body_text=description)
        else:
            request.user.post_object_description(obj, body_text=description)


class ProxyUserManagerStatusAdmin(ProxyUserAdmin):
    def queryset(self, request):
        """
        Returns a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = models.ProxyUserManagerStatus._default_manager.get_query_set()

        # TODO: this should be handled by some parameter to the ChangeList.
        ordering = self.ordering or ()  # otherwise we might try to *None, which is bad ;)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

class ThreadAdmin(BaseAdmin):
    list_display = (
        'node', 'thread_type', 'title',
        'answer_count', 'view_count', 'followed_count',
        'added_at', 'last_activity_at',
        'closed', 'is_deleted',
    )
    list_display_links = ('title',)
    fields = (
        'node', 'thread_type', 'title', 'slug',
        'approved', 'external_access', 'category',
        'added_at',
        'last_activity_at', 'last_activity_by',
        'closed', 'closed_at', 'closed_by', 'close_reason',
        'is_deleted',
        "dt_created", "dt_changed",
    )

    readonly_fields = (
        'node', 'thread_type',
        'category',
        'added_at',
        'last_activity_at', 'last_activity_by',
        'closed_at', 'closed_by', 'close_reason',
        "dt_created", "dt_changed",
    )

    search_fields = (
        'title', 'node__title'
    )

    list_filter = (
        'thread_type',
        'closed',
        'is_deleted',
    )


#######################################

admin.site.register(models.StaticPage, StaticPageAdmin)
admin.site.register(models.MenuItem, MenuItemAdmin)
admin.site.register(models.Actuality, ActualityAdmin)
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Vote, VoteAdmin)
admin.site.register(models.FollowedThread, FollowedThreadAdmin)
admin.site.register(models.FollowedNode, FollowedNodeAdmin)
admin.site.register(models.SubscribedThread, SubscribedThreadAdmin)
admin.site.register(models.SubscribedNode, SubscribedNodeAdmin)
admin.site.register(models.PostRevision, PostRevisionAdmin)
admin.site.register(models.Activity, ActivityAdmin)
admin.site.register(models.Node, NodeAdmin)
admin.site.register(models.Post, PostAdmin)
admin.site.register(models.Organization, OrganizationAdmin)
admin.site.register(models.ProxyUser, ProxyUserAdmin)
admin.site.register(models.ProxyUserManagerStatus, ProxyUserManagerStatusAdmin)
admin.site.register(Thread, ThreadAdmin)
admin.site.register(models.ThreadView, BaseAdmin)
