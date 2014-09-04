# -*- coding: utf-8 -*-
"""
openode openode url configuraion file
"""
import os.path
from django.conf import settings
from django.conf.urls.defaults import url, patterns, include
from django.contrib import admin
from openode.feed import RssLastestQuestionsFeed, RssIndividualQuestionFeed
from openode.sitemap import QuestionsSitemap
from openode.skins.utils import update_media_revision
from openode import const

from slots import report_exception

if not settings.DEBUG:
    from django.core import signals as core_signals
    core_signals.got_request_exception.connect(report_exception)

admin.autodiscover()
update_media_revision()  # needs to be run once, so put it here

node_url = 'node/(?P<node_id>\d+)/(?P<node_slug>[\w-]+)'

node_module_url = '%s/(?P<module>%s)/' % (node_url, '|'.join([cm[0] for cm in const.NODE_MODULES]))


threads_filter_kwargs = (
    ('scope', '(?P<scope>[\w\-]+)'),
    ('sort', '(?P<sort>[\w\-]+)'),
    # ('query', '(?P<query>[^/]+)'),
    ('tags', '(?P<tags>[\w+.#,-]+)'),
    ('author', '(?P<author>[\[\d\,\]]+)'),
    ('page', '(?P<page>\d+)')
)

threads_filter_regex = ''.join(['(%s:%s/)?' % (key, val) for key, val in threads_filter_kwargs])

feeds = {
    'rss': RssLastestQuestionsFeed,
    'question': RssIndividualQuestionFeed
}

sitemaps = {
    'questions': QuestionsSitemap
}

handler500 = "openode.views.http.server_error"
handler404 = "openode.views.http.not_found"

APP_PATH = os.path.dirname(__file__)

from openode import views


