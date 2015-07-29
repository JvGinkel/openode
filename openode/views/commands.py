"""
:synopsis: most ajax processors for openode

This module contains most (but not all) processors for Ajax requests.
Not so clear if this subdivision was necessary as separation of Ajax and non-ajax views
is not always very clean.
"""
import datetime
from bs4 import BeautifulSoup

from django.core import exceptions
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    )
from django.forms import IntegerField, CharField
from django.shortcuts import get_object_or_404
from django.template import Context
from django.utils import simplejson
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.views.decorators import csrf

from openode import const, forms, mail, models
from openode.conf import settings as openode_settings
from openode.skins.loaders import (
    get_template,
    render_into_skin,
    render_into_skin_as_string,
    render_text_into_skin
    )
from openode.utils import decorators, url_utils
from openode.models.thread import Thread
from openode.utils.http import render_forbidden
from openode.utils.slug import slugify
from openode.utils.forms import get_db_object_or_404


@csrf.csrf_exempt
def manage_inbox(request):
    """delete, mark as new or seen user's
    response memo objects, excluding flags
    request data is memo_list  - list of integer id's of the ActivityAuditStatus items
    and action_type - string - one of delete|mark_new|mark_seen
    """

    response_data = dict()
    try:
        if request.is_ajax():
            if request.method == 'POST':
                post_data = simplejson.loads(request.raw_post_data)
                if request.user.is_authenticated():
                    activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
                    activity_types += (
                        const.TYPE_ACTIVITY_MENTION,
                        const.TYPE_ACTIVITY_MARK_OFFENSIVE,
                    )
                    user = request.user
                    memo_set = models.ActivityAuditStatus.objects.filter(
                        id__in=post_data['memo_list'],
                        activity__activity_type__in=activity_types,
                        user=user
                    )

                    action_type = post_data['action_type']
                    if action_type == 'delete':
                        memo_set.delete()
                    elif action_type == 'mark_new':
                        memo_set.update(status=models.ActivityAuditStatus.STATUS_NEW)
                    elif action_type == 'mark_seen':
                        memo_set.update(status=models.ActivityAuditStatus.STATUS_SEEN)
                    elif action_type == 'remove_flag':
                        for memo in memo_set:
                            activity_type = memo.activity.activity_type
                            if activity_type == const.TYPE_ACTIVITY_MARK_OFFENSIVE:
                                request.user.flag_post(
                                    post=memo.activity.content_object,
                                    cancel_all=True
                                )

                    #elif action_type == 'close':
                    #    for memo in memo_set:
                    #        if memo.activity.content_object.post_type == "question":
                    #            request.user.close_question(question = memo.activity.content_object, reason = 7)
                    #            memo.delete()
                    elif action_type == 'delete_post':
                        for memo in memo_set:
                            content_object = memo.activity.content_object
                            if isinstance(content_object, models.PostRevision):
                                post = content_object.post
                            else:
                                post = content_object
                            request.user.delete_post(post)
                            reject_reason = models.PostFlagReason.objects.get(
                                                    id=post_data['reject_reason_id']
                                                )
                            template = get_template('email/rejected_post.html')
                            data = {
                                    'post': post.html,
                                    'reject_reason': reject_reason.details.html
                                   }
                            body_text = template.render(Context(data))
                            mail.send_mail(
                                subject_line=_('your post was not accepted'),
                                body_text=unicode(body_text),
                                recipient_list=[post.author.email, ]
                            )
                            memo.delete()

                    user.update_response_counts()

                    response_data['success'] = True
                    data = simplejson.dumps(response_data)
                    return HttpResponse(data, mimetype="application/json")
                else:
                    raise exceptions.PermissionDenied(
                        _('Sorry, but anonymous users cannot access the inbox')
                    )
            else:
                raise exceptions.PermissionDenied('must use POST request')
        else:
            #todo: show error page but no-one is likely to get here
            return HttpResponseRedirect(reverse('index'))
    except Exception, e:
        message = unicode(e)
        if message == '':
            message = _('Oops, apologies - there was some error')
        response_data['message'] = message
        response_data['success'] = False
        data = simplejson.dumps(response_data)
        return HttpResponse(data, mimetype="application/json")


def process_vote(user=None, vote_direction=None, post=None):
    """function (non-view) that actually processes user votes
    - i.e. up- or down- votes

    in the future this needs to be converted into a real view function
    for that url and javascript will need to be adjusted

    also in the future make keys in response data be more meaningful
    right now they are kind of cryptic - "status", "count"
    """

    if post.thread is None:
        raise exceptions.PermissionDenied(
            _("You can't vote for this post.")
        )

    if not user.has_openode_perm('question_answer_vote', post.thread):
        raise exceptions.PermissionDenied(
            _('Sorry, but you don\'t have permission to vote.')
            # _('Sorry, anonymous users cannot vote')
        )

    user.assert_can_vote_for_post(post=post, direction=vote_direction)
    vote = user.get_old_vote_for_post(post)
    response_data = {}
    if vote != None:
        user.assert_can_revoke_old_vote(vote)
        score_delta = vote.cancel()
        response_data['count'] = post.points + score_delta
        response_data['status'] = 1  # this means "cancel"
    else:
        #this is a new vote
        votes_left = user.get_unused_votes_today()
        if votes_left <= 0:
            raise exceptions.PermissionDenied(
                            _('Sorry you ran out of votes for today')
                        )

        votes_left -= 1
        if votes_left <= \
            openode_settings.VOTES_LEFT_WARNING_THRESHOLD:
            msg = _('You have %(votes_left)s votes left for today') \
                    % {'votes_left': votes_left}
            response_data['message'] = msg

        if vote_direction == 'up':
            vote = user.upvote(post=post)
        else:
            vote = user.downvote(post=post)

        response_data['count'] = post.points
        response_data['status'] = 0  # this means "not cancel", normal operation

    response_data['success'] = 1

    return response_data


