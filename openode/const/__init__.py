# encoding:utf-8
"""
All constants could be used in other modules
For reasons that models, views can't have unicode
text in this project, all unicode text go here.
"""
from django.utils.translation import ugettext as _
import re

LONG_TIME = 60 * 60 * 24 * 30  # 30 days is a lot of time
DATETIME_FORMAT = '%I:%M %p, %d %b %Y'


THREAD_SORT_METHOD_AGE = 'age'
THREAD_SORT_METHOD_ACTIVITY = 'activity'
THREAD_SORT_METHOD_POSTS = 'posts'

THREAD_SORT_DIR_UP = 'asc'
THREAD_SORT_DIR_DOWN = 'desc'

THREAD_SORT_DIR_LIST = (THREAD_SORT_DIR_UP, THREAD_SORT_DIR_DOWN)

THREAD_SORT_METHOD_LIST = (THREAD_SORT_METHOD_AGE, THREAD_SORT_METHOD_ACTIVITY, THREAD_SORT_METHOD_POSTS)

DEFAULT_THREAD_SORT_METHOD = THREAD_SORT_METHOD_ACTIVITY
DEFAULT_THREAD_SORT_DIR = THREAD_SORT_DIR_DOWN


POST_TYPE_THREAD_POST = 'answer'
POST_TYPE_COMMENT = 'comment'
POST_TYPE_QUESTION = 'question'
POST_TYPE_ORGANIZATION_DESCRIPTION = 'organization_description'
POST_TYPE_USER_DESCRIPTION = 'user_description'
POST_TYPE_REJECT_REASON = 'reject_reason'
POST_TYPE_NODE_DESCRIPTION = 'node_description'
POST_TYPE_DISCUSSION = 'discussion'
POST_TYPE_DOCUMENT = 'document'


POST_TYPES = (
    POST_TYPE_THREAD_POST,  # used in Questions (QA) module and Discussions (Forum) module as generic posts from users. Verbose name is Answer and Post respectively.
    POST_TYPE_COMMENT,  # used in Questions (QA) module for POST_TYPE_THREAD_POST comments
    POST_TYPE_QUESTION,  # used in Questions (QA) module as main post - the Question with Title saved in Thread
    POST_TYPE_ORGANIZATION_DESCRIPTION,
    POST_TYPE_USER_DESCRIPTION,
    POST_TYPE_REJECT_REASON,
    POST_TYPE_NODE_DESCRIPTION,
    POST_TYPE_DISCUSSION,  # used in Discussions module (Forum) as main post - the Discussion with Title saved in Thread
    POST_TYPE_DOCUMENT  # used in Documents module (Library) as main post - the Document with Title saved in Thread
)

SIMPLE_REPLY_SEPARATOR_TEMPLATE = '==== %s -=-=='

#values for SELF_NOTIFY_WHEN... settings use bits
NEVER = 'never'
FOR_FIRST_REVISION = 'first'
FOR_ANY_REVISION = 'any'
SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN_CHOICES = (
    (NEVER, _('Never')),
    (FOR_FIRST_REVISION, _('When new post is published')),
    (FOR_ANY_REVISION, _('When post is published or revised')),
)
#need more options for web posts b/c user is looking at the page
#when posting. when posts are made by email - user is not looking
#at the site and therefore won't get any feedback unless an email is sent back
#todo: rename INITIAL -> FIRST and make values of type string
#FOR_INITIAL_REVISION_WHEN_APPROVED = 1
#FOR_ANY_REVISION_WHEN_APPROVED = 2
#FOR_INITIAL_REVISION_ALWAYS = 3
#FOR_ANY_REVISION_ALWAYS = 4
#SELF_NOTIFY_WEB_POST_AUTHOR_WHEN_CHOICES = (
#    (NEVER, _('Never')),
#    (
#        FOR_INITIAL_REVISION_WHEN_APPROVED,
#        _('When inital revision is approved by moderator')
#    ),
#    (
#        FOR_ANY_REVISION_WHEN_APPROVED,
#        _('When any revision is approved by moderator')
#    ),
#    (
#        FOR_INITIAL_REVISION_ALWAYS,
#        _('Any time when inital revision is published')
#    ),
#    (
#        FOR_ANY_REVISION_ALWAYS,
#        _('Any time when revision is published')
#    )
#)

