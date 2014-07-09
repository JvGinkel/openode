# -*- coding: utf-8 -*-

import datetime
import os

from django import forms
from django.utils.translation import ugettext as _

from openode.const import THREAD_TYPE_DOCUMENT
from openode.document.models import Document, DocumentRevision  # , Page
from openode.forms.admin import BaseMoveForm
from openode.models import Thread, Node
from openode.models.thread import ThreadCategory
from openode.utils.path import sanitize_file_name

from mptt.forms import TreeNodeChoiceField

from openode.forms import AskForm

#######################################


class DocumentModelForm(forms.ModelForm):
    class Meta:
        model = Document


class DocumentFileForm(forms.Form):
    file_data = forms.FileField(required=False)
    remove = forms.BooleanField(required=False)

    def clean(self):
        cl_data = super(DocumentFileForm, self).clean()
        try:
            _file = cl_data["file_data"]
        except KeyError:
            raise forms.ValidationError(_("Selected file is empty. Please choose another one."))
        else:
            if not (cl_data["remove"] or _file):
                self._errors["file_data"] = self.error_class([_(u"You must add new document or remove old.")])
                del cl_data["remove"]
                del cl_data["file_data"]
        return cl_data


class DocumentForm(AskForm):
    file_data = forms.FileField(required=False)
    thread_category = TreeNodeChoiceField(queryset=ThreadCategory.objects.none(), required=False)
    allow_external_access = forms.BooleanField(required=False)

    def clean(self):
        try:
            _file = self.cleaned_data["file_data"]
        except KeyError:
            raise forms.ValidationError(_("Selected file is empty. Please choose another one."))
        file_name = _file.name if _file else None

        if file_name:

            # change length of file_name by Thread title max_length
            file_name = file_name[:Thread._meta.get_field_by_name("title")[0].max_length]

            self.cleaned_data.setdefault("title", file_name)
            if "title" in self.errors:
                del self.errors["title"]

            self.cleaned_data.setdefault("text", "")
            if "text" in self.errors:
                del self.errors["text"]

        return super(DocumentForm, self).clean()

    def __init__(self, *args, **kwargs):
        kwargs["allow_tags"] = False
        super(DocumentForm, self).__init__(*args, **kwargs)
        self.fields["thread_category"].queryset = self.node.thread_categories.all()
        self.fields["text"].required = False


class DocumentRevisionModelForm(forms.ModelForm):
    """
        DEPRECATED

        form for creating DocumentRevision with connect to Document > Article > Node environment
    """

    title = forms.CharField(max_length=255)
    node = forms.ModelChoiceField(queryset=Node.objects.all(),
        widget=forms.HiddenInput()
        )
    thread_category = TreeNodeChoiceField(queryset=ThreadCategory.objects.all(), required=False)

    class Meta:
        model = DocumentRevision
        fields = (
            "title",
            "file_data",
        )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.document = kwargs.pop("document", None)
        node = kwargs.pop("node")
        super(DocumentRevisionModelForm, self).__init__(*args, **kwargs)
        self.fields["thread_category"].queryset = node.thread_categories.all()

    def clean_file_data(self):
        if not (self.instance.pk or self.cleaned_data["file_data"]):
            raise forms.ValidationError("This field is required")
        return self.cleaned_data["file_data"]

    def save(self, *args, **kwargs):

        """
            TODO
        """

        user = self.request.user

        if not self.document:

            thread = Thread.objects.create_new(
                self.cleaned_data["title"],
                user,
                datetime.datetime.now(),
                "",  # text
                tagnames="",
                thread_type=THREAD_TYPE_DOCUMENT,
                node=self.cleaned_data["node"],
            )
            thread.category = self.cleaned_data["thread_category"]
            thread.save()

            self.document = Document.objects.create(
                author=user,
                thread=thread
            )
        else:
            thread = self.instance.document.thread

            if thread.title != self.cleaned_data["title"]:
                thread.title = self.cleaned_data["title"]
                thread.save()

        # save document revision

        file_data = self.cleaned_data["file_data"] or self.instance.file_data

        # TODO document revision
        parsed_file_name = os.path.splitext(file_data.name)
        file_name = parsed_file_name[0].lower()
        suffix = parsed_file_name[1].replace(".", "").lower()

        self.instance.pk = None
        self.instance.uuid = None
        self.instance.revision = None

        self.instance.original_filename = file_name
        self.instance.suffix = suffix
        self.instance.filename_slug = sanitize_file_name(file_name)
        self.instance.document = self.document
        self.instance.author = user
        return super(DocumentRevisionModelForm, self).save(*args, **kwargs)