@csrf.csrf_exempt
def vote(request, thread_id):
    """
    todo: this subroutine needs serious refactoring it's too long and is hard to understand

    vote_type:
        acceptAnswer : 0,
        questionUpVote : 1,
        questionDownVote : 2,
        followed : 4,
        answerUpVote: 5,
        answerDownVote:6,
        offensiveQuestion : 7,
        remove offensiveQuestion flag : 7.5,
        remove all offensiveQuestion flag : 7.6,
        offensiveAnswer:8,
        remove offensiveAnswer flag : 8.5,
        remove all offensiveAnswer flag : 8.6,
        removeQuestion: 9,
        removeAnswer:10
        questionSubscribeUpdates:11
        questionUnSubscribeUpdates:12

    accept answer code:
        response_data['allowed'] = -1, Accept his own answer   0, no allowed - Anonymous    1, Allowed - by default
        response_data['success'] =  0, failed                                               1, Success - by default
        response_data['status']  =  0, By default                       1, Answer has been accepted already(Cancel)

    vote code:
        allowed = -3, Don't have enough votes left
                  -1, Vote his own post
                   0, no allowed - Anonymous
                   1, Allowed - by default
        status  =  0, By default
                   1, Cancel
                   2, Vote is too old to be canceled

    offensive code:
        allowed = -3, Don't have enough flags left
                   0, not allowed
                   1, allowed
        status  =  0, by default
                   1, can't do it again
    """

    response_data = {
        "allowed": 1,
        "success": 1,
        "status": 0,
        "count": 0,
        "message": ''
    }

    try:
        if request.is_ajax() and request.method == 'POST':
            vote_type = request.POST.get('type')
        else:
            raise Exception(_('Sorry, something is not right here...'))

        if vote_type == '0':

            answer_id = request.POST.get('postId')
            answer = get_object_or_404(models.Post, post_type='answer', id=answer_id)

            if request.user.is_authenticated():

                if answer.accepted():
                    request.user.unaccept_best_answer(answer)
                    response_data['status'] = 1  # cancelation

                    # Unpublish question flow answer
                    if answer.thread.node.is_question_flow_enabled:
                        if request.user.has_perm('can_solve_question_flow'):
                            answer.thread.question_flow_state = const.QUESTION_FLOW_STATE_ANSWERED
                            answer.thread.save()
                        else:
                            response_data['success'] = 0
                            response_data['message'] = _(u"You are not permitted to select best answer.")

                else:
                    request.user.accept_best_answer(answer)

                    # Publish answer in question flow
                    if answer.thread.node.is_question_flow_enabled:
                        if request.user.has_perm('can_solve_question_flow'):
                            answer.thread.question_flow_state = const.QUESTION_FLOW_STATE_PUBLISHED
                            answer.thread.question_flow_interviewee_user = None
                            answer.thread.save()
                        else:
                            response_data['success'] = 0
                            response_data['message'] = _(u"You are not permitted to select best answer.")

            else:
                response_data['success'] = 0
                response_data['message'] = _(u"Anonymous user can't vote for best answer.")

            ####################################################################
            answer.thread.update_summary_html()  # regenerate question/thread summary html
            ####################################################################

        elif vote_type in ('1', '2', '5', '6'):  # Q&A up/down votes

            ###############################
            # all this can be avoided with
            # better query parameters
            vote_direction = 'up'
            if vote_type in ('2', '6'):
                vote_direction = 'down'

            if vote_type in ('5', '6'):
                #todo: fix this weirdness - why postId here
                #and not with question?
                id = request.POST.get('postId')
                post = get_object_or_404(models.Post, post_type='answer', id=id)
            else:
                thread = get_object_or_404(models.Thread, id=thread_id)
                post = thread._main_post()
            #
            ######################

            response_data = process_vote(
                user=request.user,
                vote_direction=vote_direction,
                post=post
            )

            ####################################################################
            if vote_type in ('1', '2'):  # up/down-vote question
                post.thread.update_summary_html()  # regenerate question/thread summary html
            ####################################################################

        elif vote_type in ['7', '8']:
            #flag question or answer
            if vote_type == '7':
                thread = get_object_or_404(models.Thread, id=thread_id)
                post = thread._main_post()
            if vote_type == '8':
                id = request.POST.get('postId')
                post = get_object_or_404(models.Post, post_type='answer', id=id)

            request.user.flag_post(post)
            response_data['count'] = post.offensive_flag_count
            response_data['success'] = 1

        elif vote_type in ['7.5', '8.5']:
            #flag question or answer
            if vote_type == '7.5':
                thread = get_object_or_404(models.Thread, id=thread_id)
                post = thread._main_post()
            if vote_type == '8.5':
                id = request.POST.get('postId')
                post = get_object_or_404(models.Post, post_type='answer', id=id)

            request.user.flag_post(post, cancel=True)

            response_data['count'] = post.offensive_flag_count
            response_data['success'] = 1

        elif vote_type in ['7.6', '8.6']:
            #flag question or answer
            if vote_type == '7.6':
                thread = get_object_or_404(models.Thread, id=thread_id)
                post = thread._main_post()
            if vote_type == '8.6':
                id = request.POST.get('postId')
                post = get_object_or_404(models.Post, id=id)

            request.user.flag_post(post, cancel_all=True)

            response_data['count'] = post.offensive_flag_count
            response_data['success'] = 1

        elif vote_type in ['9', '10']:
            #delete question or answer
            thread = get_object_or_404(models.Thread, id=thread_id)
            post = thread._main_post()
            if vote_type == '10':
                id = request.POST.get('postId')
                post = get_object_or_404(models.Post, post_type='answer', id=id)

            if post.deleted == True:
                request.user.restore_post(post=post)
            else:
                request.user.delete_post(post=post)

        elif request.is_ajax() and request.method == 'POST':

            if not request.user.is_authenticated():
                response_data['allowed'] = 0
                response_data['success'] = 0

            thread = get_object_or_404(models.Thread, id=thread_id)
            vote_type = request.POST.get('type')

            #follow answer
            if vote_type == '4':
                fave = request.user.toggle_followed_thread(thread)
                response_data['count'] = models.FollowedThread.objects.filter(thread=thread).count()
                if fave == False:
                    response_data['status'] = 1

            # subscribe for thread updates
            elif vote_type == '11':
                user = request.user
                if user.is_authenticated():
                    if user not in thread.subscribed_by.all():
                        user.subscribe_thread(thread)
                        if openode_settings.EMAIL_VALIDATION == True \
                            and user.email_isvalid == False:

                            response_data['message'] = \
                                    _(
                                        'Your subscription is saved, but email address '
                                        '%(email)s needs to be validated, please see '
                                        '<a href="%(details_url)s">more details here</a>'
                                    ) % {'email': user.email, 'details_url': reverse('faq') + '#validate'}

                    subscribed = user.subscribe_for_followed_question_alerts()
                    if subscribed:
                        if 'message' in response_data:
                            response_data['message'] += '<br/>'
                        response_data['message'] += _('email update frequency has been set to daily')
                    #response_data['status'] = 1
                    #responst_data['allowed'] = 1
                else:
                    pass
                    #response_data['status'] = 0
                    #response_data['allowed'] = 0

            # unsubscribe from thread updates
            elif vote_type == '12':
                user = request.user
                if user.is_authenticated():
                    user.unsubscribe_thread(thread)
        else:
            response_data['success'] = 0
            response_data['message'] = u'Request mode is not supported. Please try again.'

        if vote_type not in (1, 2, 4, 5, 6, 11, 12):
            #followed or subscribe/unsubscribe
            #upvote or downvote question or answer - those
            #are handled within user.upvote and user.downvote
            thread = models.Thread.objects.get(id=thread_id)
            thread.invalidate_cached_data()

        data = simplejson.dumps(response_data)

    except Exception, e:
        response_data['message'] = unicode(e)
        response_data['success'] = 0
        data = simplejson.dumps(response_data)
    return HttpResponse(data, mimetype="application/json")


