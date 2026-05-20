from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.translation import gettext_lazy as _

from .helpers import (
    user_in_group,
)


class CompanyUserInlineFormset(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.user and user_in_group(self.user, "RegulatorUser"):
            has_admin = False
            for form in self.forms:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    if form.cleaned_data.get("is_company_administrator"):
                        has_admin = True

            if not has_admin:
                raise ValidationError(_("There must be at least one administrator user."))
