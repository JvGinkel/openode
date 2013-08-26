"""
Authorisation related functions.

This entire module will be removed some time in
the future

Many of these functions are being replaced with assertions:
User.assert_can...
"""
import datetime
from django.db import transaction
#from openode.models import Answer
from openode.models import signals
from openode.conf import settings as openode_settings


###########################################
## actions changes event
###########################################
@transaction.commit_on_success
def onFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()

    post.offensive_flag_count = post.offensive_flag_count + 1
    post.save()

    signals.flag_offensive.send(
        sender=post.__class__,
        instance=post,
        mark_by=user
    )

    if post.is_comment():
        #do not hide or delete comments automatically yet,
        #because there is no .deleted field in the comment model
        return

    #todo: These should be updated to work on same revisions.
    if post.offensive_flag_count == openode_settings.MIN_FLAGS_TO_HIDE_POST:
        pass

    elif post.offensive_flag_count == openode_settings.MIN_FLAGS_TO_DELETE_POST:

        post.deleted = True
        #post.deleted_at = timestamp
        #post.deleted_by = Admin
        post.save()


@transaction.commit_on_success
def onUnFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()

    post.offensive_flag_count = post.offensive_flag_count - 1
    post.save()

    signals.remove_flag_offensive.send(
        sender=post.__class__,
        instance=post,
        mark_by=user
    )

    if post.is_comment():
        #do not hide or delete comments automatically yet,
        #because there is no .deleted field in the comment model
        return

    #todo: These should be updated to work on same revisions.
    # The post fell below DELETE treshold, undelete it
    if post.offensive_flag_count == openode_settings.MIN_FLAGS_TO_DELETE_POST - 1:
        post.deleted = False
        post.save()


@transaction.commit_on_success
def onAnswerAccept(answer, user, timestamp=None):
    answer.thread.set_accepted_answer(answer=answer, timestamp=timestamp)


@transaction.commit_on_success
def onAnswerAcceptCanceled(answer, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    answer.thread.set_accepted_answer(answer=None, timestamp=None)


@transaction.commit_on_success
def onUpVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.save()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) + 1
    post.points = int(post.points) + 1
    post.save()


@transaction.commit_on_success
def onUpVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.delete()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) - 1
        if post.vote_up_count < 0:
            post.vote_up_count = 0

    post.points = int(post.points) - 1
    post.save()


@transaction.commit_on_success
def onDownVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.save()

    post.vote_down_count = int(post.vote_down_count) + 1
    post.points = int(post.points) - 1
    post.save()


@transaction.commit_on_success
def onDownVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.delete()

    post.vote_down_count = int(post.vote_down_count) - 1
    if post.vote_down_count < 0:
        post.vote_down_count  = 0
    post.points = post.points + 1
    post.save()