#internally organizationed views - used by the tagging system
@csrf.csrf_exempt
@decorators.post_only
@decorators.ajax_login_required
def mark_tag(request, **kwargs):  # tagging system
    action = kwargs['action']
    post_data = simplejson.loads(request.raw_post_data)
    raw_tagnames = post_data['tagnames']
    reason = post_data['reason']
    assert reason in ('good', 'bad', 'subscribed')
    #separate plain tag names and wildcard tags

    tagnames, wildcards = forms.clean_marked_tagnames(raw_tagnames)
    cleaned_tagnames, cleaned_wildcards = request.user.mark_tags(
                                                            tagnames,
                                                            wildcards,
                                                            reason=reason,
                                                            action=action
                                                        )

    #lastly - calculate tag usage counts
    tag_usage_counts = dict()
    for name in tagnames:
        if name in cleaned_tagnames:
            tag_usage_counts[name] = 1
        else:
            tag_usage_counts[name] = 0

    for name in wildcards:
        if name in cleaned_wildcards:
            tag_usage_counts[name] = models.Tag.objects.filter(
                                        name__startswith=name[:-1]
                                    ).count()
        else:
            tag_usage_counts[name] = 0

    return HttpResponse(simplejson.dumps(tag_usage_counts), mimetype="application/json")


#@decorators.ajax_only
@decorators.get_only
def get_tags_by_wildcard(request):
    """returns an json encoded array of tag names
    in the response to a wildcard tag name
    """
    wildcard = request.GET.get('wildcard', None)
    if wildcard is None:
        raise Http404

    matching_tags = models.Tag.objects.get_by_wildcards([wildcard, ])
    count = matching_tags.count()
    names = matching_tags.values_list('name', flat=True)[:20]
    re_data = simplejson.dumps({'tag_count': count, 'tag_names': list(names)})
    return HttpResponse(re_data, mimetype='application/json')


@decorators.get_only
def get_thread_shared_users(request):
    """returns snippet of html with users"""
    thread_id = request.GET['thread_id']
    thread_id = IntegerField().clean(thread_id)
    thread = models.Thread.objects.get(id=thread_id)
    users = thread.get_users_shared_with()
    data = {
        'users': users,
    }
    html = render_into_skin_as_string('widgets/user_list.html', data, request)
    re_data = simplejson.dumps({
        'html': html,
        'users_count': users.count(),
        'success': True
    })
    return HttpResponse(re_data, mimetype='application/json')


@decorators.ajax_only
def get_html_template(request):
    """returns rendered template"""
    template_name = request.REQUEST.get('template_name', None)
    allowed_templates = (
        'widgets/tag_category_selector.html',
    )
    #have allow simple context for the templates
    if template_name not in allowed_templates:
        raise Http404
    return {
        'html': get_template(template_name).render()
    }


