# -*- coding: utf-8 -*-
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.forms.models import inlineformset_factory, modelform_factory
from django.shortcuts import get_object_or_404
from django.utils.datastructures import MergeDict
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from django.utils.datastructures import SortedDict

from openode import const
from openode.models import get_users_with_perm
from openode.models.node import Node, Post, FollowedNode, SubscribedNode, NodeUser
from openode.models.user import Activity, Organization
from openode.skins.loaders import render_into_skin, get_template
from openode.forms.node import NodeAnnotationEditForm, NodeSettingsForm, NodeUserForm, PerexesEditForm, \
    AskToCreateNodeForm
from openode.forms.organization import OrganizationForm

from openode.utils.http import render_forbidden
from openode.utils.notify_users import notify_about_requests


def node_detail(request, node_id, node_slug):
    """
    node detail
    """
    node = get_object_or_404(Node, pk=node_id)

    if node.slug != node_slug:
        return HttpResponseRedirect(node.get_absolute_url())

    if not request.user.has_openode_perm('node_read', node):
        if request.user.has_openode_perm('node_show', node):
            return node_ask_to_join(request, node_id, node_slug)
        else:
            return render_forbidden(request)

    available_modules = [m[0] for m in node.get_modules()]

    default_module = node.default_module
    if default_module in available_modules:
        return HttpResponseRedirect(reverse('node_module', kwargs={'node_id': node.pk, 'node_slug': node.slug, 'module': default_module}))
    else:
        # fallback to annotation
        return HttpResponseRedirect(reverse('node_module', kwargs={'node_id': node.pk, 'node_slug': node.slug, 'module': const.NODE_MODULE_ANNOTATION}))


@login_required
def node_annotation_edit(request, node_id, node_slug):
    """
    Node Annotation Edit
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_annotation_edit', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    if not request.user.has_openode_perm('node_edit_annotation', node):
        return render_forbidden(request)

    text = getattr(node.description, "text", u"")
    data = {"text": text} if text else None

    if request.method == "POST":
        data = MergeDict(request.POST, data)
        form = NodeAnnotationEditForm(data=data, node=node)
        if form.is_valid():
            text = form.cleaned_data["text"]

            # edit
            if node.description:
                node.description.apply_edit(
                    edited_by=request.user,
                    text=text
                )
            # create new one
            else:
                post = Post.objects.create_new(
                    thread=None,
                    author=request.user,
                    added_at=datetime.now(),
                    text=text,
                    post_type="node_description",
                )
                post.save()
                node.description = post

            node.save()

            request.user.message_set.create(message=_('Node annotation has been succesfully saved.'))
            return HttpResponseRedirect(reverse('node_annotation_edit', args=[node.pk, node.slug]))

    else:
        form = NodeAnnotationEditForm(data=data, node=node)

    template_data = {
        'node': node,
        'form': form,
        'page_class': 'node-edit',
    }

    return render_into_skin('node/annotation/edit.html', template_data, request)


@login_required
def node_settings(request, node_id, node_slug):
    """
    Node Settings
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_settings', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    if not (request.user.is_admin('openode.change_node') or request.user.has_openode_perm('node_settings', node)):
        return render_forbidden(request)

    NodeUserInlineFormSet = inlineformset_factory(Node, NodeUser, form=NodeUserForm, extra=1)
    node_users = NodeUser.objects.filter(node=node).order_by('role', 'user__last_name', 'user__first_name')

    if request.method == "POST":
        form = NodeSettingsForm(instance=node, data=request.POST)
        formset = NodeUserInlineFormSet(request.POST, instance=node, queryset=node_users)
        form_is_valid = form.is_valid()
        formset_is_valid = formset.is_valid()
        if form_is_valid and formset_is_valid:
            form.save(user=request.user)
            formset.save()
            request.user.message_set.create(message=_('Node settings has been succesfully saved.'))
            return HttpResponseRedirect(reverse('node_settings', args=[node.pk, node.slug]))

    else:
        form = NodeSettingsForm(instance=node)
        formset = NodeUserInlineFormSet(instance=node, queryset=node_users)

    user_emails_by_role = SortedDict()
    for node_user in node_users:
        user_emails_by_role.setdefault(node_user.get_role_display(), []).append(node_user.user.email)

    template_data = {
        'node': node,
        'form': form,
        'formset': formset,
        'user_emails_by_role': user_emails_by_role,
        'page_class': 'node-edit',
    }

    return render_into_skin('node/edit_settings.html', template_data, request)


