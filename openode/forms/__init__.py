# -*- coding: utf-8 -*-

"""Forms, custom form fields and related utility functions
used in Openode"""

import re
import urllib

from django import forms
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from django.utils.translation import ugettext_lazy as _, ungettext_lazy, string_concat
from django.utils.html import strip_tags
from django_countries import countries
from mptt.forms import TreeNodeChoiceField
from recaptcha_works.fields import RecaptchaField

from openode import const
from openode.const import message_keys
from openode.conf import settings as openode_settings, get_tag_display_filter_strategy_choices
from openode.forms.fields import WysiwygFormField
from openode.forms.widgets import Wysiwyg
from openode.mail import extract_first_email_address
from openode.utils.url_utils import reverse_lazy

from openode.utils.forms import NextUrlField

import logging


def clean_login_url(url):
    """
    pass through, unless next parameter would go to
        logout or sign in page
    because it make no sense to do so, when we want to login"""
    # dependate on authopenid
    if url in (reverse('user_signout'), reverse('logout'), reverse('user_signin')):
        return reverse('index')
    return urllib.quote(url.encode("utf-8"))


def cleanup_dict(dictionary, key, empty_value):
    """deletes key from dictionary if it exists
    and the corresponding value equals the empty_value
    """
    if key in dictionary and dictionary[key] == empty_value:
        del dictionary[key]


def format_form_errors(form):
    """Formats form errors in HTML
    if there is only one error - returns a plain string
    if more than one, returns an unordered list of errors
    in HTML format.
    If there are no errors, returns empty string
    """
    if form.errors:
        errors = form.errors.values()
        if len(errors) == 1:
            return errors[0]
        else:
            result = '<ul>'
            for error in errors:
                result += '<li>%s</li>' % error
            result += '</ul>'
            return result
    else:
        return ''


def clean_marked_tagnames(tagnames):
    """return two strings - one containing tagnames
    that are straight names of tags, and the second one
    containing names of wildcard tags,
    wildcard tags are those that have an asterisk at the end
    the function does not verify that the tag names are valid
    """
    if openode_settings.USE_WILDCARD_TAGS is False:
        return tagnames, list()

    pure_tags = list()
    wildcards = list()
    for tagname in tagnames:
        if tagname == '':
            continue
        if tagname.endswith('*'):
            if tagname.count('*') > 1:
                continue
            else:
                wildcards.append(tagname)
        else:
            pure_tags.append(tagname)

    return pure_tags, wildcards


def filter_choices(remove_choices=None, from_choices=None):
    """a utility function that will remove choice tuples
    usable for the forms.ChoicesField from
    ``from_choices``, the removed ones will be those given
    by the ``remove_choice`` list

    there is no error checking, ``from_choices`` tuple must be as expected
    to work with the forms.ChoicesField
    """

    if not isinstance(remove_choices, list):
        raise TypeError('remove_choices must be a list')

    filtered_choices = tuple()
    for choice_to_test in from_choices:
        remove = False
        for choice in remove_choices:
            if choice == choice_to_test[0]:
                remove = True
                break
        if remove is False:
            filtered_choices += (choice_to_test, )

    return filtered_choices


COUNTRY_CHOICES = (('unknown', _('select country')),) + countries.COUNTRIES