@decorators.get_only
def get_tag_list(request):
    """returns tags to use in the autocomplete
    function
    """
    tags = models.Tag.objects.filter(
                        deleted=False,
                        status=models.Tag.STATUS_ACCEPTED
                    )

    tag_names = tags.values_list(
                        'name', flat=True
                    )

    output = '\n'.join(map(escape, tag_names))
    return HttpResponse(output, mimetype='text/plain')


@decorators.get_only
def load_object_description(request):
    """returns text of the object description in text"""
    obj = get_db_object_or_404(request.GET)  # openode forms utility
    text = getattr(obj.description, 'text', '').strip()
    return HttpResponse(text, mimetype='text/plain')


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def save_object_description(request):
    """if object description does not exist,
    creates a new record, otherwise edits an existing
    one"""
    obj = get_db_object_or_404(request.POST)
    text = request.POST['text']
    if obj.description:
        request.user.edit_post(obj.description, body_text=text)
    else:
        request.user.post_object_description(obj, body_text=text)
    return {'html': obj.description.html}


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def rename_tag(request):
    # DEPRECATED ???
    # TODO: use Thread.can_retag method
    if not request.user.has_perm('openode.change_tag'):
        raise exceptions.PermissionDenied()
    post_data = simplejson.loads(request.raw_post_data)
    to_name = forms.clean_tag(post_data['to_name'])
    from_name = forms.clean_tag(post_data['from_name'])
    path = post_data['path']

    #kwargs = {'from': old_name, 'to': new_name}
    #call_command('rename_tags', **kwargs)

    tree = category_tree.get_data()
    category_tree.rename_category(
        tree,
        from_name=from_name,
        to_name=to_name,
        path=path
    )
    category_tree.save_data(tree)


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def delete_tag(request):
    """todo: actually delete tags
    now it is only deletion of category from the tree"""
    if request.user.is_anonymous() \
        or not request.user.is_admin('openode.delete_tag'):
        raise exceptions.PermissionDenied()
    post_data = simplejson.loads(request.raw_post_data)
    tag_name = forms.clean_tag(post_data['tag_name'])
    path = post_data['path']
    tree = category_tree.get_data()
    category_tree.delete_category(tree, tag_name, path)
    category_tree.save_data(tree)
    return {'tree_data': tree}


# DEPRECATED - to delete
@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def add_tag_category(request):
    """adds a category at the tip of a given path expects
    the following keys in the ``request.POST``
    * path - array starting with zero giving path to
      the category page where to add the category
    * new_category_name - string that must satisfy the
      same requiremets as a tag

    return json with the category tree data
    todo: switch to json stored in the live settings
    now we have indented input
    """
    if request.user.is_anonymous() \
        or not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()

    post_data = simplejson.loads(request.raw_post_data)
    category_name = forms.clean_tag(post_data['new_category_name'])
    path = post_data['path']

    tree = category_tree.get_data()

    if category_tree.path_is_valid(tree, path) == False:
        raise ValueError('category insertion path is invalid')

    new_path = category_tree.add_category(tree, category_name, path)
    category_tree.save_data(tree)
    return {
        'tree_data': tree,
        'new_path': new_path
    }


@csrf.csrf_protect
def subscribe_for_tags(request):
    """process subscription of users by tags"""
    #todo - use special separator to split tags
    tag_names = request.REQUEST.get('tags', '').strip().split()
    pure_tag_names, wildcards = forms.clean_marked_tagnames(tag_names)
    if request.user.is_authenticated():
        if request.method == 'POST':
            if 'ok' in request.POST:
                request.user.mark_tags(
                            pure_tag_names,
                            wildcards,
                            reason='good',
                            action='add'
                        )
                request.user.message_set.create(
                    message=_('Your tag subscription was saved, thanks!')
                )
            else:
                message = _(
                    'Tag subscription was canceled (<a href="%(url)s">undo</a>).'
                ) % {'url': request.path + '?tags=' + request.REQUEST['tags']}
                request.user.message_set.create(message=message)
            return HttpResponseRedirect(reverse('index'))
        else:
            data = {'tags': tag_names}
            return render_into_skin('subscribe_for_tags.html', data, request)
    else:
        all_tag_names = pure_tag_names + wildcards
        message = _('Please sign in to subscribe for: %(tags)s') \
                    % {'tags': ', '.join(all_tag_names)}
        request.user.message_set.create(message=message)
        request.session['subscribe_for_tags'] = (pure_tag_names, wildcards)
        return HttpResponseRedirect(url_utils.get_login_url())


@decorators.get_only
def api_get_questions(request):
    """json api for retrieving questions"""
    query = request.GET.get('query', '').strip()
    if not query:
        return HttpResponseBadRequest('Invalid query')

    threads = models.Thread.objects.get_visible(user=request.user)
    # else:
    #     threads = models.Thread.objects.all()

    threads = models.Thread.objects.get_for_query(
                                    search_query=query,
                                    qs=threads
                                )

    #todo: filter out deleted threads, for now there is no way
    threads = threads.distinct()[:30]
    thread_list = [{
        'title': escape(thread.title),
        'url': thread.get_absolute_url(),
        'answer_count': thread.get_answer_count(request.user)
    } for thread in threads]
    json_data = simplejson.dumps(thread_list)
    return HttpResponse(json_data, mimetype="application/json")


