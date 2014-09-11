# -*- coding: utf-8 -*-

import logging

from django.conf import settings as django_settings
from django.utils.translation import activate, get_language
from django.utils.translation import ugettext as _

from openode import const
from openode import mail
from openode.conf import settings as openode_settings
from openode.utils import humanize_datetime
from openode.skins.loaders import get_template


def immediately_notify_users(post):

    # we don't want to disturb original routine
    try:
        # set default language TODO - language per user - add user atribute
        old_lang = get_language()
        activate(django_settings.LANGUAGE_CODE)

        DEBUG_THIS_COMMAND = getattr(django_settings, 'DEBUG_SEND_EMAIL_NOTIFICATIONS', True)

        # compose subject according to the post type
        subject_line = _('Notification')
        if post.post_type == const.POST_TYPE_QUESTION:
            subject_line += ': ' + _('Question')
        elif post.post_type == const.POST_TYPE_DOCUMENT:
            subject_line += ': ' + _('Document')
        elif post.post_type == const.POST_TYPE_COMMENT:
            subject_line += ': ' + _('Comment')
        elif post.post_type == const.POST_TYPE_THREAD_POST:
            if post.thread.thread_type == const.THREAD_TYPE_QUESTION:
                subject_line += ': ' + _('Answer')
            elif post.thread.thread_type == const.THREAD_TYPE_DISCUSSION:
                subject_line += ': ' + _('Discussion post')
        else:
            # post type is probably only a description, do nothing
            activate(old_lang)
            return False

        subject_line += ' - ' + post.thread.title

        # compose message according to post type
        url_prefix = openode_settings.APP_URL
        # link to node
        # text = u'<p>%s: <a href="%s">%s</a></p>' % (_('Node'), url_prefix + post.thread.node.get_absolute_url(), post.thread.node.full_title())
        text = u'<p>%s: %s</p>' % (_('Node'), post.thread.node.full_title())
        # title according to the post type
        text += '<h2>'
        if post.last_edited_by:
            # post was updated
            if post.post_type == const.POST_TYPE_QUESTION:
                text += _('Updated question')
            elif post.post_type == const.POST_TYPE_DOCUMENT:
                text += _('Updated document')
            elif post.post_type == const.POST_TYPE_COMMENT:
                text += _('Updated comment')
            elif post.post_type == const.POST_TYPE_THREAD_POST:
                if post.thread.thread_type == const.THREAD_TYPE_QUESTION:
                    text += _('Updated answer')
                elif post.thread.thread_type == const.THREAD_TYPE_DISCUSSION:
                    text += _('Updated discussion post')
        else:
            # post is new
            if post.post_type == const.POST_TYPE_QUESTION:
                text += _('New question')
            elif post.post_type == const.POST_TYPE_DOCUMENT:
                text += _('New document')
            elif post.post_type == const.POST_TYPE_COMMENT:
                text += _('New comment')
            elif post.post_type == const.POST_TYPE_THREAD_POST:
                if post.thread.thread_type == const.THREAD_TYPE_QUESTION:
                    text += _('New answer')
                elif post.thread.thread_type == const.THREAD_TYPE_DISCUSSION:
                    text += _('New discussion post')
        text += '</h2>'

        # link to post
        if post.post_type == const.POST_TYPE_DOCUMENT:
            url = url_prefix + post.thread.get_absolute_url()
        else:
            url = url_prefix + post.get_absolute_url()
        text += '<p><a href="%(url)s">%(url)s</a></p>' % {"url": url}

        # author
        text += '<p>'
        if post.last_edited_by:
            # post was updated
            text += _(u'%(datetime)s changed by <strong>%(user)s</strong>') % {'datetime': humanize_datetime(post.last_edited_at, 0), 'user': post.last_edited_by.screen_name}
        else:
            # post is new
            text += _(u'%(datetime)s created by <strong>%(user)s</strong>') % {'datetime': humanize_datetime(post.added_at, 0), 'user': post.author.screen_name}
        text += '</p>'

        # show post text
        text += post.html

        # show related post if convenient
        if post.post_type == const.POST_TYPE_THREAD_POST and post.thread.thread_type == const.THREAD_TYPE_QUESTION:
            text += '<h3>'
            text += _('Question')
            text += '</h3>'
            # text += '<p><a href="%s">%s</a></p>' % (url_prefix + post.thread._main_post().get_absolute_url(), url_prefix + post.thread._main_post().get_absolute_url())
            text += post.thread._main_post().html
        elif post.post_type == const.POST_TYPE_COMMENT:
            text += '<h3>'
            text += _('Commented post')
            text += '</h3>'
            # text += '<p><a href="%s">%s</a></p>' % (url_prefix + post.parent.get_absolute_url(), url_prefix + post.parent.get_absolute_url())
            text += post.parent.html

        # message bottom
        text += '<hr />'
        text += '<p>'
        text += _('Please remember that you can always adjust frequency of the email updates or turn them off entirely in your profile.')
        text += '</p>'
        text += '<p>'
        text += _('If you believe that this message was sent in an error, please contact us.')
        text += '</p>'

        # render email
        data = {
            'text': text,
            'site_name': openode_settings.APP_SHORT_NAME,
            'site_url': openode_settings.APP_URL
        }
        template = get_template('email/instant_notification.html')
        message = template.render(data)

        recipients = {}
        # get all thread followers
        for user in post.thread.followed_by.filter(notification_subscriptions__frequency='i', notification_subscriptions__feed_type='q_sel'):
            recipients[user.pk] = user

        # get all node followers
        for user in post.thread.node.followed_by.filter(notification_subscriptions__frequency='i', notification_subscriptions__feed_type='q_sel'):
            recipients[user.pk] = user

        # remove author of this editation from recipients
        if post.last_edited_by:
            # post was updated
            recipients.pop(post.last_edited_by.pk, None)
        else:
            # post is new
            recipients.pop(post.author.pk, None)

        # send all emails
        for user in recipients.values():
            if DEBUG_THIS_COMMAND:
                recipient_email = django_settings.ADMINS[0][1]
            else:
                recipient_email = user.email

            mail.send_mail(subject_line, message, django_settings.DEFAULT_FROM_EMAIL, [recipient_email], raise_on_failure=True)
            logging.info('Email notification sent: %s' % repr({
                "user": user.screen_name,
                "user_email": recipient_email,
                "user_pk": user.pk,
                "post_pk": post.pk
            }))

        activate(old_lang)
        return True

    except Exception, e:
        logging.error('Email notification - failed to send immediate notification for post: %s' % repr({
            "post_pk": post.pk,
            "error": e
        }))

    return False

def notify_about_requests(user_list, subject, text):
    data = {
            'text': text,
            'site_name': openode_settings.APP_SHORT_NAME,
            'site_url': openode_settings.APP_URL
        }

    template = get_template('email/notification.html')
    message = template.render(data)
    email_list = [user.email for user in user_list]

    mail.send_mail(subject, message, django_settings.DEFAULT_FROM_EMAIL, email_list, raise_on_failure=True)

