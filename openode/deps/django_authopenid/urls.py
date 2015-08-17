# -*- coding: utf-8 -*-
from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('openode.deps.django_authopenid.views',
    # yadis rdf
    url(r'^yadis.xrdf$', 'xrdf', name='yadis_xrdf'),
     # manage account registration
    url(r'^signin/$', 'signin', name='user_signin'),
    url(r'^widget/signin/$', 'signin', {'template_name': 'authopenid/widget_signin.html'}, name='widget_signin'),
    url(r'^signout/$', 'signout', name='user_signout'),
    #this view is "complete-openid" signin
    url(r'^signin/complete/$', 'complete_signin', name='user_complete_signin'),
    url(r'^signin/complete-oauth/$', 'complete_oauth_signin', name='user_complete_oauth_signin'),

    url(r'^lost-password/$', 'lost_password', name="lost_password"),
    url(r'^lost-password/done/$', 'lost_password_done', name="lost_password_done"),
    url(r'^change-password/(?P<key>\w+)/$', 'change_password', name="change_password"),

    url(r'^register/$', 'register', name='user_register'),
    url(r'^signup/$', 'signup_with_password', name='user_signup_with_password'),
    url(r'^logout/$', 'logout_page', name='logout'),  # only page displaying info of successful logout
    #these two commeted out urls should work only with EMAIL_VALIDATION=True
    #but the setting is disabled right now
    #url(r'^%s%s$' % (_('email/'), _('sendkey/')), 'send_email_key', name='send_email_key'),
    #url(r'^%s%s(?P<id>\d+)/(?P<key>[\dabcdef]{32})/$' % (_('email/'), _('verify/')), 'verifyemail', name='user_verifyemail'),
    url(r'^recover/$', 'account_recover', name='user_account_recover'),
    url(r'^verify-email/$', 'verify_email_and_register', name='verify_email_and_register'),

    # this method is ajax only
    url(r'^delete_login_method/$', 'delete_login_method', name='delete_login_method'),
)