@csrf.csrf_exempt
@decorators.post_only
@decorators.ajax_login_required
def set_tag_filter_strategy(request):
    """saves data in the ``User.[email/display]_tag_filter_strategy``
    for the current user
    """
    filter_type = request.POST['filter_type']
    filter_value = int(request.POST['filter_value'])
    assert(filter_type in ('display', 'email'))
    if filter_type == 'display':
        assert(filter_value in dict(const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES))
        request.user.display_tag_filter_strategy = filter_value
    else:
        assert(filter_value in dict(const.TAG_EMAIL_FILTER_STRATEGY_CHOICES))
        request.user.email_tag_filter_strategy = filter_value
    request.user.save()
    return HttpResponse('', mimetype="application/json")


@login_required
@csrf.csrf_protect
def close(request, thread_id):  # close thread
    """view to initiate and process
    thread close
    """
    thread = get_object_or_404(models.Thread, id=thread_id)
    form = forms.CloseForm(request.POST or None)

    if not request.user.has_openode_perm('%s_close' % thread.thread_type, thread.node):
        return render_forbidden(request)

    try:
        if request.method == 'POST':
            if form.is_valid():
                request.user.close_thread(
                    thread=thread,
                    reason=form.cleaned_data['reason']
                    )
                return HttpResponseRedirect(thread.get_absolute_url())
        else:
            request.user.assert_can_close_thread(thread)
        data = {
            'thread': thread,
            'form': form,
        }
        return render_into_skin('thread_close.html', data, request)
    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message=unicode(e))
        return HttpResponseRedirect(thread.get_absolute_url())


@login_required
@csrf.csrf_protect
def reopen(request, thread_id):  # re-open thread
    """view to initiate and process
    thread reopen

    this is not an ajax view
    """

    thread = get_object_or_404(models.Thread, id=thread_id)

    if not request.user.has_openode_perm('%s_close' % thread.thread_type, thread.node):
        return render_forbidden(request)

    # open thread
    try:
        if request.method == 'POST':
            request.user.reopen_thread(thread)
            return HttpResponseRedirect(thread.get_absolute_url())
        else:
            request.user.assert_can_reopen_thread(thread)
            closed_by_profile_url = thread.closed_by.get_profile_url()
            data = {
                'thread': thread,
                'closed_by_profile_url': closed_by_profile_url,
            }
            return render_into_skin('thread_reopen.html', data, request)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message=unicode(e))
        return HttpResponseRedirect(thread.get_absolute_url())


#DEPRECATED - to delete
@csrf.csrf_exempt
@decorators.ajax_only
def swap_question_with_answer(request):
    """receives two json parameters - answer id
    and new question title
    the view is made to be used only by the site administrator
    or moderators
    """
    if request.user.is_authenticated():
        if request.user.is_administrator() or request.user.is_moderator():
            answer = models.Post.objects.get_answers(request.user).get(id=request.POST['answer_id'])
            new_question = answer.swap_with_question(new_title=request.POST['new_title'])
            return {
                'id': new_question.id,
                'slug': new_question.slug
            }
    raise Http404


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def upvote_comment(request):
    if request.user.is_anonymous():
        raise exceptions.PermissionDenied(_('Please sign in to vote'))
    form = forms.VoteForm(request.POST)
    if form.is_valid():
        comment_id = form.cleaned_data['post_id']
        # cancel_vote = form.cleaned_data['cancel_vote']
        comment = get_object_or_404(models.Post, post_type='comment', id=comment_id)
        process_vote(
            post=comment,
            vote_direction='up',
            user=request.user
        )
    else:
        raise ValueError
    #FIXME: rename js
    return {'score': comment.points}


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def delete_post(request):

    if request.user.is_anonymous():
        raise exceptions.PermissionDenied(_('Please sign in to delete/restore posts'))

    form = forms.VoteForm(request.POST)

    if form.is_valid():
        post = get_object_or_404(
            models.Post,
            post_type__in=('question', 'answer', 'discussion', "document"),
            pk=form.cleaned_data['post_id']
        )

        if not post.has_delete_perm(request.user):
            raise exceptions.PermissionDenied(
                _('Sorry, but you don\'t have permission to accept answer.')
            )

        if form.cleaned_data['cancel_vote']:
            request.user.restore_post(post)
        else:
            request.user.delete_post(post)

            if post.is_answer():
                request.user.log(post, const.LOG_ACTION_DELETE_ANSWER)
    else:
        raise ValueError

    return {'is_deleted': post.deleted}


def delete_thread(request, thread_id):

    # if request.user.is_anonymous():
    #     raise exceptions.PermissionDenied(_('Please sign in to delete/restore posts'))

    try:
        thread = Thread.objects.get(pk=thread_id)
    except Thread.DoesNotExist:
        raise Http404
    else:
        if not thread.has_delete_perm(request.user):
            return render_forbidden(request)
        thread.delete(soft=True)

        if thread.is_question():
            request.user.log(thread, const.LOG_ACTION_CLOSE_QUESTION)

        request.user.message_set.create(message=_('Thread has been succesfully deleted.'))

    return HttpResponseRedirect(
        thread.node.get_absolute_url(
            module=const.NODE_MODULE_BY_THREAD_TYPE[thread.thread_type]
        )
    )


