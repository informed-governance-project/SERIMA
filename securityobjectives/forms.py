from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from incidents.forms import DropdownCheckboxSelectMultiple

from .models import StandardAnswer


class SecurityObjectiveAnswerForm(forms.Form):
    is_implemented = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "so-input-field",
            }
        ),
    )
    justification = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "",
                "class": "so-input-field",
            }
        ),
    )
    review_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "",
                "class": "so-input-field",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", None)
        super().__init__(*args, **kwargs)

        def set_readonly(field_name):
            field = self.fields[field_name]
            field_classes = field.widget.attrs.get("class", "")
            field.widget.attrs.update({"class": f"{field_classes} readonly_field"})
            field.disabled = True

        if initial:
            is_readonly = initial.get("is_readonly", True)
            is_regulator = initial.get("is_regulator", True)
            has_review_comment = initial.get("has_review_comment", False)

            if is_readonly or is_regulator:
                set_readonly("is_implemented")
                set_readonly("justification")

            if is_readonly or (has_review_comment and not is_regulator):
                set_readonly("review_comment")
            elif not is_regulator:
                self.fields["review_comment"].widget = forms.HiddenInput()
                self.initial["review_comment"] = None


class SecurityObjectiveStatusForm(forms.Form):
    ALL_FAIL = "ALL_FAIL"
    ALL_PASS = "ALL_PASS"

    status = forms.ChoiceField(
        required=False,
        choices=[
            ("NOT_REVIEWED", _("Not reviewed")),
            ("PASS", _("Passed")),
            ("FAIL", _("Revision required")),
            ("ALL_PASS", _("All passed")),
            ("ALL_FAIL", _("All revision required")),
        ],
        widget=forms.Select(
            attrs={
                "class": "so_status_form so-input-field",
            }
        ),
    )

    actions = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "so_actions_form so-input-field",
                "placeholder": "",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", None)
        super().__init__(*args, **kwargs)

        def set_readonly(field_name):
            field = self.fields[field_name]
            field_classes = field.widget.attrs.get("class", "")
            field.widget.attrs.update({"class": f"{field_classes} readonly_field"})
            field.disabled = True

        if initial:
            is_readonly = initial.get("is_readonly", True)
            is_regulator = initial.get("is_regulator", True)
            current_classes = self.fields["status"].widget.attrs.get("class", "")
            new_classes = current_classes

            if is_readonly:
                set_readonly("status")
                set_readonly("actions")

            if is_regulator:
                set_readonly("actions")

            if initial["status"] == "PASS":
                new_classes = f"{current_classes} text-white bg-passed"

            if initial["status"] == "FAIL":
                new_classes = f"{current_classes} text-white bg-failed"

            self.fields["status"].widget.attrs.update(
                {"class": new_classes},
            )


class SelectSOStandardForm(forms.Form):
    so_standard = forms.ChoiceField(
        widget=forms.Select(),
        required=True,
        label=_("Evaluation Framework"),
    )

    year = forms.ChoiceField(
        widget=forms.Select(),
        choices=[(year, year) for year in range(timezone.now().year - 3, timezone.now().year + 2)],
        required=True,
        initial=timezone.now().year,
        label=_("Year"),
    )
    sectors = forms.MultipleChoiceField(
        required=True,
        widget=DropdownCheckboxSelectMultiple(attrs={"data-selected-text-format": "count > 3"}),
        label=_("Sectors"),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", None)
        super().__init__(*args, **kwargs)
        if initial:
            self.fields["so_standard"].choices = initial["standard_list"]
            self.fields["sectors"].choices = initial["sectors_list"]
        else:
            self.fields["so_standard"].disabled = True
            self.fields["year"].disabled = True
            self.fields["sectors"].disabled = True


class ImportSOForm(forms.Form):
    import_file = forms.FileField(
        required=True,
    )

    standard = forms.ChoiceField(
        widget=forms.Select(),
        required=True,
        label=_("Evaluation Framework"),
    )

    company = forms.ChoiceField(
        widget=forms.Select(),
        required=True,
        label=_("Company"),
    )

    year = forms.ChoiceField(
        widget=forms.Select(),
        choices=[(year, year) for year in range(timezone.now().year - 3, timezone.now().year + 2)],
        required=True,
        initial=timezone.now().year,
        label=_("Year"),
    )

    sectors = forms.MultipleChoiceField(
        required=True,
        widget=DropdownCheckboxSelectMultiple(attrs={"data-selected-text-format": "count > 3"}),
        label=_("Sectors"),
    )

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop("choices", {})
        super().__init__(*args, **kwargs)

        if choices.get("standard") and choices.get("company") and choices.get("sectors"):
            self.fields["standard"].choices = choices["standard"]
            self.fields["company"].choices = choices["company"]
            self.fields["sectors"].choices = choices["sectors"]
        else:
            for field_name in ["standard", "company", "year", "sectors"]:
                self.fields[field_name].disabled = True


class CopySOForm(forms.Form):
    year = forms.ChoiceField(
        widget=forms.Select(),
        choices=[(year, year) for year in range(timezone.now().year - 3, timezone.now().year + 2)],
        required=True,
        initial=timezone.now().year,
        label=_("Year"),
    )

    sectors = forms.MultipleChoiceField(
        required=True,
        widget=DropdownCheckboxSelectMultiple(attrs={"data-selected-text-format": "count > 3"}),
        label=_("Sectors"),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", None)
        super().__init__(*args, **kwargs)
        if initial["sectors"]:
            self.fields["sectors"].choices = initial["sectors"]
        else:
            self.fields["year"].disabled = True
            self.fields["sectors"].disabled = True


class ReviewForm(forms.ModelForm):
    class Meta:
        model = StandardAnswer
        fields = ["review_comment", "status"]
        widgets = {
            "review_comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "summernote",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", None)
        is_only_review_comment = kwargs.pop("is_only_review_comment", False)
        super().__init__(*args, **kwargs)
        self.fields["review_comment"].required = True
        self.fields["status"].required = False
        self.fields["status"].disabled = True
        self.is_only_review_comment = False
        self.is_read_only = False

        if initial:
            current_classes = self.fields["status"].widget.attrs.get("class", "")
            is_read_only = initial.get("is_readonly", True)
            self.is_read_only = is_read_only
            self.fields["review_comment"].disabled = is_read_only
            new_classes = f"{current_classes} fw-bolder text-white"

            if initial["status"] == "PASSM":
                initial["status"] = "PASS"
                self.initial["status"] = "PASS"

            if initial["status"] == "FAILM":
                initial["status"] = "FAIL"
                self.initial["status"] = "FAIL"

            if initial["status"] == "PASS":
                new_classes = f"{new_classes} bg-passed"

            if initial["status"] == "FAIL":
                new_classes = f"{new_classes} bg-failed"

            self.fields["status"].widget.attrs.update(
                {"class": new_classes},
            )

        if is_only_review_comment and not is_read_only:
            self.is_only_review_comment = True
            self.fields["status"].widget = forms.HiddenInput()

    def clean_status(self):
        status = self.cleaned_data.get("status")
        if status not in ["PASS", "FAIL"] and not self.is_only_review_comment:
            raise forms.ValidationError("Status must be either PASS or FAIL.")
        return status
