# -*- coding: utf-8 -*-

from mptt.forms import TreeNodeChoiceField, TreeNodePositionField

from django import forms
from django.utils.translation import ugettext as _

from openode.forms.widgets import Wysiwyg
from openode.models import Node
from openode.models.fields import WysiwygField
from openode.utils.url_utils import reverse_lazy

################################################################################
# BASIC
################################################################################


class BaseModelForm(forms.ModelForm):
    """
    Base model forms class
    """
    pass


class BaseAdminModelForm(BaseModelForm):
    """
    Base model admin form
    """

    @classmethod
    def formfield_for_dbfield(cls, ff_callback, db_field, **kwargs):
        """
        Hook for overriding formfield creation
        """

        # enable Wysiwyg for admin
        if isinstance(db_field, WysiwygField) and not 'widget' in kwargs:
            kwargs['widget'] = Wysiwyg

        formfield = ff_callback(db_field, **kwargs)

        # remove "+" function from formfield widget
        if hasattr(formfield, 'widget'):
            formfield.widget.can_add_related = False

        return formfield

################################################################################
################################################################################


class BaseMoveForm(BaseAdminModelForm):
    """
    Administration form for moving mptt objects in parent-hierarchy
    """

    class Meta:
        fields = ()

    def __init__(self, *args, **kwargs):
        super(BaseMoveForm, self).__init__(*args, **kwargs)
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

        self.fields['target'] = TreeNodeChoiceField(
            queryset=self._meta.model._tree_manager.exclude(
                tree_id=self.instance.tree_id,
                lft__gte=self.instance.lft,
                rght__lte=self.instance.rght
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
# ADMIN FORMS
################################################################################


class NodeMoveForm(BaseMoveForm):
    """
    Administration form for moving Category in parent-hierarchy
    """

    class Meta:
        model = Node
        fields = ()


class NodeAdminForm(BaseAdminModelForm):

    class Meta:
        model = Node

    def __init__(self, *args, **kwargs):
        """
            overwrite default simple wysiwyg
        """
        super(NodeAdminForm, self).__init__(*args, **kwargs)

        widget_attrs = {
            "mode": "full",
            "width": "800px",
        }

        if self.instance.pk:
            widget_attrs.update({
                "upload_url": reverse_lazy("upload_attachment_node", args=[self.instance.pk])
            })

        for key in Node.WYSIWYG_FIELDS:
            self.fields[key].widget = Wysiwyg(**widget_attrs)

    def clean_deleted(self):
        # do something that validates your data
        if self.instance:
            if self.cleaned_data["deleted"]:
                if self.instance.get_descendants().filter(deleted=False).exists():
                    raise forms.ValidationError(_("All descendants of this node must be deleted first."))
            else:
                if self.instance.get_ancestors().filter(deleted=True).exists():
                    raise forms.ValidationError(_("All ancestors of this node must not deleted."))
        return self.cleaned_data["deleted"]