class CountryField(forms.ChoiceField):
    """this is better placed into the django_coutries app"""

    def __init__(self, *args, **kwargs):
        """sets label and the country choices
        """
        kwargs['choices'] = kwargs.pop('choices', COUNTRY_CHOICES)
        kwargs['label'] = kwargs.pop('label', _('Country'))
        super(CountryField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """Handles case of 'unknown' country selection
        """
        if self.required:
            if value == 'unknown':
                raise forms.ValidationError(_('Country field is required'))
        if value == 'unknown':
            return None
        return value


class CountedWordsField(forms.CharField):
    """a field where a number of words is expected
    to be in a certain range"""

    def __init__(
        self, min_words=0, max_words=9999, field_name=None,
        *args, **kwargs
    ):
        self.min_words = min_words
        self.max_words = max_words
        self.field_name = field_name
        super(CountedWordsField, self).__init__(*args, **kwargs)

    def clean(self, value):
        #todo: this field must be adapted to work with Chinese, etc.
        #for that we'll have to count characters instead of words
        if value is None:
            value = ''

        value = value.strip()

        word_count = len(value.split())
        if word_count < self.min_words:
            msg = ungettext_lazy(
                'must be > %d word',
                'must be > %d words',
                self.min_words - 1
            ) % (self.min_words - 1)
            #todo - space is not used in Chinese
            raise forms.ValidationError(
                string_concat(self.field_name, ' ', msg)
            )

        if word_count > self.max_words:
            msg = ungettext_lazy(
                'must be < %d word',
                'must be < %d words',
                self.max_words + 1
            ) % (self.max_words + 1)
            raise forms.ValidationError(
                string_concat(self.field_name, ' ', msg)
            )
        return value


class DomainNameField(forms.CharField):
    """Field for Internet Domain Names
    todo: maybe there is a standard field for this?
    """

    def is_valid_hostname(self, hostname):
        """
            http://stackoverflow.com/a/2532344/291667
        """
        if len(hostname) > 255:
            return False
        if hostname[-1:] == ".":
            hostname = hostname[:-1]  # strip exactly one dot from the right, if present
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in hostname.split("."))

    def clean(self, value):
        if self.is_valid_hostname(value):
            return value
        raise forms.ValidationError(
            '%s is not a valid domain name' % value
        )


class TitleField(forms.CharField):
    """Fild receiving question title"""
    def __init__(self, *args, **kwargs):
        super(TitleField, self).__init__(*args, **kwargs)
        self.required = kwargs.get('required', True)
        self.widget = forms.TextInput(
                            attrs={'size': 70, 'autocomplete': 'off'}
                        )
        self.max_length = 255
        self.label = _('title')
        self.help_text = _(
            'please enter a descriptive title for your question'
        )
        self.initial = ''

    def clean(self, value):
        """cleans the field for minimum and maximum length
        also is supposed to work for unicode non-ascii characters"""
        if value is None:
            value = ''
        if len(value) < openode_settings.MIN_TITLE_LENGTH:
            msg = ungettext_lazy(
                'title must be > %d character',
                'title must be > %d characters',
                openode_settings.MIN_TITLE_LENGTH
            ) % openode_settings.MIN_TITLE_LENGTH
            raise forms.ValidationError(msg)
        encoded_value = value.encode('utf-8')
        if len(value) == len(encoded_value):
            if len(value) > self.max_length:
                raise forms.ValidationError(
                    _(
                        'The title is too long, maximum allowed size is '
                        '%d characters'
                    ) % self.max_length
                )
        elif len(encoded_value) > self.max_length:
            raise forms.ValidationError(
                _(
                    'The title is too long, maximum allowed size is '
                    '%d bytes'
                ) % self.max_length
            )

        return value.strip()  # TODO: test me


class EditorField(WysiwygFormField):
    """EditorField is subclassed by the
    :class:`QuestionEditorField` and :class:`AnswerEditorField`
    """
    length_error_template_singular = 'post content must be > %d character',
    length_error_template_plural = 'post content must be > %d characters',
    min_length = 10  # sentinel default value

    def __init__(self, *args, **kwargs):
        super(EditorField, self).__init__(*args, **kwargs)
        self.required = True
        self.label = _('content')
        self.help_text = u''
        self.initial = ''

    def clean(self, value):

        if value is None:
            value = ''

        if len(strip_tags(value.strip())) < self.min_length:
            msg = ungettext_lazy(
                self.length_error_template_singular,
                self.length_error_template_plural,
                self.min_length
            ) % self.min_length
            raise forms.ValidationError(msg)
        return value


class QuestionEditorField(EditorField):
    """Editor field for the questions"""

    def __init__(self, *args, **kwargs):
        super(QuestionEditorField, self).__init__(*args, **kwargs)
        self.length_error_template_singular = _('Question body must be > %d character')
        self.length_error_template_plural = _('Question body must be > %d characters')
        self.min_length = openode_settings.MIN_QUESTION_BODY_LENGTH


class AnswerEditorField(EditorField):
    """Editor field for answers"""

    def __init__(self, *args, **kwargs):
        super(AnswerEditorField, self).__init__(*args, **kwargs)
        self.length_error_template_singular = _('Text must be at least %d character long.')
        self.length_error_template_plural = _('Text must be at least %d characters long.')
        self.min_length = kwargs.get("min_length", openode_settings.MIN_ANSWER_BODY_LENGTH)