#######################################


class EditThreadCategoryForm(BaseMoveForm):
    """
        edit category name and/or tree structure of this category
    """

    class Meta:
        model = ThreadCategory
        fields = ("name", )

    def __init__(self, *args, **kwargs):
        super(EditThreadCategoryForm, self).__init__(*args, **kwargs)

        help_text = _(u"Fill only if you want to change current position")

        self.fields["position"].required = False
        self.fields["position"].choices.insert(0, ("", "-------"))
        self.fields["position"].help_text = help_text

        # moving is enabled only in actual tree
        self.fields["target"] = self.fields["target"].__class__(
            queryset=self._meta.model._tree_manager.filter(
                node__id=self.instance.node_id,
            ).exclude(
                lft__gte=self.instance.lft,
                rght__lte=self.instance.rght
            ),
            label=self.fields["target"].label,
            required=False,
            help_text=help_text
        )

    def clean(self):
        cl_data = self.cleaned_data

        if not(bool(cl_data["target"]) is bool(cl_data["position"])):
            msg = _(u"For move in tree must be both fields filled.")
            self._errors["target"] = self.error_class([msg])
            self._errors["position"] = self.error_class([msg])
            del cl_data["target"]
            del cl_data["position"]

        return cl_data

    def save(self, commit=True):
        """
        Move self.instance node to selected 'position' relative to 'target'
        """
        cl_data = self.cleaned_data

        if cl_data["target"] and cl_data["position"]:
            return super(EditThreadCategoryForm, self).save(commit=commit)
        elif commit:
            self.instance.save()
        return self.instance


class AddThreadCategoryForm(forms.ModelForm):
    """
        add category with tree structure
    """

    class Meta:
        model = ThreadCategory
        fields = ("name", "parent", "node")
        widgets = {
            'node': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        node = kwargs.pop("node")
        super(AddThreadCategoryForm, self).__init__(*args, **kwargs)

        # set queryset to node's categories
        qs = node.thread_categories.all()

        # exclude subnodes of instance from queryset
        if self.instance.pk:
            qs = qs.exclude(
                tree_id=self.instance.tree_id,
                lft__gte=self.instance.lft,
                rght__lte=self.instance.rght
            )

        self.fields["parent"].queryset = qs


from mptt.forms import TreeNodeChoiceField, TreeNodePositionField


class CategoryMoveForm(forms.ModelForm):

    class Meta:
        model = ThreadCategory
        fields = ()

    def __init__(self, *args, **kwargs):
        super(CategoryMoveForm, self).__init__(*args, **kwargs)

        self.fields['position'] = TreeNodePositionField(
            choices=(
                (TreeNodePositionField.LEFT, _(u'predecessor')),
                (TreeNodePositionField.RIGHT, _(u'successor')),
                (TreeNodePositionField.FIRST_CHILD, _(u'first child')),
                (TreeNodePositionField.LAST_CHILD, _(u'latest child')),
            ),
            label=_(u'Position of this item is'),
            required=True,
            )

        print self.instance.node

        self.fields['target'] = TreeNodeChoiceField(
            queryset=self._meta.model._tree_manager.filter(
                node=self.instance.node
            ).exclude(
                tree_id=self.instance.tree_id,
                lft__gte=self.instance.lft,
                rght__lte=self.instance.rght,
            ),
            label=u"of item",
        )

    def save(self, commit=True):
        """
        Move self.instance node to selected 'position' relative to 'target'
        """
        cl_data = self.cleaned_data
        self.instance.move_to(
            cl_data['target'],
            position=cl_data['position']
        )
        if commit:
            self.instance.save()
        return self.instance

################################################################################

class DownloadZipForm(forms.Form):
    documents_ids = forms.CharField()
