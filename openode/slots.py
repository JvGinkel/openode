# -*- coding: utf-8 -*-
import sys

from django.conf import settings

################################################################################
# EMAIL ERROR REPORTING
################################################################################


def report_exception(sender, **kwargs):
    """
    Reporting web errors via e-mail as a full traceback (same as debug 500 page)
    """
    from django.core.mail import EmailMultiAlternatives
    from django.views import debug

    request = kwargs['request']
    exc_info = sys.exc_info()
    response = debug.technical_500_response(request, *exc_info)

    user_string = 'USER: None'
    if request:
        if hasattr(request, 'user'):
            if request.user.is_anonymous():
                user_string = 'USER: anonymous'
            else:
                user_string = 'USER: %s %s' % (
                    request.user.pk,
                    request.user.email or "?"
                )

    subject = 'HTML Error (%s, %s): %s' % (
        request.META.get('REMOTE_ADDR') or "? IP",
        # (request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS and 'internal' or 'EXTERNAL'),
        user_string,
        request.path
    )
    content = response.content

    msg = EmailMultiAlternatives(
        settings.EMAIL_SUBJECT_PREFIX + subject,
        u'Please, see HTML content',
        settings.SERVER_EMAIL,
        [a[1] for a in settings.ADMINS if a]
    )
    msg.attach_alternative(content, "text/html")
    msg.send()