@login_required
def node_follow(request, node_id, node_slug):
    """
    Node follow
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_follow', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    FollowedNode.objects.get_or_create(node=node, user=request.user)
    node.update_followed_count()

    data = simplejson.dumps({'success': True})
    request.user.log(node, const.LOG_ACTION_FOLLOW_NODE)
    return HttpResponse(data, mimetype="application/json")


@login_required
def node_unfollow(request, node_id, node_slug):
    """
    Node unfollow
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_unfollow', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    ret = {}
    if node.node_users.filter(role=const.NODE_USER_ROLE_MANAGER, user=request.user).exists():
        # user must follow managed nodes
        ret.update({'success': False})
    else:
        try:
            FollowedNode.objects.get(node=node, user=request.user).delete()
        except FollowedNode.DoesNotExist:
            pass
        node.update_followed_count()
        ret.update({'success': True})
        request.user.log(node, const.LOG_ACTION_UNFOLLOW_NODE)

    return HttpResponse(simplejson.dumps(ret), mimetype="application/json")


@login_required
def node_subscribe(request, node_id, node_slug):
    """
    Node subscribe
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_subscribe', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    sc, created = SubscribedNode.objects.get_or_create(node=node, user=request.user)

    data = simplejson.dumps({'success': True})
    return HttpResponse(data, mimetype="application/json")


@login_required
def node_unsubscribe(request, node_id, node_slug):
    """
    Node unsubscribe
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_unsubscribe', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))
    SubscribedNode.objects.filter(node=node, user=request.user).delete()

    data = simplejson.dumps({'success': True})
    return HttpResponse(data, mimetype="application/json")


def node_followers(request, node_id, node_slug):
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_followers', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))
    data = {
        'follows': node.node_following_users.order_by("-added_at"),
        'node': node
    }

    return render_into_skin('node/followers.html', data, request)


def node_perexes_edit(request, node_id, node_slug):

    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_perexes_edit', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    if not (request.user.is_admin('openode.change_node') or request.user.has_openode_perm('node_settings', node)):
        return render_forbidden(request)

    fields = (
        "perex_node_important",
        "perex_node",
    )
    for module_name, xx, xxx in node.get_modules():
        fields += (
            "perex_%s" % module_name,
            "perex_%s_important" % module_name
        )

    Form = modelform_factory(Node, form=PerexesEditForm, fields=fields)

    if request.method == "POST":
        form = Form(request.POST, instance=node)
        if form.is_valid():
            form.save()
            request.user.message_set.create(message=_('Node perexes has been succesfully saved.'))
    else:
        form = Form(instance=node)

    to_tmpl = {
        "form": form,
        "node": node,
        "modules": [m[0] for m in node.get_modules()]
    }
    return render_into_skin("node/edit_perexes.html", to_tmpl, request)