urlpatterns = patterns('',
    url(r'^$', views.readers.index, name='index'),

    (r'^admin/', include(admin.site.urls)),
    (r'^settings/', include('openode.deps.livesettings.urls')),

    url(r'^toggle-node/$', views.readers.toggle_node, name='toggle_node'),
    url(r'^toggle-category/$', views.readers.toggle_category, name='toggle_category'),

    url(
        r'^sitemap.xml$',
        'django.contrib.sitemaps.views.sitemap',
        {'sitemaps': sitemaps},
        name='sitemap'
    ),

    (r'^search/', include('openode.search.urls')),

    url(r'^live/', views.live.live, name="live"),

    # documents urls
    # url(r'^document/', include("openode.document.urls", namespace="document")),

    url(r'^archive/', views.readers.archive, name="archive"),

    # url(r'^about/$', views.meta.about, name='about'),
    # url(r'^privacy/$', views.meta.privacy, name='privacy'),
    # url(r'^help/$', views.meta.help, name='help'),

    url(
        r'^(?P<slug>[a-zA-Z0-9\-_]+)\.html$',
        views.readers.static_page,
        name='static_page'
    ),

    url(
        r'^answers/(?P<id>\d+)/edit/$',
        views.writers.edit_answer,
        name='edit_answer'
    ),
    url(
        r'^answers/(?P<id>\d+)/revisions/$',
        views.readers.revisions,
        kwargs={'post_type': 'answer'},
        name='answer_revisions'
    ),

    url(
        r'^%s/$' % node_url,
        views.node.node_detail,
        name='node'
    ),

    url(
        r'^%s/annotation/edit/$' % node_url,
        views.node.node_annotation_edit,
        name='node_annotation_edit'
    ),

    url(
        r'^%s/settings/$' % node_url,
        views.node.node_settings,
        name='node_settings'
    ),

    ###################################

    url(
        r'^mark-read/(?P<node>all|\d+)/',
        views.node.mark_read,
        name='node_mark_read'
    ),

    url(
        r'^mark-read/followed\-(?P<followed>%s)/$' % ("|".join([const.THREAD_TYPE_QUESTION, const.THREAD_TYPE_DISCUSSION, "node"])),
        views.node.mark_read,
        name='node_mark_read'
    ),

    ###################################

    url(
        r'^%s/follow/$' % node_url,
        views.node.node_follow,
        name='node_follow'
    ),

    url(
        r'^%s/unfollow/$' % node_url,
        views.node.node_unfollow,
        name='node_unfollow'
    ),
    url(
        r'^%s/subscribe/$' % node_url,
        views.node.node_subscribe,
        name='node_subscribe'
    ),
    url(
        r'^%s/ask-to-join/$' % node_url,
        views.node.node_ask_to_join,
        name='node_ask_to_join'
    ),

    url(
        r'^%s/unsubscribe/$' % node_url,
        views.node.node_unsubscribe,
        name='node_unsubscribe'
    ),

    url(
        r'^%s/followers/$' % node_url,
        views.node.node_followers,
        name='node_followers'
    ),

    ############################################################################

    # force forum 'module'
    # url(
    #     r'node/(?P<node_id>\d+)/(?P<node_slug>[\w-]+)/(?P<module>forum)/',
    #     views.readers.node_module,
    #     name='node_module'
    # ),

    # other modules
    url(
        r'^%s%s$' % (node_module_url, threads_filter_regex),
        views.readers.node_module,
        name='node_module'
    ),

    ############################################################################

    url(
        r'^%s/edit-perexes/$' % node_url,
        views.node.node_perexes_edit,
        name='node_perexes_edit'
    ),


    ###################################
    # library urls
    ###################################

    url(
        r'^%s/%s/' % (node_url, const.NODE_MODULE_LIBRARY),
        include('openode.document.urls')
    ),

    ###################################

    url(
        r'^admin/show-perm-table/',
        views.users.show_perm_table,
        name='show_perm_table'
    ),

    ###################################

    url(
        r'^api/get_questions/',
        views.commands.api_get_questions,
        name='api_get_questions'
    ),
    url(
        r'^get-thread-shared-users/',
        views.commands.get_thread_shared_users,
        name='get_thread_shared_users'
    ),
    # url(
    #     r'^get-thread-shared-organizations/',
    #     views.commands.get_thread_shared_organizations,
    #     name='get_thread_shared_organizations'
    # ),
    url(
        r'^resolve-organization-join-request/',
        views.commands.resolve_organization_join_request,
        name='resolve_organization_join_request'
    ),
    url(
        r'^resolve-node-join-request/',
        views.commands.resolve_node_join_request,
        name='resolve_node_join_request'
    ),
    url(
        r'^save-draft-question/',
        views.commands.save_draft_question,
        name='save_draft_question'
    ),
    url(
        r'^save-draft-answer/',
        views.commands.save_draft_answer,
        name='save_draft_answer'
    ),
    url(
        r'^get-users-info/',
        views.commands.get_users_info,
        name='get_users_info'
    ),
    # url(
    #     r'^get-editor/',
    #     views.commands.get_editor,
    #     name='get_editor'
    # ),
    url(
        r'^%s%s$' % (node_module_url, 'add/'),
        views.writers.thread_add,
        name='thread_add'
    ),
    url(
        r'^thread/(?P<id>\d+)/edit/$',
        views.writers.edit_thread,
        name='edit_thread'
    ),
    url(  # this url is both regular and ajax
        r'^%s(?P<id>\d+)/%s$' % ('questions/', 'retag/'),
        views.writers.retag_question,
        name='retag_question'
    ),
    url(
        r'^%s(?P<thread_id>\d+)/%s$' % ('thread/', 'close/'),
        views.commands.close,
        name='thread_close'
    ),
    url(
        r'^%s(?P<thread_id>\d+)/%s$' % ('thread/', 'reopen/'),
        views.commands.reopen,
        name='thread_reopen'
    ),
    url(  # ajax only
        r'^%s(?P<thread_id>\d+)/%s$' % ('thread/', 'vote/'),
        views.commands.vote,
        name='vote'
    ),
    url(
        r'^%s(?P<id>\d+)/%s$' % ('questions/', 'revisions/'),
        views.readers.revisions,
        kwargs={'post_type': 'question'},
        name='question_revisions'
    ),
    url(  # ajax only
        r'^comment/upvote/$',
        views.commands.upvote_comment,
        name='upvote_comment'
    ),
    url(  # ajax only
        r'^post/delete/$',
        views.commands.delete_post,
        name='delete_post'
    ),
    url(  # ajax only
        r'^thread/(?P<thread_id>\d+)/delete/$',
        views.commands.delete_thread,
        name='delete_thread'
    ),
    url(  # ajax only
        r'^post_comments/$',
        views.writers.post_comments,
        name='post_comments'
    ),

    url(
        r'^discussion-answer/(?P<pk>\d+)/$',
        views.readers.discussion_answer,
        name='discussion_answer'
    ),

    url(  # ajax only
        r'^edit_comment/$',
        views.writers.edit_comment,
        name='edit_comment'
    ),
    url(  # ajax only
        r'^comment/delete/$',
        views.writers.delete_comment,
        name='delete_comment'
    ),
    url(  # ajax only
        r'^comment/get_text/$',
        views.readers.get_comment,
        name='get_comment'
    ),
    url(  # post only
        r'^comment/convert/$',
        views.writers.comment_to_answer,
        name='comment_to_answer'
    ),
    url(  # post only
        r'^answer/convert/$',
        views.writers.answer_to_comment,
        name='answer_to_comment'
    ),
    url(  # post only
        r'^answer/publish/$',
        views.commands.publish_answer,
        name='publish_answer'
    ),
    url(
        r'^tags/$',
        views.tag.tag_list,
        name='tags'
    ),
    url(
        r'^tags/(?P<tag_id>\d+)/$',
        views.tag.tag_detail,
        name='tag_detail'
    ),
    url(
        r'^%s$' % 'suggested-tags/',
        views.meta.list_suggested_tags,
        name='list_suggested_tags'
    ),
    url(  # ajax only
        r'^%s$' % 'moderate-suggested-tag',
        views.commands.moderate_suggested_tag,
        name='moderate_suggested_tag'
    ),
    #todo: collapse these three urls and use an extra json data var
    url(  # ajax only
        r'^%s%s$' % ('mark-tag/', 'interesting/'),
        views.commands.mark_tag,
        kwargs={'reason': 'good', 'action': 'add'},
        name='mark_interesting_tag'
    ),
    url(  # ajax only
        r'^%s%s$' % ('mark-tag/', 'ignored/'),
        views.commands.mark_tag,
        kwargs={'reason': 'bad', 'action': 'add'},
        name='mark_ignored_tag'
    ),
    url(  # ajax only
        r'^%s%s$' % ('mark-tag/', 'subscribed/'),
        views.commands.mark_tag,
        kwargs={'reason': 'subscribed', 'action': 'add'},
        name='mark_subscribed_tag'
    ),
    url(  # ajax only
        r'^unmark-tag/',
        views.commands.mark_tag,
        kwargs={'action': 'remove'},
        name='unmark_tag'
    ),
    url(  # ajax only
        r'^set-tag-filter-strategy/',
        views.commands.set_tag_filter_strategy,
        name='set_tag_filter_strategy'
    ),
    url(
        r'^get-tags-by-wildcard/',
        views.commands.get_tags_by_wildcard,
        name='get_tags_by_wildcard'
    ),
    url(
        r'^get-tag-list/',
        views.commands.get_tag_list,
        name='get_tag_list'
    ),
    url(
        r'^load-object-description/',
        views.commands.load_object_description,
        name='load_object_description'
    ),
    url(  # ajax only
        r'^save-object-description/',
        views.commands.save_object_description,
        name='save_object_description'
    ),
    url(  # ajax only
        r'^add-tag-category/',
        views.commands.add_tag_category,
        name='add_tag_category'
    ),
    url(  # ajax only
        r'^rename-tag/',
        views.commands.rename_tag,
        name='rename_tag'
    ),
    url(
        r'^delete-tag/',
        views.commands.delete_tag,
        name='delete_tag'
    ),
    url(  # ajax only
        r'^save-organization-logo-url/',
        views.commands.save_organization_logo_url,
        name='save_organization_logo_url'
    ),
    url(  # ajax only
        r'^delete-organization-logo/',
        views.commands.delete_organization_logo,
        name='delete_organization_logo'
    ),
    url(  # ajax only
        r'^add-organization/',
        views.commands.add_organization,
        name='add_organization'
    ),
    url(  # ajax only
        r'^set-organization-openness/',
        views.commands.set_organization_openness,
        name='set_organization_openness'
    ),
    url(  # ajax only
        r'^edit-object-property-text/',
        views.commands.edit_object_property_text,
        name='edit_object_property_text'
    ),
    url(
        r'^swap-question-with-answer/',
        views.commands.swap_question_with_answer,
        name='swap_question_with_answer'
    ),
    url(
        r'^%s$' % 'subscribe-for-tags/',
        views.commands.subscribe_for_tags,
        name='subscribe_for_tags'
    ),
    url(
        r'^%s$' % 'users/',
        views.users.show_users,
        name='users'
    ),
    url(
        r'^(?P<organization_id>\d+)/(?P<organization_slug>[^\/]+)/$',
        views.users.organization_detail,
        name='organization_detail'
    ),
    url(
        r'^%s%s(?P<organization_id>\d+)/(?P<organization_slug>[^\/]+)/membership/$' % ('users/', 'by-organization/'),
        views.users.organization_membership,
        name='organization_membership'
    ),
    #todo: rename as user_edit, b/c that's how template is named
    url(
        r'^%s(?P<id>\d+)/%s$' % ('users/', 'edit/'),
        views.users.edit_user,
        name='edit_user'
    ),
    url(
        r'^%s(?P<id>\d+)/$' % 'users/',
        views.users.user_profile, {'tab_name': ''},
        name='user_profile'
    ),
    url(
        r'^%s(?P<id>\d+)/(?P<tab_name>\w+)/$' % 'users/',
        views.users.user_profile,
        name='user_profile'
    ),
    url(
        r'^%s$' % 'organizations/',
        views.users.organization_list,
        name='organization_list'
    ),
    url(
        r'^%s$' % 'users/update_has_custom_avatar/',
        views.users.update_has_custom_avatar,
        name='user_update_has_custom_avatar'
    ),
    url(
        r'get-html-template/',
        views.commands.get_html_template,
        name='get_html_template'
    ),
    url(  # ajax only
        r'^%s%s$' % ('messages/', 'markread/'),
        views.commands.read_message,
        name='read_message'
    ),
    url(  # ajax only
        r'^manage-inbox/$',
        views.commands.manage_inbox,
        name='manage_inbox'
    ),
    url(  # ajax only
        r'^save-post-reject-reason/$',
        views.commands.save_post_reject_reason,
        name='save_post_reject_reason'
    ),
    url(  # ajax only
        r'^delete-post-reject-reason/$',
        views.commands.delete_post_reject_reason,
        name='delete_post_reject_reason'
    ),
    url(  # ajax only
        r'^edit-organization-membership/$',
        views.commands.edit_organization_membership,
        name='edit_organization_membership'
    ),
    url(  # ajax only
        r'^join-or-leave-organization/$',
        views.commands.join_or_leave_organization,
        name='join_or_leave_organization'
    ),
    url(
        r'^feeds/(?P<url>.*)/$',
        'django.contrib.syndication.views.feed',
        {'feed_dict': feeds},
        name='feeds'
    ),
    #upload url is ajax only
    url(r'^%s$' % 'upload/', views.writers.upload, name='upload'),

    url(r'^upload-attachment-node/(?P<node_id>\d+)/$', views.upload.upload_attachment_node, name='upload_attachment_node'),
    # url(r'^upload-attachment-thread/(?P<thread_id>\d+)/$', views.upload.upload_attachment_thread, name='upload_attachment_thread'),

    # static serving attachemnt files with permission check
    url(
        r'^%s(\w+)/(?P<uuid>\w+)/(.+)$' % (settings.WYSIWYG_NODE_URL[1:]),
        views.download.download_attachment,
        {'model_name': "AttachmentFileNode"},
        name='download_attachment'
        ),
    url(
        r'^%s(\w+)/(?P<uuid>\w+)/(.+)$' % (settings.WYSIWYG_THREAD_URL[1:]),
        views.download.download_attachment,
        {'model_name': "AttachmentFileThread"},
        name='download_attachment'
        ),

    url(r'^%s$' % 'feedback/', views.meta.feedback, name='feedback'),
    #url(r'^feeds/rss/$', RssLastestQuestionsFeed, name="latest_questions_feed"),
    url(
        r'^doc/(?P<path>.*)$',
        'django.views.static.serve',
        {'document_root': os.path.join(APP_PATH, 'doc', 'build', 'html').replace('\\', '/')},
        name='openode_docs',
    ),
    url(
        '^custom\.css$',
        views.meta.config_variable,
        kwargs={
            'variable_name': 'CUSTOM_CSS',
            'mimetype': 'text/css'
        },
        name='custom_css'
    ),
    url(
        '^custom\.js$',
        views.meta.config_variable,
        kwargs={
            'variable_name': 'CUSTOM_JS',
            'mimetype': 'text/javascript'
        },
        name='custom_js'
    ),
    url(
        r'^jsi18n/$',
        'django.views.i18n.javascript_catalog',
        {'domain': 'djangojs', 'packages': ('openode',)},
        name='openode_jsi18n'
    ),
    url(r'^set_lang/$', views.readers.set_lang, name='set_lang'),

    url(
        r'^%s%s(?P<thread_id>\d+)/(?P<thread_slug>[\w-]+)/$' % (node_module_url, 'thread/'),
        views.thread.thread,
        name='thread'
    ),
    url(
        r'^%s%s/(?P<thread_id>\d+)/(?P<thread_slug>[\w-]+)/followers/$' % (node_module_url, 'thread'),
        views.readers.thread_followers,
        name='thread_followers'
    ),
    url(
        r'^%s%s/(?P<thread_id>\d+)/(?P<thread_slug>[\w-]+)/last-visit/$' % (node_module_url, 'thread'),
        views.readers.thread_last_visit,
        name='thread_last_visit'
    ),

    url(
        r'^remove-from-followers/(?P<pk>\d+)/$',
        views.commands.remove_from_followers,
        name='remove_from_followers'
    ),

)