REPLY_SEPARATOR_TEMPLATE = '==== %(user_action)s %(instruction)s -=-=='
REPLY_WITH_COMMENT_TEMPLATE = _(
    'Note: to reply with a comment, '
    'please use <a href="mailto:%(addr)s?subject=%(subject)s">this link</a>'
)
REPLY_SEPARATOR_REGEX = re.compile(r'==== .* -=-==', re.MULTILINE | re.DOTALL)

ANSWER_SORT_METHODS = (  # no translations needed here
    'latest', 'oldest', 'votes'
)
#todo: add assertion here that all sort methods are unique
#because they are keys to the hash used in implementations
#of Q.run_advanced_search


THREAD_SCOPE_ALL = 'all'
THREAD_SCOPE_UNANSWERED = 'unanswered'
THREAD_SCOPE_FOLLOWED = 'followed'
THREAD_SCOPE_WITH_NO_ACCEPTED_ANSWER = 'with-no-accepted-answer'
THREAD_SCOPE_WITH_ACCEPTED_ANSWER = 'with-accepted-answer'

THREAD_SCOPE_LIST = (
    THREAD_SCOPE_ALL,
    THREAD_SCOPE_UNANSWERED,
    THREAD_SCOPE_FOLLOWED,
    THREAD_SCOPE_WITH_NO_ACCEPTED_ANSWER,
    THREAD_SCOPE_WITH_ACCEPTED_ANSWER
)

DEFAULT_THREAD_SCOPE = THREAD_SCOPE_ALL

TAG_LIST_FORMAT_CHOICES = (
    ('list', _('list')),
    ('cloud', _('cloud')),
)

PAGE_SIZE_CHOICES = (('10', '10',), ('30', '30',), ('50', '50',),)
ANSWERS_PAGE_SIZE = 20
QUESTIONS_PER_PAGE_USER_CHOICES = ((10, u'10'), (30, u'30'), (50, u'50'),)

#todo: implement this
#    ('NO_UPVOTED_ANSWERS',),
#)

#todo:
#this probably needs to be language-specific
#and selectable/changeable from the admin interface
#however it will be hard to expect that people will type
#correct regexes - plus this must be an anchored regex
#to do full string match
#IMPRTANT: tag related regexes must be portable between js and python
TAG_CHARS = r'\w+.#-'
TAG_REGEX_BARE = r'[%s]+' % TAG_CHARS
TAG_REGEX = r'^%s$' % TAG_REGEX_BARE
TAG_SPLIT_REGEX = r'[ ,]+'
TAG_SEP = ','  # has to be valid TAG_SPLIT_REGEX char and MUST NOT be in const.TAG_CHARS
#!!! see const.message_keys.TAG_WRONG_CHARS_MESSAGE
EMAIL_REGEX = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b', re.I)

TYPE_ACTIVITY_ASK_QUESTION = 1
TYPE_ACTIVITY_ANSWER = 2
TYPE_ACTIVITY_COMMENT_QUESTION = 3
TYPE_ACTIVITY_COMMENT_ANSWER = 4
TYPE_ACTIVITY_UPDATE_QUESTION = 5
TYPE_ACTIVITY_UPDATE_ANSWER = 6
TYPE_ACTIVITY_PRIZE = 7
TYPE_ACTIVITY_MARK_ANSWER = 8
TYPE_ACTIVITY_VOTE_UP = 9
TYPE_ACTIVITY_VOTE_DOWN = 10
TYPE_ACTIVITY_CANCEL_VOTE = 11
TYPE_ACTIVITY_DELETE_QUESTION = 12
TYPE_ACTIVITY_DELETE_ANSWER = 13
TYPE_ACTIVITY_MARK_OFFENSIVE = 14
TYPE_ACTIVITY_UPDATE_TAGS = 15
TYPE_ACTIVITY_FOLLOWED = 16
TYPE_ACTIVITY_USER_FULL_UPDATED = 17
TYPE_ACTIVITY_EMAIL_UPDATE_SENT = 18
TYPE_ACTIVITY_MENTION = 19
TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT = 20
TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT = 21
TYPE_ACTIVITY_CREATE_ORGANIZATION_DESCRIPTION = 22
TYPE_ACTIVITY_UPDATE_ORGANIZATION_DESCRIPTION = 23
TYPE_ACTIVITY_CREATE_REJECT_REASON = 26
TYPE_ACTIVITY_UPDATE_REJECT_REASON = 27
TYPE_ACTIVITY_VALIDATION_EMAIL_SENT = 28
TYPE_ACTIVITY_POST_SHARED = 29
TYPE_ACTIVITY_ASK_TO_JOIN_GROUP = 30
TYPE_ACTIVITY_CREATE_NODE_DESCRIPTION = 31
TYPE_ACTIVITY_UPDATE_NODE_DESCRIPTION = 32
TYPE_ACTIVITY_CREATE_DISCUSSION = 33
TYPE_ACTIVITY_UPDATE_DISCUSSION = 34
TYPE_ACTIVITY_CREATE_DOCUMENT = 35
TYPE_ACTIVITY_UPDATE_DOCUMENT = 36
TYPE_ACTIVITY_ASK_TO_JOIN_NODE = 37
TYPE_ACTIVITY_ASK_TO_CREATE_NODE = 38
#TYPE_ACTIVITY_EDIT_QUESTION = 17
#TYPE_ACTIVITY_EDIT_ANSWER = 18