def node_ask_to_join(request, node_id, node_slug):
    """
        ask to join (create/cancel) node view
    """
    node = get_object_or_404(Node, pk=node_id)
    if node.slug != node_slug:
        return HttpResponseRedirect(reverse('node_ask_to_join', kwargs={
            'node_id': node_id,
            'node_slug': node.slug
        }))

    action = request.GET.get('request')

    if not request.user.is_anonymous() and node.node_users.filter(user=request.user).exists():
        return HttpResponseRedirect(node.get_absolute_url())

    join_request = None

    if request.user.is_authenticated():
        node_content_type = ContentType.objects.get_for_model(Node)
        if action == 'join':
            join_request, created = Activity.objects.get_or_create(
                object_id=node.pk,
                content_type=node_content_type,
                user=request.user,
                activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE
            )
            request.user.log(node, const.LOG_ACTION_ASK_TO_JOIN_NODE)
        elif action == 'cancel':
            try:
                join_request = Activity.objects.get(
                    object_id=node.pk,
                    content_type=node_content_type,
                    user=request.user,
                    activity_type=const.TYPE_ACTIVITY_ASK_TO_JOIN_NODE
                )
                join_request.delete()
            except Activity.DoesNotExist:
                pass
            finally:
                join_request = None

    to_tmpl = {
        'node': node,
        'join_request': join_request
    }
    return render_into_skin("node/ask_to_join.html", to_tmpl, request)


@login_required()
def node_ask_to_create(request):
    """
        ask to create node

        There is no cancel option as user may create more than one request
        and there is no way to tell what request he wants to cancel.

    """
    sent = False   # was form successful, sent and without errors?

    if request.POST:
        form = AskToCreateNodeForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            note = form.cleaned_data['note']
            summary = ugettext_noop(u'''%(user)s wants to create a new node %(node_name)s.
                Here is a note regarding the request:  %(note)s''') % {
                'user': request.user,
                'node_name': name,
                'note': note
            }

            data = simplejson.dumps({
                'user_name': request.user.screen_name,
                'user_email': request.user.email,
                'node_name': name,
                'note': note
            })

            # ugettext_noop(summary)  # this will translate it after its pulled from db, not before.

            create_request, created = Activity.objects.get_or_create(
                    user=request.user,
                    activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_NODE,
                    # summary=summary,
                    data=data
                )
            request.user.log(create_request, const.LOG_ACTION_ASK_TO_CREATE_NODE)
            sent = True
    else:
        form = AskToCreateNodeForm()

    to_tmpl = {
        'sent': sent,
        'form': form,
    }

    return render_into_skin("node/ask_to_create.html", to_tmpl, request)


@login_required()
def ask_to_create_org(request):
    """
        ask to create organization
    """
    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            org = form.save(request)

            summary = _(u'''%(user)s wants to create a new organization %(organization_name)s.
            Description of the organization:  %(description)s''') % {'user': request.user, 'organization_name': org.title, 'description': org.description.summary}

            # send mail:
            users_to_notify = get_users_with_perm('add_organization')
            subject = _(u'''%(user)s wants to create a new organization %(organization_name)s''') % {'user': request.user, 'organization_name': org.title}

            notify_about_requests(users_to_notify, subject, summary)

            org_request, created = Activity.objects.get_or_create(
                object_id=org.pk,
                content_type=ContentType.objects.get_for_model(Organization),
                user=request.user,
                activity_type=const.TYPE_ACTIVITY_ASK_TO_CREATE_ORG,
                summary=summary,
            )

            request.user.log(org, const.LOG_ACTION_ASK_TO_CREATE_ORG)
    else:
        form = OrganizationForm()

    to_tmpl = {
        'form': form,
    }

    return render_into_skin("ask_to_create_organization.html", to_tmpl, request)


@login_required
def mark_read(request, node=None, followed=None):

    from openode.models.thread import Thread
    user = request.user

    threads = []

    if node:
        if node.isdigit():
            threads = Thread.objects.filter(node__id=node)
        elif node == "all":
            threads = Thread.objects.all()

    elif followed:
        if followed in [const.THREAD_TYPE_DISCUSSION, const.THREAD_TYPE_QUESTION]:
            threads = [ft.thread for ft in user.user_followed_threads.filter(thread__thread_type=followed)]
        elif followed == "node":
            threads = Thread.objects.filter(node__id__in=user.user_followed_nodes.values_list("node_id"))

    else:
        raise Http404

    for thread in threads:
        if thread.has_unread_posts_for_user(user) or thread.has_unread_main_post_for_user(user):
            thread.visit(user)

    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse("index")))