#openode-user communication system
@csrf.csrf_exempt
def read_message(request):  # marks message a read
    if request.method == "POST":
        if request.POST['formdata'] == 'required':
            request.session['message_silent'] = 1
            if request.user.is_authenticated():
                request.user.delete_messages()
    return HttpResponse('')


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def edit_organization_membership(request):
    #todo: this call may need to go.
    #it used to be the one creating organizations
    #from the user profile page
    #we have a separate method
    form = forms.EditOrganizationMembershipForm(request.POST)
    if form.is_valid():
        organization_name = form.cleaned_data['organization_name']
        user_id = form.cleaned_data['user_id']
        try:
            user = models.User.objects.get(id=user_id)
        except models.User.DoesNotExist:
            raise exceptions.PermissionDenied(
                'user with id %d not found' % user_id
            )

        action = form.cleaned_data['action']
        #warning: possible race condition
        if action == 'add':
            organization_params = {'name': organization_name, 'user': user}
            organization = models.Organization.objects.get_or_create(**organization_params)
            request.user.edit_organization_membership(user, organization, 'add')
            template = get_template('widgets/organization_snippet.html')
            return {
                'name': organization.title,
                'description': getattr(organization.organization_description, 'text', ''),
                'html': template.render({'organization': organization})
            }
        elif action == 'remove':
            try:
                organization = models.Organization.objects.get(organization_name=organization_name)
                request.user.edit_organization_membership(user, organization, 'remove')
            except models.Organization.DoesNotExist:
                raise exceptions.PermissionDenied()
        else:
            raise exceptions.PermissionDenied()
    else:
        raise exceptions.PermissionDenied()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def save_organization_logo_url(request):
    """saves urls for the organization logo"""
    form = forms.OrganizationLogoURLForm(request.POST)
    if form.is_valid():
        organization_id = form.cleaned_data['organization_id']
        image_url = form.cleaned_data['image_url']
        organization = models.Organization.objects.get(id=organization_id)
        organization.logo_url = image_url
        organization.save()
    else:
        raise ValueError('invalid data found when saving organization logo')


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def add_organization(request):
    organization_name = request.POST.get('organization')
    if organization_name:
        organization, created = models.Organization.objects.get_or_create(
                            name=organization_name,
                            openness=models.Organization.OPEN
                        )
        url = reverse('organization_detail', kwargs={'organization_id': organization.id,
                   'organization_slug': slugify(organization_name)})
        response_dict = dict(organization_name=organization_name,
                             url=url)
        return response_dict


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def delete_organization_logo(request):
    organization_id = IntegerField().clean(int(request.POST['organization_id']))
    organization = models.Organization.objects.get(id=organization_id)
    organization.logo_url = None
    organization.save()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def delete_post_reject_reason(request):
    reason_id = IntegerField().clean(int(request.POST['reason_id']))
    reason = models.PostFlagReason.objects.get(id=reason_id)
    reason.delete()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def set_organization_openness(request):
    organization_id = IntegerField().clean(int(request.POST['organization_id']))
    value = IntegerField().clean(int(request.POST['value']))
    organization = models.Organization.objects.get(id=organization_id)
    organization.openness = value
    organization.save()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.admins_only
def edit_object_property_text(request):
    model_name = CharField().clean(request.REQUEST['model_name'])
    object_id = IntegerField().clean(request.REQUEST['object_id'])
    property_name = CharField().clean(request.REQUEST['property_name'])

    accessible_fields = (
        ('Organization', 'preapproved_emails'),
        ('Organization', 'preapproved_email_domains')
    )

    if (model_name, property_name) not in accessible_fields:
        raise exceptions.PermissionDenied()

    obj = models.get_model(model_name).objects.get(id=object_id)
    if request.method == 'POST':
        text = CharField().clean(request.POST['text'])
        setattr(obj, property_name, text)
        obj.save()
    elif request.method == 'GET':
        return {'text': getattr(obj, property_name)}
    else:
        raise exceptions.PermissionDenied()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def join_or_leave_organization(request):
    """called when user wants to join/leave
    ask to join/cancel join request, depending
    on the organizations acceptance level for the given user

    returns resulting "membership_level"
    """
    if request.user.is_anonymous():
        raise exceptions.PermissionDenied()

    Organization = models.Organization
    Membership = models.OrganizationMembership

    organization_id = IntegerField().clean(request.POST['organization_id'])
    organization = Organization.objects.get(id=organization_id)

    membership = request.user.get_organization_membership(organization)
    if membership is None:
        membership = request.user.join_organization(organization)
        new_level = membership.get_level_display()
    else:
        membership.delete()
        new_level = Membership.get_level_value_display(Membership.NONE)

    return {'membership_level': new_level}


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def save_post_reject_reason(request):
    """saves post reject reason and returns the reason id
    if reason_id is not given in the input - a new reason is created,
    otherwise a reason with the given id is edited and saved
    """
    form = forms.EditRejectReasonForm(request.POST)
    if form.is_valid():
        title = form.cleaned_data['title']
        details = form.cleaned_data['details']
        if form.cleaned_data['reason_id'] is None:
            reason = request.user.create_post_reject_reason(
                title=title, details=details
            )
        else:
            reason_id = form.cleaned_data['reason_id']
            reason = models.PostFlagReason.objects.get(id=reason_id)
            request.user.edit_post_reject_reason(
                reason, title=title, details=details
            )
        return {
            'reason_id': reason.id,
            'title': title,
            'details': details
        }
    else:
        raise Exception(forms.format_form_errors(form))


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.admins_only
def moderate_suggested_tag(request):
    """accepts or rejects a suggested tag
    if thread id is given, then tag is
    applied to or removed from only one thread,
    otherwise the decision applies to all threads
    """
    form = forms.ModerateTagForm(request.POST)
    if form.is_valid():
        tag_id = form.cleaned_data['tag_id']
        thread_id = form.cleaned_data.get('thread_id', None)

        try:
            tag = models.Tag.objects.get(id=tag_id)  # can tag not exist?
        except models.Tag.DoesNotExist:
            return

        if thread_id:
            threads = models.Thread.objects.filter(id=thread_id)
        else:
            threads = tag.threads.all()

        if form.cleaned_data['action'] == 'accept':
            #todo: here we lose ability to come back
            #to the tag moderation and approve tag to
            #other threads later for the case where tag.used_count > 1
            tag.status = models.Tag.STATUS_ACCEPTED
            tag.save()
            for thread in threads:
                thread.add_tag(
                    tag_name=tag.name,
                    user=tag.created_by,
                    timestamp=datetime.datetime.now(),
                    silent=True
                )
        else:
            if tag.threads.count() > len(threads):
                for thread in threads:
                    thread.tags.remove(tag)
                tag.used_count = tag.threads.count()
                tag.save()
            elif tag.status == models.Tag.STATUS_SUGGESTED:
                tag.delete()
    else:
        raise Exception(forms.format_form_errors(form))


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def save_draft_question(request):
    """saves draft questions"""
    #todo: allow drafts for anonymous users
    if request.user.is_anonymous():
        return

    form = forms.DraftQuestionForm(request.POST)
    if form.is_valid():
        title = form.cleaned_data.get('title', '')
        text = form.cleaned_data.get('text', '')
        tagnames = form.cleaned_data.get('tagnames', '')
        if title or text or tagnames:
            try:
                draft = models.DraftQuestion.objects.get(author=request.user)
            except models.DraftQuestion.DoesNotExist:
                draft = models.DraftQuestion()

            draft.title = title
            draft.text = text
            draft.tagnames = tagnames
            draft.author = request.user
            draft.save()


