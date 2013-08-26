# -*- coding: utf-8 -*-

from openode.deps.django_authopenid.forms import LoginForm
from openode.forms import clean_login_url

from openode.models.cms import MenuItem, MENU_UPPER, MENU_FOOTER
from openode.const import NODE_MODULE_ANNOTATION, NODE_MODULE_QA, NODE_MODULE_FORUM, NODE_MODULE_LIBRARY
from openode.views.context import get_for_user_profile


def menu_items(request):
    """
    add menu items to context
    """
    return {
        "menu_items_upper": MenuItem.objects.filter(menu=MENU_UPPER, language=request.LANGUAGE_CODE),
        "menu_items_footer": MenuItem.objects.filter(menu=MENU_FOOTER, language=request.LANGUAGE_CODE)
    }


def node_modules(request):
    """
    add node module names constants to context
    """
    return {
        "NODE_MODULE_ANNOTATION": NODE_MODULE_ANNOTATION,
        "NODE_MODULE_QA": NODE_MODULE_QA,
        "NODE_MODULE_FORUM": NODE_MODULE_FORUM,
        "NODE_MODULE_LIBRARY": NODE_MODULE_LIBRARY
    }


def login_form(request):
    """
    login form
    """
    if not request.user.is_authenticated():

        next = clean_login_url(request.get_full_path())

        header_login_form = LoginForm(initial={
            'login_provider_name': 'local',
            'password_action': 'login',
            'next': next
        })
        return {
            "header_login_form": header_login_form
        }
    else:
        return {}


def user_profile(request):
    if 'flags_count' not in request:
        return get_for_user_profile(request.user)
    else:
        return {}
