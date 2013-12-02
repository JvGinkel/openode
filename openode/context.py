# -*- coding: utf-8 -*-
"""Openode template context processor that makes some parameters
from the django settings, all parameters from the openode livesettings
and the application available for the templates
"""
import sys
from django.conf import settings
from django.core.urlresolvers import reverse
# from django.utils import simplejson

import openode
# from openode import models
from openode import const
from openode.conf import settings as openode_settings
from openode.skins.loaders import get_skin
from openode.utils import url_utils
from openode.utils.slug import slugify


def application_settings(request):
    """The context processor function"""
    if not request.path.startswith('/' + settings.OPENODE_URL):
        #todo: this is a really ugly hack, will only work
        #when openode is installed not at the home page.
        #this will not work for the
        #heavy modders of openode, because their custom pages
        #will not receive the openode settings in the context
        #to solve this properly we should probably explicitly
        #add settings to the context per page
        return {}

    my_settings = openode_settings.as_dict()
    my_settings['LANGUAGE_CODE'] = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    my_settings['ALLOWED_UPLOAD_FILE_TYPES'] = settings.OPENODE_ALLOWED_UPLOAD_FILE_TYPES
    my_settings['OPENODE_URL'] = settings.OPENODE_URL
    my_settings['STATIC_URL'] = settings.STATIC_URL
    my_settings['OPENODE_CSS_DEVEL'] = getattr(settings, 'OPENODE_CSS_DEVEL', False)
    my_settings['DEBUG'] = settings.DEBUG
    my_settings['FORCE_STATIC_SERVE_WITH_DJANGO'] = settings.FORCE_STATIC_SERVE_WITH_DJANGO
    my_settings['USING_RUNSERVER'] = 'runserver' in sys.argv
    my_settings['OPENODE_VERSION'] = openode.get_version()
    my_settings['LOGIN_URL'] = url_utils.get_login_url()
    my_settings['USER_REGISTRATION_URL'] = url_utils.get_user_registration_url()
    my_settings['LOGOUT_URL'] = url_utils.get_logout_url()
    my_settings['LOGOUT_REDIRECT_URL'] = url_utils.get_logout_redirect_url()
    my_settings['LANGUAGES'] = getattr(settings, 'LANGUAGES', ())

    # wysiwyg
    my_settings["WYSIWYG_SETTING_SIMPLE"] = settings.WYSIWYG_SETTING_SIMPLE
    my_settings["WYSIWYG_SETTING_COMMENT"] = settings.WYSIWYG_SETTING_COMMENT

    context = {
        'settings': my_settings,
        'skin': get_skin(request),
        'moderation_items': request.user.get_moderation_items(),
        'noscript_url': const.DEPENDENCY_URLS['noscript'],
        'THREAD_TYPE_QUESTION': const.THREAD_TYPE_QUESTION,
        'THREAD_TYPE_DISCUSSION': const.THREAD_TYPE_DISCUSSION,
        'THREAD_TYPE_DOCUMENT': const.THREAD_TYPE_DOCUMENT,
    }

    #calculate context needed to list all the organizations
    def _get_organization_url(organization):
        """calculates url to the organization based on its id and name"""
        organization_slug = slugify(organization['name'])
        return reverse(
            'organization_detail',
            kwargs={'organization_id': organization['id'], 'organization_slug': organization_slug}
        )

    return context