@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def save_draft_answer(request):
    """saves draft answers"""
    #todo: allow drafts for anonymous users
    if request.user.is_anonymous():
        return

    form = forms.DraftAnswerForm(request.POST)
    if form.is_valid():
        thread_id = form.cleaned_data['thread_id']
        try:
            thread = models.Thread.objects.get(id=thread_id)
        except models.Thread.DoesNotExist:
            return
        try:
            draft = models.DraftAnswer.objects.get(
                                            thread=thread,
                                            author=request.user
                                    )
        except models.DraftAnswer.DoesNotExist:
            draft = models.DraftAnswer()

        draft.author = request.user
        draft.thread = thread
        draft.text = form.cleaned_data.get('text', '')
        draft.save()


@decorators.get_only
def get_users_info(request):
    """retuns list of user names and email addresses
    of "fake" users - so that admins can post on their
    behalf"""
    if request.user.is_anonymous():
        return HttpResponseForbidden()

    query = request.GET['q']
    limit = IntegerField().clean(request.GET['limit'])

    users = models.User.objects
    user_info_list = users.filter(username__istartswith=query)

    if request.user.is_admin('user.change_proxyuser'):
        user_info_list = user_info_list.values_list('username', 'email')
    else:
        user_info_list = user_info_list.values_list('username')

    result_list = ['|'.join(info) for info in user_info_list[:limit]]
    return HttpResponse('\n'.join(result_list), mimetype='text/plain')

# DEPRECATED
# @csrf.csrf_protect
# def share_question_with_organization(request):
#     form = forms.ShareQuestionForm(request.POST)
#     try:
#         if form.is_valid():

#             thread_id = form.cleaned_data['thread_id']
#             organization_name = form.cleaned_data['recipient_name']

#             thread = models.Thread.objects.get(id=thread_id)
#             question_post = thread._main_post()

#             #get notif set before
#             sets1 = question_post.get_notify_sets(
#                                     mentioned_users=list(),
#                                     exclude_list=[request.user, ]
#                                 )

#             #share the post
#             if organization_name == openode_settings.GLOBAL_GROUP_NAME:
#                 thread.make_public(recursive=True)
#             else:
#                 organization = models.Organization.objects.get(name=organization_name)
#                 thread.add_to_organizations((organization,), recursive=True)

#             #get notif sets after
#             sets2 = question_post.get_notify_sets(
#                                     mentioned_users=list(),
#                                     exclude_list=[request.user, ]
#                                 )

#             notify_sets = {
#                 'for_mentions': sets2['for_mentions'] - sets1['for_mentions'],
#                 'for_email': sets2['for_email'] - sets1['for_email'],
#                 'for_inbox': sets2['for_inbox'] - sets1['for_inbox']
#             }

#             question_post.issue_update_notifications(
#                 updated_by=request.user,
#                 notify_sets=notify_sets,
#                 activity_type=const.TYPE_ACTIVITY_POST_SHARED,
#                 timestamp=datetime.datetime.now()
#             )

#             return HttpResponseRedirect(thread.get_absolute_url())
#     except Exception:
#         error_message = _('Sorry, looks like sharing request was invalid')
#         request.user.message_set.create(message=error_message)
#         return HttpResponseRedirect(thread.get_absolute_url())


