from django import forms
from django.conf import settings
from django.forms import modelformset_factory
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.forms import TranslatableModelForm

from governanceplatform.helpers import get_sectors_grouped
from governanceplatform.models import Regulation, Sector
from incidents.forms import DropdownCheckboxSelectMultiple
from securityobjectives.models import Standard

from .models import (
    CompanyProject,
    CompanyReporting,
    ObservationRecommendation,
    ObservationRecommendationThrough,
    Project,
    Template,
)


class ImportRiskAnalysisForm(forms.Form):
    import_file = forms.FileField(
        widget=forms.FileInput(attrs={"accept": ".json"}),
        required=True,
        label=_("JSON File"),
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

        if choices.get("company") and choices.get("sectors"):
            self.fields["company"].choices = choices["company"]
            self.fields["sectors"].choices = choices["sectors"]
        else:
            for field_name in ["company", "year", "sectors"]:
                self.fields[field_name].disabled = True


class RecommendationsSelectForm(TranslatableModelForm):
    selected = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "recommendation-select-checkbox"}),
    )

    class Meta:
        model = ObservationRecommendation
        fields = ["id", "selected", "code", "description", "sectors"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["sectors"].required = False


RecommendationsSelectFormSet = modelformset_factory(ObservationRecommendation, form=RecommendationsSelectForm, extra=0)


class ReviewCommentForm(forms.ModelForm):
    class Meta:
        model = CompanyReporting
        fields = ["id", "comment"]


class ObservationRecommendationOrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["order"].widget.attrs = {
            "class": "reporting-input-field",
            "data-recommendation-id": self.instance.pk,
        }

    class Meta:
        model = ObservationRecommendationThrough
        fields = ["order"]


class TemplateAdminForm(forms.ModelForm):
    template_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={"accept": ".docx"}),
    )

    class Meta:
        model = Template
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        languages_choices = [(code, _(name)) for code, name in settings.LANGUAGES]

        self.fields["language"] = forms.ChoiceField(choices=languages_choices)

    def clean_template_file(self):
        file = self.cleaned_data.get("template_file")
        if isinstance(file, (memoryview, bytes)):
            return bytes(file)
        if file:
            if not file.name.endswith(".docx"):
                raise forms.ValidationError(_("Only .docx files are allowed."))
            return file.read()
        existing = self.instance.template_file
        if existing:
            return bytes(existing)
        return None


class CreateProjectForm(forms.ModelForm):
    name = forms.CharField(
        required=True,
        label=_("Project name"),
    )

    regulation = forms.ModelChoiceField(
        queryset=Regulation.objects.none(),
        required=True,
        label=_("Regulation"),
    )

    standard = forms.ModelChoiceField(
        queryset=Standard.objects.none(),
        required=True,
        label=_("Standard"),
    )

    reference_year = forms.ChoiceField(
        choices=[(year, year) for year in range(timezone.now().year - 4, timezone.now().year + 1)][::-1],
        required=True,
        label=_("Base year"),
    )

    years = forms.MultipleChoiceField(
        widget=DropdownCheckboxSelectMultiple(),
        choices=[(year, year) for year in range(timezone.now().year - 20, timezone.now().year)][::-1],
        required=False,
        label=_("Comparison years"),
    )

    sectors = forms.MultipleChoiceField(
        required=True,
        widget=DropdownCheckboxSelectMultiple(),
        label=_("Sectors"),
    )

    selected_languages = forms.MultipleChoiceField(
        required=True,
        widget=DropdownCheckboxSelectMultiple(),
        label=_("Languages"),
    )

    class Meta:
        model = Project
        fields = [
            "name",
            "regulation",
            "standard",
            "reference_year",
            "years",
            "sectors",
            "top_ranking",
            "threshold_for_high_risk",
            "selected_file_format",
            "selected_languages",
        ]

    def clean_years(self):
        data = self.cleaned_data["years"]
        # convert str to int
        return [int(y) for y in data]

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop("choices", {})
        is_copy = kwargs.pop("is_copy", False)
        super().__init__(*args, **kwargs)

        languages_choices = [(code, _(name)) for code, name in settings.LANGUAGES]

        self.fields["selected_languages"].choices = languages_choices

        regulation_qs = choices.get("regulations", Regulation.objects.all())
        standard_qs = choices.get("standards", Standard.objects.all())
        sector_choices = get_sectors_grouped(Sector.objects.all())

        self.fields["regulation"].queryset = regulation_qs
        self.fields["standard"].queryset = standard_qs
        self.fields["sectors"].choices = sector_choices

        if self.instance and self.instance.pk:
            project = self.instance

            self.initial["regulation"] = project.standard.regulation
            self.initial["standard"] = project.standard

            # M2M sectors
            self.initial["sectors"] = list(project.sectors.values_list("id", flat=True))

            if is_copy:
                disabled_fields = [
                    "regulation",
                    "standard",
                    "reference_year",
                    "years",
                    "sectors",
                    "top_ranking",
                    "threshold_for_high_risk",
                    "selected_file_format",
                    "selected_languages",
                ]
            else:
                disabled_fields = ["regulation", "standard"]

            for field_name in disabled_fields:
                self.fields[field_name].disabled = True


class CompanyProjectDashboard(forms.ModelForm):
    class Meta:
        model = CompanyProject
        fields = [
            "is_selected",
            "statistic_selected",
            "governance_report_selected",
        ]
        widgets = {
            "is_selected": forms.CheckboxInput(),
            "statistic_selected": forms.CheckboxInput(),
            "governance_report_selected": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company_project_id = self.instance.pk if self.instance else None

        if self.instance and not self.instance.has_security_objectives or not self.instance.has_risk_assessment:
            self.fields["is_selected"].widget.attrs["disabled"] = True
            self.fields["statistic_selected"].widget.attrs["disabled"] = True
            self.fields["governance_report_selected"].widget.attrs["disabled"] = True

        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "company-project-input",
                    "data-company-project-id": company_project_id,
                }
            )