#todo: rename this to TYPE_ACTIVITY_CHOICES
TYPE_ACTIVITY = (
    (TYPE_ACTIVITY_ASK_QUESTION, _('asked a question')),
    (TYPE_ACTIVITY_ANSWER, _('answered a question')),
    (TYPE_ACTIVITY_COMMENT_QUESTION, _('commented question')),
    (TYPE_ACTIVITY_COMMENT_ANSWER, _('commented answer')),
    (TYPE_ACTIVITY_UPDATE_QUESTION, _('edited question')),
    (TYPE_ACTIVITY_UPDATE_ANSWER, _('edited answer')),
    (TYPE_ACTIVITY_MARK_ANSWER, _('marked best answer')),
    (TYPE_ACTIVITY_VOTE_UP, _('upvoted')),
    (TYPE_ACTIVITY_VOTE_DOWN, _('downvoted')),
    (TYPE_ACTIVITY_CANCEL_VOTE, _('canceled vote')),
    (TYPE_ACTIVITY_DELETE_QUESTION, _('deleted question')),
    (TYPE_ACTIVITY_DELETE_ANSWER, _('deleted answer')),
    (TYPE_ACTIVITY_MARK_OFFENSIVE, _('marked offensive')),
    (TYPE_ACTIVITY_UPDATE_TAGS, _('updated tags')),
    (TYPE_ACTIVITY_FOLLOWED, _('selected followed')),
    (TYPE_ACTIVITY_USER_FULL_UPDATED, _('completed user profile')),
    (TYPE_ACTIVITY_EMAIL_UPDATE_SENT, _('email update sent to user')),
    (TYPE_ACTIVITY_POST_SHARED, _('a post was shared')),
    (TYPE_ACTIVITY_ASK_TO_JOIN_GROUP, _('user asks to join node')),
    (TYPE_ACTIVITY_ASK_TO_CREATE_NODE, _('user asks to create node')),
    (
        TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT,
        _('reminder about unanswered questions sent'),
    ),
    (
        TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT,
        _('reminder about accepting the best answer sent'),
    ),
    (TYPE_ACTIVITY_MENTION, _('mentioned in the post')),
    (
        TYPE_ACTIVITY_CREATE_ORGANIZATION_DESCRIPTION,
        _('created tag description'),
    ),
    (
        TYPE_ACTIVITY_UPDATE_ORGANIZATION_DESCRIPTION,
        _('updated tag description')
    ),
    (
        TYPE_ACTIVITY_CREATE_REJECT_REASON,
        _('created post reject reason'),
    ),
    (
        TYPE_ACTIVITY_UPDATE_REJECT_REASON,
        _('updated post reject reason')
    ),
    (
        TYPE_ACTIVITY_VALIDATION_EMAIL_SENT,
        'sent email address validation message'  # don't translate, internal
    ),
)