@csrf.csrf_protect
def resolve_organization_join_request(request):
    """moderator of the organization can accept or reject a new user"""
    request_id = IntegerField().clean(request.POST['request_id'])
    action = request.POST['action']

    organization_membership = get_object_or_404(models.OrganizationMembership, pk=request_id)

    if action == 'approve':
        organization_membership.level = models.OrganizationMembership.FULL
        organization_membership.save()
        organization_membership.user.log(organization_membership.organization, const.LOG_ACTION_JOIN_GROUP)
        request.user.log(organization_membership, const.LOG_ACTION_APPROVE_JOIN_GROUP)

        msg_data = {'organization': organization_membership.organization.title}
        message = _('Your reqest to join organization %(organization)s has been approved!') % msg_data
        organization_membership.user.message_set.create(message=message)
    else:
        request.user.log(organization_membership, const.LOG_ACTION_REFUSE_JOIN_GROUP)

        msg_data = {'organization': organization_membership.organization.title}
        message = _('Sorry, your reqest to join organization %(organization)s has been denied.') % msg_data
        organization_membership.user.message_set.create(message=message)

        organization_membership.delete()

    return HttpResponseRedirect(reverse('user_profile', args=[request.user.id, 'organization_joins']))


@csrf.csrf_protect
def resolve_node_join_request(request):
    """moderator of the organization can accept or reject a new user"""
    request_id = IntegerField().clean(request.POST['request_id'])
    action = request.POST['action']
    assert(action in ('approve', 'deny'))

    activity = get_object_or_404(models.Activity, pk=request_id)
    node = activity.content_object
    applicant = activity.user

    if action == 'approve':
        cu, created = models.NodeUser.objects.get_or_create(user=applicant, node=node)

        applicant.log(node, const.LOG_ACTION_JOIN_NODE)
        request.user.log(cu, const.LOG_ACTION_APPROVE_JOIN_NODE)

        msg_data = {'node': node.title}
        message = _('Your request to join Node %(node)s has been approved!') % msg_data
        applicant.message_set.create(message=message)
    else:
        request.user.log(activity, const.LOG_ACTION_REFUSE_JOIN_NODE)

        msg_data = {'node': node.title}
        message = _('Sorry, your request to join Node %(node)s has been denied.') % msg_data
        applicant.message_set.create(message=message)

    activity.delete()
    return HttpResponseRedirect(reverse('user_profile', args=[request.user.id, 'node_joins']))

@csrf.csrf_protect
def resolve_node_create_request(request):
    """moderator of the organization can accept or reject a new user"""

    request_id = IntegerField().clean(request.POST['request_id'])
    action = request.POST['action']
    assert(action in ('approve', 'deny'))

    activity = get_object_or_404(models.Activity, pk=request_id)
    applicant = activity.user

    if action == 'approve':
        applicant.log(activity, const.LOG_ACTION_ASK_TO_CREATE_NODE_ACCEPTED)
        request.user.log(applicant, const.LOG_ACTION_ASK_TO_CREATE_NODE_ACCEPTED)

        message = _('Your request to create node has been approved!')
        applicant.message_set.create(message=message)
        activity.delete()

        title = request.GET.get("title")
        return HttpResponseRedirect("%s%s" % (
            reverse('admin:openode_node_add'),
            "?title=%s" % title if title else ""
        ))

    else:
        request.user.log(activity, const.LOG_ACTION_ASK_TO_CREATE_NODE_DECLINED)
        message = _('Sorry, your request to create node has been denied.')
        applicant.message_set.create(message=message)

    activity.delete()
    return HttpResponseRedirect(reverse('user_profile', args=[request.user.id, 'node_create']))

@csrf.csrf_protect
def resolve_organization_request(request):
    """moderator of the organization can accept or reject a new user"""

    request_id = IntegerField().clean(request.POST['request_id'])
    action = request.POST['action']
    assert(action in ('approve', 'deny'))

    activity = get_object_or_404(models.Activity, pk=request_id)
    applicant = activity.user
    org = activity.content_object

    if action == 'approve':
        org.approved = True
        org.save()
        applicant.log(activity, const.LOG_ACTION_ASK_TO_CREATE_ORG_ACCEPTED)
        request.user.log(applicant, const.LOG_ACTION_ASK_TO_CREATE_ORG_ACCEPTED)

        message = _('Your request to create organization has been approved!')
        applicant.message_set.create(message=message)
        activity.delete()
        #return HttpResponseRedirect(reverse('admin:openode_organization_change', args=(activity.object_id,)))
    else:
        request.user.log(activity, const.LOG_ACTION_ASK_TO_CREATE_ORG_DECLINED)
        message = _('Sorry, your request to create organization has been denied.')
        applicant.message_set.create(message=message)
        activity.delete()
    return HttpResponseRedirect(reverse('user_profile', args=[request.user.id, 'organization_requests']))


@login_required
def remove_from_followers(request, pk):
    """
        Only node managers can force remove user from thread-followed-users.
    """
    followed_thread = get_object_or_404(models.FollowedThread, pk=pk)
    thread = followed_thread.thread

    if not thread.node.node_users.filter(user=request.user, role=const.NODE_USER_ROLE_MANAGER).exists():
        return HttpResponseForbidden()

    url = reverse("thread_followers", args=[thread.node.pk, thread.node.slug, thread.get_module(), thread.pk, thread.slug])
    followed_thread.delete()
    return HttpResponseRedirect(url)


# DEPRECATED - to delete
@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
def publish_answer(request):
    """will publish or unpublish answer, if
    current thread is moderated
    """
    denied_msg = _('Sorry, only thread moderators can use this function')
    if request.user.is_authenticated():
        if request.user.is_administrator_or_moderator() is False:
            raise exceptions.PermissionDenied(denied_msg)
    #todo: assert permission
    answer_id = IntegerField().clean(request.POST['answer_id'])
    answer = models.Post.objects.get(id=answer_id, post_type='answer')

    return {'redirect_url': answer.get_absolute_url()}