def clean_tag(tag_name):
    """a function that cleans a single tag name"""
    tag_length = len(tag_name)
    if tag_length > openode_settings.MAX_TAG_LENGTH:
        #singular form is odd in english, but required for pluralization
        #in other languages
        msg = ungettext_lazy(
            #odd but added for completeness
            _('Each tag must be shorter than %(max_chars)d character.'),
            _('Each tag must be shorter than %(max_chars)d characters.'),
            tag_length
        ) % {
            'max_chars': openode_settings.MAX_TAG_LENGTH
        }
        raise forms.ValidationError(msg)

    #todo - this needs to come from settings
    if tag_length > 0:
        tagname_re = re.compile(const.TAG_REGEX, re.UNICODE)
        if not tagname_re.search(tag_name):
            raise forms.ValidationError(
                _(message_keys.TAG_WRONG_CHARS_MESSAGE)
            )

        if openode_settings.FORCE_LOWERCASE_TAGS:
            #a simpler way to handle tags - just lowercase thew all
            return tag_name.lower()
        else:
            try:
                from openode import models
                stored_tag = models.Tag.objects.get(name__iexact=tag_name)
                return stored_tag.name
            except models.Tag.DoesNotExist:
                return tag_name
    else:
        return ''


class TagNamesField(forms.CharField):
    """field that receives Openode tag names"""

    def __init__(self, *args, **kwargs):
        super(TagNamesField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'}
        )
        self.max_length = 255
        self.error_messages['max_length'] = _(
                            'We ran out of space for recording the tags. '
                            'Please shorten or delete some of them.'
                        )
        self.label = _('tags')
        self.help_text = ungettext_lazy(
            'Tags are short keywords, with no spaces within. '
            'Up to %(max_tags)d tag can be used.',
            'Tags are short keywords, with no spaces within. '
            'Up to %(max_tags)d tags can be used.',
            openode_settings.MAX_TAGS_PER_POST
        ) % {'max_tags': openode_settings.MAX_TAGS_PER_POST}
        self.initial = ''

    def clean(self, value):
        from openode import models
        value = super(TagNamesField, self).clean(value)
        data = value.strip()
        split_re = re.compile(const.TAG_SPLIT_REGEX)
        tag_strings = split_re.split(data)
        # entered_tags = []
        tag_count = len(tag_strings)
        if tag_count > openode_settings.MAX_TAGS_PER_POST:
            max_tags = openode_settings.MAX_TAGS_PER_POST
            msg = ungettext_lazy(
                        'please use %(tag_count)d tag or less',
                        'please use %(tag_count)d tags or less',
                        tag_count) % {'tag_count': max_tags}
            raise forms.ValidationError(msg)

        cleaned_entered_tags = list()
        for tag in tag_strings:
            cleaned_tag = clean_tag(tag)
            if cleaned_tag not in cleaned_entered_tags:
                cleaned_entered_tags.append(clean_tag(tag))

        result = u' '.join(cleaned_entered_tags)

        if len(result) > 125:  # magic number!, the same as max_length in db
            raise forms.ValidationError(self.error_messages['max_length'])

        return u' '.join(cleaned_entered_tags)