#MENTION activity is added implicitly, unfortunately
RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS = (
    TYPE_ACTIVITY_COMMENT_QUESTION,
    TYPE_ACTIVITY_COMMENT_ANSWER,
    TYPE_ACTIVITY_UPDATE_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_POST_SHARED
)


#the same as for instant notifications for now
#MENTION activity is added implicitly, unfortunately
RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY = (
    TYPE_ACTIVITY_ANSWER,
    TYPE_ACTIVITY_ASK_QUESTION,
    TYPE_ACTIVITY_COMMENT_QUESTION,
    TYPE_ACTIVITY_COMMENT_ANSWER,
    TYPE_ACTIVITY_UPDATE_ANSWER,
    TYPE_ACTIVITY_UPDATE_QUESTION,
    # TYPE_ACTIVITY_POST_SHARED,
#    TYPE_ACTIVITY_PRIZE,
#    TYPE_ACTIVITY_MARK_ANSWER,
#    TYPE_ACTIVITY_VOTE_UP,
#    TYPE_ACTIVITY_VOTE_DOWN,
#    TYPE_ACTIVITY_CANCEL_VOTE,
#    TYPE_ACTIVITY_DELETE_QUESTION,
#    TYPE_ACTIVITY_DELETE_ANSWER,
#    TYPE_ACTIVITY_MARK_OFFENSIVE,
#    TYPE_ACTIVITY_FOLLOWED,
)

RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES = {
    TYPE_ACTIVITY_COMMENT_QUESTION: 'question_comment',
    TYPE_ACTIVITY_COMMENT_ANSWER: 'answer_comment',
    TYPE_ACTIVITY_UPDATE_ANSWER: 'answer_update',
    TYPE_ACTIVITY_UPDATE_QUESTION: 'question_update',
    TYPE_ACTIVITY_ANSWER: 'new_answer',
    TYPE_ACTIVITY_ASK_QUESTION: 'new_question',
    TYPE_ACTIVITY_POST_SHARED: 'post_shared'
}

assert(
    set(RESPONSE_ACTIVITY_TYPES_FOR_INSTANT_NOTIFICATIONS) \
    == set(RESPONSE_ACTIVITY_TYPE_MAP_FOR_TEMPLATES.keys())
)

TYPE_RESPONSE = {
    'QUESTION_ANSWERED': _('answered question'),
    'QUESTION_COMMENTED': _('commented question'),
    'ANSWER_COMMENTED': _('commented answer'),
    'ANSWER_ACCEPTED': _('accepted answer'),
}

POST_STATUS = {
    'solved': _('SOLVED'),
    'closed': _('CLOSED'),
    'deleted': _('DELETED'),
    'default_version': _('initial version'),
    'retagged': _('retagged'),
    'private': _('[private]') # TODO DEPRECATED
}