if 'openode.deps.django_authopenid' in settings.INSTALLED_APPS:
    urlpatterns += (
        url(r'^%s' % 'account/', include('openode.deps.django_authopenid.urls')),
    )

if 'avatar' in settings.INSTALLED_APPS:
    #unforturately we have to wire avatar urls here,
    #because views add and change are adapted to
    #use jinja2 templates
    urlpatterns += (
        url('^avatar/add/$', views.avatar_views.add, name='avatar_add'),
        url(
            '^avatar/change/$',
            views.avatar_views.change,
            name='avatar_change'
        ),
        url(
            '^avatar/delete/$',
            views.avatar_views.delete,
            name='avatar_delete'
        ),
        url(  # this urs we inherit from the original avatar app
            '^avatar/render_primary/(?P<user_id>[\+\d]+)/(?P<size>[\d]+)/$',
            views.avatar_views.render_primary,
            name='avatar_render_primary'
        ),
    )

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += (
        url(r'^rosetta/', include('rosetta.urls')),
    )

if 'admin_tools' in settings.INSTALLED_APPS:
    urlpatterns += (
        url(r'^admin_tools/', include('admin_tools.urls')),
    )

if 'django_select2' in settings.INSTALLED_APPS:
    urlpatterns += (
        url(r'^ext/', include('django_select2.urls')),
    )

urlpatterns += patterns('',
    url(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:],
        'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT.replace('\\', '/')},
    ),
)

if settings.FORCE_STATIC_SERVE_WITH_DJANGO:
    urlpatterns += patterns('',
        url(
            r'^%s(?P<path>.*)$' % settings.STATIC_URL[1:],
            'django.views.static.serve',
            {'document_root': settings.STATIC_ROOT.replace('\\', '/')},
        ),
    )