class EmailNotifyField(forms.BooleanField):
    """Rendered as checkbox which turns on
    email notifications on the post"""
    def __init__(self, *args, **kwargs):
        super(EmailNotifyField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget.attrs['class'] = 'nomargin'


class SummaryField(forms.CharField):

    def __init__(self, *args, **kwargs):
        super(SummaryField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'}
        )
        self.max_length = 300
        self.label = _('update summary:')
        self.help_text = _(
            'enter a brief summary of your revision (e.g. '
            'fixed spelling, grammar, improved style, this '
            'field is optional)'
        )


class CleanCharField(forms.CharField):
    def to_python(self, value):
        return super(CleanCharField, self).to_python(value).strip()


class EditorForm(forms.Form):
    """form with one field - `editor`
    the field must be created dynamically, so it's added
    in the __init__() function"""

    def __init__(self, editor_attrs=None):
        super(EditorForm, self).__init__()
        editor_attrs = editor_attrs or {}
        self.fields['editor'] = EditorField(editor_attrs=editor_attrs)


class DumpUploadForm(forms.Form):
    """This form handles importing
    data into the forum. At the moment it only
    supports stackexchange import.
    """
    dump_file = forms.FileField()


class ShowQuestionForm(forms.Form):
    """Cleans data necessary to access answers and comments
    by the respective comment or answer id - necessary
    when comments would be normally wrapped and/or displayed
    on the page other than the first page of answers to a question.
    Same for the answers that are shown on the later pages.
    """
    answer = forms.IntegerField(required=False)
    comment = forms.IntegerField(required=False)
    page = forms.IntegerField(required=False)
    sort = forms.CharField(required=False)

    def __init__(self, data, default_sort_method):
        super(ShowQuestionForm, self).__init__(data)
        self.default_sort_method = default_sort_method

    def get_pruned_data(self):
        nones = ('answer', 'comment', 'page')
        for key in nones:
            if key in self.cleaned_data:
                if self.cleaned_data[key] is None:
                    del self.cleaned_data[key]
        if 'sort' in self.cleaned_data:
            if self.cleaned_data['sort'] == '':
                del self.cleaned_data['sort']
        return self.cleaned_data

    def clean(self):
        """this form must always be valid
        should use defaults if the data is incomplete
        or invalid"""
        if self._errors:
            #since the form is always valid, clear the errors
            logging.error(unicode(self._errors))
            self._errors = {}

        in_data = self.get_pruned_data()
        out_data = dict()
        if ('answer' in in_data) ^ ('comment' in in_data):
            out_data['show_page'] = None
            out_data['answer_sort_method'] = self.default_sort_method
            out_data['show_comment'] = in_data.get('comment', None)
            out_data['show_answer'] = in_data.get('answer', None)
        else:
            out_data['show_page'] = in_data.get('page', 1)
            out_data['answer_sort_method'] = in_data.get(
                                                    'sort',
                                                    self.default_sort_method
                                                )
            out_data['show_comment'] = None
            out_data['show_answer'] = None
        self.cleaned_data = out_data
        return out_data


class SendMessageForm(forms.Form):
    subject_line = forms.CharField(
                        label=_('Subject line'),
                        max_length=64,
                        widget=forms.TextInput(attrs={'size': 64}, )
                    )
    body_text = forms.CharField(
                            label=_('Message text'),
                            max_length=1600,
                            widget=forms.Textarea(attrs={'cols': 64})
                        )


class NotARobotForm(forms.Form):
    recaptcha = RecaptchaField(
                    private_key=openode_settings.RECAPTCHA_SECRET,
                    public_key=openode_settings.RECAPTCHA_KEY
                )


class FeedbackForm(forms.Form):
    name = forms.CharField(label=_('Your name (optional):'), required=False)
    email = forms.EmailField(label=_('Email:'), required=False)
    message = forms.CharField(
        label=_('Your message:'),
        max_length=800,
        widget=forms.Textarea(attrs={'cols': 60})
    )
    no_email = forms.BooleanField(
        label=_("I don't want to give my email or receive a response:"),
        required=False
    )
    next = NextUrlField()

    def __init__(self, is_auth=False, *args, **kwargs):
        super(FeedbackForm, self).__init__(*args, **kwargs)
        self.is_auth = is_auth
        if not is_auth:
            if openode_settings.USE_RECAPTCHA:
                self._add_recaptcha_field()

    def _add_recaptcha_field(self):
        self.fields['recaptcha'] = RecaptchaField(
                            private_key=openode_settings.RECAPTCHA_SECRET,
                            public_key=openode_settings.RECAPTCHA_KEY
                        )

    def clean(self):
        super(FeedbackForm, self).clean()
        if not self.is_auth:
            if not self.cleaned_data['no_email'] \
                and not self.cleaned_data['email']:
                msg = _('Please mark "I dont want to give my mail" field.')
                self._errors['email'] = self.error_class([msg])

        return self.cleaned_data


class FormWithHideableFields(object):
    """allows to swap a field widget to HiddenInput() and back"""

    def hide_field(self, name):
        """replace widget with HiddenInput()
        and save the original in the __hidden_fields dictionary
        """
        if not hasattr(self, '__hidden_fields'):
            self.__hidden_fields = dict()
        if name in self.__hidden_fields:
            return
        self.__hidden_fields[name] = self.fields[name].widget
        self.fields[name].widget = forms.HiddenInput()

    def show_field(self, name):
        """restore the original widget on the field
        if it was previously hidden
        """
        if name in self.__hidden_fields:
            self.fields[name] = self.__hidden_fields.pop(name)


class DraftQuestionForm(forms.Form):
    """No real validation required for this form"""
    title = forms.CharField(required=False)
    text = forms.CharField(required=False)
    tagnames = forms.CharField(required=False)


class DraftAnswerForm(forms.Form):
    """Only thread_id is required"""
    thread_id = forms.IntegerField()
    text = forms.CharField(required=False)


class AskForm(forms.Form):
    """the form used to openode questions
    field ask_anonymously is shown to the user if the
    if ALLOW_ASK_ANONYMOUSLY live setting is True
    however, for simplicity, the value will always be present
    in the cleaned data, and will evaluate to False if the
    settings forbids anonymous asking
    """
    title = TitleField()
    text = WysiwygFormField(
        widget=Wysiwyg(
            mode="full"
            )
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.node = kwargs.pop('node')
        allow_tags = kwargs.pop("allow_tags", True)

        super(AskForm, self).__init__(*args, **kwargs)

        if allow_tags and self.user.has_perm('openode.change_tag'):
            self.fields['tags'] = TagNamesField()

        self.fields["text"].widget = Wysiwyg(
            mode="full",
            upload_url=reverse_lazy("upload_attachment_node", args=[self.node.pk])
        )


class QuestionAddForm(AskForm):
    def __init__(self, *args, **kwargs):
        super(QuestionAddForm, self).__init__(*args, **kwargs)
        self.fields["text"].min_length = openode_settings.MIN_ANSWER_BODY_LENGTH


class DocumentAddForm(AskForm):
    pass


class DiscussionAddForm(AskForm):
    """the form used to openode questions
    field ask_anonymously is shown to the user if the
    if ALLOW_ASK_ANONYMOUSLY live setting is True
    however, for simplicity, the value will always be present
    in the cleaned data, and will evaluate to False if the
    settings forbids anonymous asking
    """
    text = WysiwygFormField(widget=Wysiwyg(), required=False)


ASK_BY_EMAIL_SUBJECT_HELP = _(
    'Subject line is expected in the format: '
    '[tag1, tag2, tag3,...] question title'
)


class AskByEmailForm(forms.Form):
    """:class:`~openode.forms.AskByEmailForm`
    validates question data, where question was posted
    by email.

    It is ivoked by the management command
    :mod:`~openode.management.commands.post_emailed_questions`

    Input is text data with attributes:

    * :attr:`~openode.forms.AskByEmailForm.sender` - unparsed "from" data
    * :attr:`~openode.forms.AskByEmailForm.subject` - subject line
    * :attr:`~openode.forms.AskByEmailForm.body_text` - body text of the email

    Cleaned values are:
    * ``email`` - email address
    * ``title`` - question title
    * ``tagnames`` - tag names all in one string
    * ``body_text`` - body of question text -
      a pass-through, no extra validation
    """
    sender = forms.CharField(max_length=255)
    subject = forms.CharField(
        max_length=255,
        error_messages={
            'required': ASK_BY_EMAIL_SUBJECT_HELP
        }
    )
    body_text = QuestionEditorField()

    def clean_sender(self):
        """Cleans the :attr:`~openode.forms.AskByEmail.sender` attribute

        If the field is valid, cleaned data will receive value ``email``
        """
        raw_email = self.cleaned_data['sender']
        email = extract_first_email_address(raw_email)
        if email is None:
            raise forms.ValidationError('Could not extract email address')
        self.cleaned_data['email'] = email
        return self.cleaned_data['sender']

    def clean_subject(self):
        """Cleans the :attr:`~openode.forms.AskByEmail.subject` attribute

        If the field is valid, cleaned data will receive values
        ``tagnames`` and ``title``
        """
        raw_subject = self.cleaned_data['subject'].strip()

        subject_re = re.compile(r'^(?:\[([^]]+)\])?(.*)$')
        match = subject_re.match(raw_subject)
        if match:
            #make raw tags comma-separated
            if match.group(1) is None:  # no tags
                self.cleaned_data['tagnames'] = ''
            else:
                tagnames = match.group(1).replace(';', ',')

                #pre-process tags
                tag_list = [tag.strip() for tag in tagnames.split(',')]
                tag_list = [re.sub(r'\s+', ' ', tag) for tag in tag_list]

                if openode_settings.REPLACE_SPACE_WITH_DASH_IN_EMAILED_TAGS:
                    tag_list = [tag.replace(' ', '-') for tag in tag_list]
                #todo: use tag separator char here
                tagnames = ' '.join(tag_list)

                #clean tags - may raise ValidationError
                self.cleaned_data['tagnames'] = TagNamesField().clean(tagnames)

            #clean title - may raise ValidationError
            title = match.group(2).strip()
            self.cleaned_data['title'] = TitleField().clean(title)
        else:
            raise forms.ValidationError(ASK_BY_EMAIL_SUBJECT_HELP)
        return self.cleaned_data['subject']


class AnswerForm(forms.Form):
    text = AnswerEditorField(widget=Wysiwyg())
    email_notify = EmailNotifyField(initial=False)

    def __init__(self, *args, **kwargs):

        self.node = kwargs.pop("node")

        super(AnswerForm, self).__init__(*args, **kwargs)
        self.fields['email_notify'].widget.attrs['id'] = 'question-subscribe-updates'

        self.fields["text"].min_length = openode_settings.MIN_ANSWER_BODY_LENGTH
        self.fields["text"].widget = Wysiwyg(
            mode="full",
            upload_url=reverse_lazy("upload_attachment_node", args=[self.node.pk])
        )


class VoteForm(forms.Form):
    """form used in ajax vote view (only comment_upvote so far)
    """
    post_id = forms.IntegerField()
    # char because it is 'true' or 'false' as string
    cancel_vote = forms.CharField()

    def clean_cancel_vote(self):
        val = self.cleaned_data['cancel_vote']
        if val == 'true':
            result = True
        elif val == 'false':
            result = False
        else:
            del self.cleaned_data['cancel_vote']
            raise forms.ValidationError(
                    'either "true" or "false" strings expected'
                )
        self.cleaned_data['cancel_vote'] = result
        return self.cleaned_data['cancel_vote']


class CloseForm(forms.Form):
    """
        close thread with reason
    """
    reason = forms.CharField(widget=forms.Textarea, label=_(u"Reason"))


class RetagQuestionForm(forms.Form):
    tags = TagNamesField()

    def __init__(self, question, *args, **kwargs):
        """initialize the default values"""
        super(RetagQuestionForm, self).__init__(*args, **kwargs)
        self.fields['tags'].initial = question.thread.tagnames


class RevisionForm(forms.Form):
    """
    Lists revisions of a Question or Answer
    """
    revision = forms.ChoiceField(
        widget=forms.Select(
            attrs={'style': 'width:100%'}
        )
    )

    def __init__(self, post, latest_revision, *args, **kwargs):
        super(RevisionForm, self).__init__(*args, **kwargs)
        revisions = post.revisions.values_list(
            'revision', 'author__username', 'revised_at', 'summary'
        )
        date_format = '%c'
        rev_choices = list()
        for r in revisions:
            rev_details = u'%s - %s (%s) %s' % (
                r[0], r[1], r[2].strftime(date_format), r[3]
            )
            rev_choices.append((r[0], rev_details))

        self.fields['revision'].choices = rev_choices
        self.fields['revision'].initial = latest_revision.revision


class EditQuestionForm(forms.Form):
    title = TitleField()
    summary = SummaryField()

    #todo: this is odd that this form takes question as an argument
    def __init__(self, *args, **kwargs):
        """populate EditQuestionForm with initial data"""
        self.main_post = kwargs.pop('main_post')
        self.user = kwargs.pop('user')  # preserve for superclass
        revision = kwargs.pop('revision')
        self.node = kwargs.pop('node')

        text_required = kwargs.pop("text_required", True)

        super(EditQuestionForm, self).__init__(*args, **kwargs)
        #it is important to add this field dynamically

        self.fields['text'] = WysiwygFormField()
        self.fields['text'].widget = Wysiwyg(
            mode="full",
            upload_url=reverse_lazy("upload_attachment_node", args=[self.node.pk])
            )
        self.fields['text'].initial = revision.text
        self.fields['text'].required = text_required

        # TODO: use Thread.can_retag method
        if self.user.has_perm('openode.change_tag'):
            self.fields['tags'] = TagNamesField()
            self.fields['tags'].initial = revision.tagnames

        self.fields['title'].initial = revision.title

        self.fields['allow_external_access'] = forms.BooleanField(
            label=_('Allow external access'),
            initial=self.main_post.thread.external_access,
            required=False
        )

        self.fields["category"] = TreeNodeChoiceField(
            queryset=self.main_post.thread.node.thread_categories.all(),
            initial=self.main_post.thread.category,
            required=False,
        )

    def has_changed(self):
        if super(EditQuestionForm, self).has_changed():
            return True


class EditAnswerForm(forms.Form):
    summary = SummaryField()

    def __init__(self, answer, revision, *args, **kwargs):
        self.answer = answer
        super(EditAnswerForm, self).__init__(*args, **kwargs)
        #it is important to add this field dynamically

        self.fields['text'] = WysiwygFormField(min_length=openode_settings.MIN_ANSWER_BODY_LENGTH)
        self.fields['text'].widget = Wysiwyg(
            mode="full",
            upload_url=reverse_lazy("upload_attachment_node", args=[self.answer.thread.node.pk])
            )

        self.fields['text'].initial = revision.text

    def has_changed(self):
        #todo: this function is almost copy/paste of EditQuestionForm.has_changed()
        if super(EditAnswerForm, self).has_changed():
            return True


class EditOrganizationDescriptionForm(forms.Form):
    text = forms.CharField(required=False)
    tag_id = forms.IntegerField()


class TagFilterSelectionForm(forms.ModelForm):
    email_tag_filter_strategy = forms.ChoiceField(
        initial=const.EXCLUDE_IGNORED,
        label=_('Choose email tag filter'),
        widget=forms.RadioSelect
    )

    def __init__(self, *args, **kwargs):
        super(TagFilterSelectionForm, self).__init__(*args, **kwargs)
        choices = get_tag_display_filter_strategy_choices()
        self.fields['email_tag_filter_strategy'].choices = choices

    class Meta:
        model = User
        fields = ('email_tag_filter_strategy',)

    def save(self):
        before = self.instance.email_tag_filter_strategy
        super(TagFilterSelectionForm, self).save()
        after = self.instance.email_tag_filter_strategy
        if before != after:
            return True
        return False


class EmailFeedSettingField(forms.ChoiceField):
    def __init__(self, *arg, **kwarg):
        kwarg['choices'] = const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES
        kwarg['widget'] = forms.RadioSelect
        super(EmailFeedSettingField, self).__init__(*arg, **kwarg)


class EditUserEmailFeedsForm(forms.Form):
    FORM_TO_MODEL_MAP = {
        'all_questions': 'q_all',
        'asked_by_me': 'q_ask',
        'answered_by_me': 'q_ans',
        'individually_selected': 'q_sel',
        'mentions_and_comments': 'm_and_c',
    }
    NO_EMAIL_INITIAL = {
        'all_questions': 'n',
        'asked_by_me': 'n',
        'answered_by_me': 'n',
        'individually_selected': 'n',
        'mentions_and_comments': 'n',
    }
    INSTANT_EMAIL_INITIAL = {
        'all_questions': 'i',
        'asked_by_me': 'i',
        'answered_by_me': 'i',
        'individually_selected': 'i',
        'mentions_and_comments': 'i',
    }

    asked_by_me = EmailFeedSettingField(
        label=_('Asked by me')
    )
    answered_by_me = EmailFeedSettingField(
        label=_('Answered by me')
    )
    individually_selected = EmailFeedSettingField(
        label=_('Individually selected')
    )
    all_questions = EmailFeedSettingField(
        label=_('Entire forum (tag filtered)'),
    )

    mentions_and_comments = EmailFeedSettingField(
        label=_('Comments and posts mentioning me'),
    )

    def set_initial_values(self, user=None):
        from openode import models
        KEY_MAP = dict([(v, k) for k, v in self.FORM_TO_MODEL_MAP.iteritems()])
        if user is not None:
            settings = models.EmailFeedSetting.objects.filter(subscriber=user)
            initial_values = {}
            for setting in settings:
                feed_type = setting.feed_type
                form_field = KEY_MAP[feed_type]
                frequency = setting.frequency
                initial_values[form_field] = frequency
            self.initial = initial_values
        return self

    def reset(self):
        """equivalent to set_frequency('n')
        but also returns self due to some legacy requirement
        todo: clean up use of this function
        """
        if self.is_bound:
            self.cleaned_data = self.NO_EMAIL_INITIAL
        self.initial = self.NO_EMAIL_INITIAL
        return self

    def get_db_model_subscription_type_names(self):
        """todo: refactor this - too hacky
        should probably use model form instead

        returns list of values acceptable in
        ``attr::models.user.EmailFeedSetting.feed_type``
        """
        return self.FORM_TO_MODEL_MAP.values()

    def set_frequency(self, frequency='n'):
        data = {
            'all_questions': frequency,
            'asked_by_me': frequency,
            'answered_by_me': frequency,
            'individually_selected': frequency,
            'mentions_and_comments': frequency
        }
        if self.is_bound:
            self.cleaned_data = data
        self.initial = data

    def save(self, user, save_unbound=False):
        """with save_unbound==True will bypass form
        validation and save initial values
        """
        from openode import models
        changed = False
        for form_field, feed_type in self.FORM_TO_MODEL_MAP.items():
            s, created = models.EmailFeedSetting.objects.get_or_create(
                                                    subscriber=user,
                                                    feed_type=feed_type
                                                )
            if save_unbound:
                #just save initial values instead
                if form_field in self.initial:
                    new_value = self.initial[form_field]
                else:
                    new_value = self.fields[form_field].initial
            else:
                new_value = self.cleaned_data[form_field]
            if s.frequency != new_value:
                s.frequency = new_value
                s.save()
                changed = True
            else:
                if created:
                    s.save()
            if form_field == 'individually_selected':
                user.followed_threads.clear()
        return changed


class SubscribeForEmailUpdatesField(forms.ChoiceField):
    """a simple yes or no field to subscribe for email or not"""
    def __init__(self, **kwargs):
        kwargs['widget'] = forms.widgets.RadioSelect
        kwargs['error_messages'] = {
            'required': _('please choose one of the options above')
        }
        kwargs['choices'] = (
            ('y', _('okay, let\'s try!')),
            (
                'n',
                _('no %(sitename)s email please, thanks')
                    % {'sitename': openode_settings.APP_SHORT_NAME}
            )
        )
        super(SubscribeForEmailUpdatesField, self).__init__(**kwargs)


class SimpleEmailSubscribeForm(forms.Form):
    subscribe = SubscribeForEmailUpdatesField()

    def save(self, user=None):
        EFF = EditUserEmailFeedsForm
        #here we have kind of an anomaly - the value 'y' is redundant
        #with the frequency variable - needs to be fixed
        if self.is_bound and self.cleaned_data['subscribe'] == 'y':
            email_settings_form = EFF()
            email_settings_form.set_initial_values(user)
            logging.debug('%s wants to subscribe' % user.username)
        else:
            email_settings_form = EFF(initial=EFF.NO_EMAIL_INITIAL)
        email_settings_form.save(user, save_unbound=True)


class OrganizationLogoURLForm(forms.Form):
    """form for saving organization logo url"""
    organization_id = forms.IntegerField()
    image_url = forms.CharField()


class EditOrganizationMembershipForm(forms.Form):
    """a form for adding or removing users
    to and from user organizations"""
    user_id = forms.IntegerField()
    organization_name = forms.CharField()
    action = forms.CharField()

    def clean_action(self):
        """allowed actions are 'add' and 'remove'"""
        action = self.cleaned_data['action']
        if action not in ('add', 'remove'):
            del self.cleaned_data['action']
            raise forms.ValidationError('invalid action')
        return action


class EditRejectReasonForm(forms.Form):
    reason_id = forms.IntegerField(required=False)
    title = CountedWordsField(
        min_words=1, max_words=4, field_name=_('Title')
    )
    details = CountedWordsField(
        min_words=6, field_name=_('Description')
    )


class ModerateTagForm(forms.Form):
    tag_id = forms.IntegerField()
    thread_id = forms.IntegerField(required=False)
    action = forms.CharField()

    def clean_action(self):
        action = self.cleaned_data['action']
        assert(action in ('accept', 'reject'))
        return action


class ShareQuestionForm(forms.Form):
    thread_id = forms.IntegerField()
    recipient_name = forms.CharField()


def thread_add_form_factory(thread_type):
    if thread_type == 'question':
        return QuestionAddForm
    elif thread_type == 'discussion':
        return DiscussionAddForm
    elif thread_type == 'document':
        return DocumentAddForm