#choices used in email and display filters
INCLUDE_ALL = 0
EXCLUDE_IGNORED = 1
INCLUDE_INTERESTING = 2
INCLUDE_SUBSCRIBED = 3
TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES = (
    (INCLUDE_ALL, _('show all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_INTERESTING, _('only interesting tags'))
)
TAG_DISPLAY_FILTER_STRATEGY_CHOICES = \
    TAG_DISPLAY_FILTER_STRATEGY_MINIMAL_CHOICES + \
    ((INCLUDE_SUBSCRIBED, _('only subscribed tags')),)


TAG_EMAIL_FILTER_STRATEGY_CHOICES = (
    (INCLUDE_ALL, _('email for all tags')),
    (EXCLUDE_IGNORED, _('exclude ignored tags')),
    (INCLUDE_INTERESTING, _('only subscribed tags')),
)

NOTIFICATION_DELIVERY_SCHEDULE_CHOICES = (
                            ('i', _('instantly')),
                            ('d', _('daily')),
                            ('w', _('weekly')),
                            ('n', _('no email')),
                        )

USERS_PAGE_SIZE = 28  # todo: move it to settings?
USERNAME_REGEX_STRING = r'^[\w \-.@+\']+$'

GRAVATAR_TYPE_CHOICES = (
                            ('identicon', _('identicon')),
                            ('mm', _('mystery-man')),
                            ('monsterid', _('monsterid')),
                            ('wavatar', _('wavatar')),
                            ('retro', _('retro')),
                        )

#chars that can go before or after @mention
TWITTER_STYLE_MENTION_TERMINATION_CHARS = '\n ;:,.!?<>"\''

COMMENT_HARD_MAX_LENGTH = 2048

#user status ch
USER_STATUS_CHOICES = (
        #in addition to these there is administrator
        #admin status is determined by the User.is_superuser() call
        ('m', _('moderator')),  # user with moderation privilege
        ('a', _('approved')),  # regular user
        ('w', _('watched')),  # regular user placed on the moderation watch
        ('s', _('suspended')),  # suspended user who cannot post new stuff
        ('b', _('blocked')),  # blocked
)
DEFAULT_USER_STATUS = 'w'

#number of items to show in user views
USER_VIEW_DATA_SIZE = 50

#not really dependency, but external links, which it would
#be nice to test for correctness from time to time
DEPENDENCY_URLS = {
    'akismet': 'https://akismet.com/signup/',
    'cc-by-sa': 'http://creativecommons.org/licenses/by-sa/3.0/legalcode',
    'embedding-video': \
        'http://openode.org/doc/optional-modules.html#embedding-video',
    'favicon': 'http://en.wikipedia.org/wiki/Favicon',
    'facebook-apps': 'http://www.facebook.com/developers/createapp.php',
    'google-webmaster-tools': 'https://www.google.com/webmasters/tools/home',
    'identica-apps': 'http://identi.ca/settings/oauthapps',
    'noscript': 'https://www.google.com/support/bin/answer.py?answer=23852',
    'linkedin-apps': 'https://www.linkedin.com/secure/developer',
    'mathjax': 'http://www.mathjax.org/resources/docs/?installation.html',
    'recaptcha': 'http://google.com/recaptcha',
    'twitter-apps': 'http://dev.twitter.com/apps/',
}

PASSWORD_MIN_LENGTH = 6

AVATAR_STATUS_CHOICE = (
    ('n', _('None')),
    ('g', _('Gravatar')),  # only if user has real uploaded gravatar
    ('a', _('Uploaded Avatar')),  # avatar uploaded locally - with django-avatar app
)

SEARCH_ORDER_BY = (
                    ('-added_at', _('date descendant')),
                    ('added_at', _('date ascendant')),
                    ('-last_activity_at', _('activity descendant')),
                    ('last_activity_at', _('activity ascendant')),
                    ('-answer_count', _('answers descendant')),
                    ('answer_count', _('answers ascendant')),
                    ('-points', _('votes descendant')),
                    ('points', _('votes ascendant')),
                  )

DEFAULT_QUESTION_WIDGET_STYLE = """
@import url('http://fonts.googleapis.com/css?family=Yanone+Kaffeesatz:300,400,700');
body {
    overflow: hidden;
}

#container {
    width: 200px;
    height: 350px;
}
ul {
    list-style: none;
    padding: 5px;
    margin: 5px;
}
li {
    border-bottom: #CCC 1px solid;
    padding-bottom: 5px;
    padding-top: 5px;
}
li:last-child {
    border: none;
}
a {
    text-decoration: none;
    color: #464646;
    font-family: 'Yanone Kaffeesatz', sans-serif;
    font-size: 15px;
}
"""

THREAD_TYPE_QUESTION = 'question'
THREAD_TYPE_DISCUSSION = 'discussion'
THREAD_TYPE_DOCUMENT = 'document'
THREAD_TYPES = (
    (THREAD_TYPE_QUESTION, _('question')),
    (THREAD_TYPE_DISCUSSION, _('discussion')),
    (THREAD_TYPE_DOCUMENT, _('document')),
)

NODE_MODULE_ANNOTATION = 'annotation'
NODE_MODULE_QA = 'qa'
NODE_MODULE_FORUM = 'forum'
NODE_MODULE_LIBRARY = 'library'
NODE_MODULES = (
    (NODE_MODULE_ANNOTATION, _('Annotation'), _(u'Annot.')),
    (NODE_MODULE_QA, _('Questions'), _(u'Q&As')),
    (NODE_MODULE_FORUM, _('Discussions'), _(u'Discu.')),
    (NODE_MODULE_LIBRARY, _('Documents'), _(u'Docs.'))
)

NODE_MODULE_CHOICES = [
    (m[0], m[1])
    for m in NODE_MODULES
]

# NODE_OPTIONAL_MODULE_CHOICES = [
#     (m[0], m[1])
#     for m in NODE_MODULES[1:]
# ]

NODE_STYLE_REGULAR = 'regular'
NODE_STYLE_CATEGORY = 'category'
NODE_STYLE = (
    (NODE_STYLE_REGULAR, _('Regular')),
    (NODE_STYLE_CATEGORY, _('Category')),
)

THREAD_TYPE_BY_NODE_MODULE = {
    NODE_MODULE_QA: THREAD_TYPE_QUESTION,
    NODE_MODULE_FORUM: THREAD_TYPE_DISCUSSION,
    NODE_MODULE_LIBRARY: THREAD_TYPE_DOCUMENT,
}

NODE_MODULE_BY_THREAD_TYPE = dict(zip(THREAD_TYPE_BY_NODE_MODULE.values(), THREAD_TYPE_BY_NODE_MODULE))

NODE_VISIBILITY_PUBLIC = 'public'
NODE_VISIBILITY_REGISTRED_USERS = 'registred-users'  # 'semi-public'
NODE_VISIBILITY_PRIVATE = 'private'
NODE_VISIBILITY_SEMIPRIVATE = 'semi-private'

NODE_VISIBILITY = (
    (NODE_VISIBILITY_PUBLIC, _('Public'), _('Node will be visible and accessible for everyone.')),
    (NODE_VISIBILITY_REGISTRED_USERS, _('Registered users'), _('Node will be visible and accessible only for registered users.')),
    (NODE_VISIBILITY_SEMIPRIVATE, u'%s – %s' % (_('Registered users'), _('Private')), _('Node will be visible for all registered users, but accessible only for node members, others may ask for access.')),
    (NODE_VISIBILITY_PRIVATE, _('Private'), _('Node will be visible and accessible only for node members disregarding user\'s role.')),
)

NODE_VISIBILITY_CHOICES = [(i, j) for i, j, k in NODE_VISIBILITY]

NODE_USER_ROLE_MEMBER = 'member'
NODE_USER_ROLE_DOCUMENT_MANAGER = 'document-manager'
NODE_USER_ROLE_READONLY = 'readonly'
NODE_USER_ROLE_MANAGER = 'manager'


NODE_USER_ROLES = (
    (NODE_USER_ROLE_MEMBER, _('Member')),
    (NODE_USER_ROLE_READONLY, u'%s – %s' % (_('Member'), _('Read only'))),
    (NODE_USER_ROLE_DOCUMENT_MANAGER, u'%s – %s' % (_('Member'), _('Document editor'))),
    (NODE_USER_ROLE_MANAGER, _('Manager')),
)

MAX_UNREAD_POSTS_COUNT = 10


LOG_ACTION_ASK_QUESTION = 1
LOG_ACTION_ANSWER = 2
LOG_ACTION_COMMENT_QUESTION = 3
LOG_ACTION_COMMENT_ANSWER = 4
LOG_ACTION_UPDATE_QUESTION = 5
LOG_ACTION_UPDATE_ANSWER = 6
LOG_ACTION_VOTE_UP = 9
LOG_ACTION_VOTE_DOWN = 10
LOG_ACTION_CANCEL_VOTE = 11
LOG_ACTION_DELETE_QUESTION = 12
LOG_ACTION_DELETE_ANSWER = 13
LOG_ACTION_MARK_OFFENSIVE = 14
LOG_ACTION_UPDATE_TAGS = 15
LOG_ACTION_FOLLOW_NODE = 16
LOG_ACTION_FOLLOW_QUESTION = 17
LOG_ACTION_FOLLOW_DISCUSSION = 18
# LOG_ACTION_FOLLOWED_DOCUMENT = 19  # user can not follow document
LOG_ACTION_UPDATE_USER = 20

LOG_ACTION_CREATE_ORGANIZATION_DESCRIPTION = 22
LOG_ACTION_UPDATE_ORGANIZATION_DESCRIPTION = 23

LOG_ACTION_CREATE_REJECT_REASON = 26
LOG_ACTION_UPDATE_REJECT_REASON = 27

LOG_ACTION_ASK_TO_JOIN_GROUP = 30
LOG_ACTION_CREATE_NODE_DESCRIPTION = 31
LOG_ACTION_UPDATE_NODE_DESCRIPTION = 32

LOG_ACTION_CREATE_DISCUSSION = 33
LOG_ACTION_UPDATE_DISCUSSION = 34

LOG_ACTION_CREATE_DOCUMENT = 35
LOG_ACTION_UPDATE_DOCUMENT = 36

LOG_ACTION_CHANGE_NODE_SETTINGS = 37
LOG_ACTION_CHANGE_NODE_MEMBER = 38
LOG_ACTION_CHANGE_NODE_PEREX = 39

LOG_ACTION_DISCUSSION_POST = 40
LOG_ACTION_UNFOLLOW_NODE = 41
LOG_ACTION_UNFOLLOW_QUESTION = 42
LOG_ACTION_UNFOLLOW_DISCUSSION = 43

LOG_ACTION_SUBSCRIBE_NODE = 44
LOG_ACTION_SUBSCRIBE_QUESTION = 45
LOG_ACTION_SUBSCRIBE_DISCUSSION = 46

LOG_ACTION_UNSUBSCRIBE_NODE = 47
LOG_ACTION_UNSUBSCRIBE_QUESTION = 48
LOG_ACTION_UNSUBSCRIBE_DISCUSSION = 49

LOG_ACTION_JOIN_GROUP = 50
LOG_ACTION_LEAVE_GROUP = 51
LOG_ACTION_CANCEL_ASK_TO_JOIN_GROUP = 52
LOG_ACTION_APPROVE_JOIN_GROUP = 53
LOG_ACTION_REFUSE_JOIN_GROUP = 54
LOG_ACTION_JOIN_NODE = 55
LOG_ACTION_APPROVE_JOIN_NODE = 56
LOG_ACTION_REFUSE_JOIN_NODE = 57
LOG_ACTION_SEND_EMAIL_TO_USER = 58

LOG_ACTION_ASK_TO_JOIN_NODE = 60
LOG_ACTION_DELETE_DOCUMENT = 61

LOG_ACTION_CLOSE_QUESTION = 70
LOG_ACTION_REOPEN_QUESTION = 71
LOG_ACTION_CLOSE_DISCUSSION = 72
LOG_ACTION_REOPEN_DISCUSSION = 73
LOG_ACTION_ADD_THREAD_CATEGORY = 74
LOG_ACTION_THREAD_CATEGORY_MOVE = 75
LOG_ACTION_THREAD_CATEGORY_EDIT = 76
LOG_ACTION_DOCUMENT_MOVE = 77
LOG_ACTION_ASK_TO_CREATE_NODE = 78
LOG_ACTION_ASK_TO_CREATE_NODE_ACCEPTED = 79
LOG_ACTION_ASK_TO_CREATE_NODE_DECLINED = 80



LOG_ACTIONS = (
    (LOG_ACTION_ASK_QUESTION, _('asked question')),
    (LOG_ACTION_ANSWER, _('answer question')),
    (LOG_ACTION_COMMENT_QUESTION, _('comment question')),
    (LOG_ACTION_CLOSE_QUESTION, _('close question')),
    (LOG_ACTION_REOPEN_QUESTION, _('reopen question')),
    (LOG_ACTION_COMMENT_ANSWER, _('comment answer')),
    (LOG_ACTION_UPDATE_QUESTION, _('update question')),
    (LOG_ACTION_UPDATE_ANSWER, _('update answer')),
    (LOG_ACTION_VOTE_UP, _('vote up')),
    (LOG_ACTION_VOTE_DOWN, _('vote down')),
    (LOG_ACTION_CANCEL_VOTE, _('cancel vote')),
    (LOG_ACTION_DELETE_QUESTION, _('delete question')),
    (LOG_ACTION_DELETE_ANSWER, _('delete answer')),
    (LOG_ACTION_MARK_OFFENSIVE, _('mark offensive')),
    (LOG_ACTION_UPDATE_TAGS, _('update tags')),
    (LOG_ACTION_FOLLOW_NODE, _('follow node')),
    (LOG_ACTION_FOLLOW_QUESTION, _('follow question')),
    (LOG_ACTION_FOLLOW_DISCUSSION, _('follow discussion')),
    (LOG_ACTION_UPDATE_USER, _('update user')),

    (LOG_ACTION_CLOSE_DISCUSSION, _('discussion close')),
    (LOG_ACTION_REOPEN_DISCUSSION, _('discussion reopen')),

    (LOG_ACTION_CREATE_ORGANIZATION_DESCRIPTION, _('create organization description')),
    (LOG_ACTION_UPDATE_ORGANIZATION_DESCRIPTION, _('update organization description')),

    (LOG_ACTION_CREATE_REJECT_REASON, _('create organization description')),
    (LOG_ACTION_UPDATE_REJECT_REASON, _('update reject reason')),

    (LOG_ACTION_ASK_TO_JOIN_GROUP, _('ask to join group')),
    (LOG_ACTION_CREATE_NODE_DESCRIPTION, _('create node description')),
    (LOG_ACTION_UPDATE_NODE_DESCRIPTION, _('update node description')),

    (LOG_ACTION_CREATE_DISCUSSION, _('create discussion')),
    (LOG_ACTION_UPDATE_DISCUSSION, _('update discussion')),

    (LOG_ACTION_CREATE_DOCUMENT, _('create document')),
    (LOG_ACTION_UPDATE_DOCUMENT, _('update document')),
    (LOG_ACTION_ADD_THREAD_CATEGORY, _('add thread category')),
    (LOG_ACTION_THREAD_CATEGORY_MOVE, _('thread category move')),
    (LOG_ACTION_THREAD_CATEGORY_EDIT, _('thread category edit')),
    (LOG_ACTION_DOCUMENT_MOVE, _('document move')),

    (LOG_ACTION_CHANGE_NODE_SETTINGS, _('change node settings')),
    (LOG_ACTION_CHANGE_NODE_MEMBER, _('change node member')),
    (LOG_ACTION_CHANGE_NODE_PEREX, _('change node perex')),

    (LOG_ACTION_DISCUSSION_POST, _('discussion post')),
    (LOG_ACTION_UNFOLLOW_NODE, _('unfollow node')),
    (LOG_ACTION_UNFOLLOW_QUESTION, _('unfollow question')),
    (LOG_ACTION_UNFOLLOW_DISCUSSION, _('unfollow discussion')),

    (LOG_ACTION_SUBSCRIBE_NODE, _('subscribe node')),
    (LOG_ACTION_SUBSCRIBE_QUESTION, _('subscribe question')),
    (LOG_ACTION_SUBSCRIBE_DISCUSSION, _('subscribe discussion')),

    (LOG_ACTION_UNSUBSCRIBE_NODE, _('unsubscribe node')),
    (LOG_ACTION_UNSUBSCRIBE_QUESTION, _('unsubscribe question')),
    (LOG_ACTION_UNSUBSCRIBE_DISCUSSION, _('unsubscribe discussion')),

    (LOG_ACTION_JOIN_GROUP, _('join group')),
    (LOG_ACTION_LEAVE_GROUP, _('leave group')),
    (LOG_ACTION_CANCEL_ASK_TO_JOIN_GROUP, _('cancel ask to join group')),
    (LOG_ACTION_APPROVE_JOIN_GROUP, _('approve joining group')),
    (LOG_ACTION_REFUSE_JOIN_GROUP, _('refuse joining group')),
    (LOG_ACTION_JOIN_NODE, _('join node')),
    (LOG_ACTION_APPROVE_JOIN_NODE, _('approve joining node')),
    (LOG_ACTION_REFUSE_JOIN_NODE, _('refuse joining node')),
    (LOG_ACTION_SEND_EMAIL_TO_USER, _('send email to user')),
    (LOG_ACTION_ASK_TO_JOIN_NODE, _('ask to join node')),
    (LOG_ACTION_ASK_TO_CREATE_NODE, _('ask to create node')),
    (LOG_ACTION_ASK_TO_CREATE_NODE_ACCEPTED, _('agreed to create node')),
    (LOG_ACTION_ASK_TO_CREATE_NODE_DECLINED, _('declined to create node')),
)


#an exception import * because that file has only strings
from openode.const.message_keys import *
from openode.const.perm_rules import *
