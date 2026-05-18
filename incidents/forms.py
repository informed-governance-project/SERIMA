from datetime import datetime, timedelta
from types import SimpleNamespace

import pytz
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.widgets import ChoiceWidget
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from parler.widgets import SortedCheckboxSelectMultiple

from governanceplatform.helpers import (
    get_active_company_from_session,
    is_user_regulator,
)
from governanceplatform.models import Regulation, Regulator, Sector, Service
from governanceplatform.settings import TIME_ZONE

from .globals import REGIONAL_AREA
from .helpers import get_workflow_categories
from .models import (
    Answer,
    Impact,
    Incident,
    IncidentWorkflow,
    QuestionOptions,
    QuestionOptionsHistory,
    ReportTimeline,
    SectorRegulation,
    Workflow,
)
from .widgets import TempusDominusV6Widget


# TO DO: change the templates to custom one
class ServicesListCheckboxSelectMultiple(ChoiceWidget):
    allow_multiple_selected = True
    input_type = "checkbox"
    template_name = "django/forms/widgets/service_checkbox_select.html"
    option_template_name = "django/forms/widgets/service_checkbox_option.html"
    add_id_index = False
    checked_attribute = {"checked": True}
    option_inherits_attrs = True
    initial_data = None

    def __init__(self, *args, **kwargs):
        if "initial" in kwargs:
            self.initial_data = kwargs.pop("initial")
        super().__init__(*args, **kwargs)

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label) in enumerate(self.choices):
            cleaned_value = option_value or ""
            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = cleaned_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(cleaned_value, option_label)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel in choices:
                selected = (not has_selected or self.allow_multiple_selected) and str(subvalue) in value
                has_selected |= selected
                # manage default value
                if self.initial_data is not None:
                    if subvalue in self.initial_data:
                        selected = True

                subgroup.append(
                    self.create_option(
                        name,
                        subvalue,
                        sublabel,
                        selected,
                        index,
                        subindex=subindex,
                        attrs=attrs,
                    )
                )

                if subindex is not None:
                    subindex += 1
        return groups


class DropdownCheckboxSelectMultiple(ChoiceWidget):
    allow_multiple_selected = True
    input_type = "select"
    template_name = "django/forms/widgets/dropdown_checkbox_select.html"
    option_template_name = "django/forms/widgets/dropdown_checkbox_option.html"
    option_inherits_attrs = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# Class for Multichoice and single choice
# TO DO : improve layout
class OtherCheckboxSelectMultiple(ChoiceWidget):
    allow_multiple_selected = True
    input_type = "checkbox"
    template_name = "django/forms/widgets/other_checkbox_select.html"
    option_template_name = "django/forms/widgets/other_checkbox_option.html"

    def __init__(self, *args, **kwargs):
        if "input_type" in kwargs:
            self.input_type = kwargs.pop("input_type")
        super().__init__(*args, **kwargs)

    # this is the standard optgroups function, just add a hook to add new input
    # and modify the CSS class
    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label) in enumerate(self.choices):
            cleaned_value = option_value or ""
            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = cleaned_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(cleaned_value, option_label)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel in choices:
                selected = (not has_selected or self.allow_multiple_selected) and str(subvalue) in value
                has_selected |= selected

                subgroup.append(
                    self.create_option(
                        name,
                        subvalue,
                        sublabel,
                        selected,
                        index,
                        subindex=subindex,
                        attrs=attrs,
                    )
                )

                if subindex is not None:
                    subindex += 1
        return groups


# create a form for each category and add fields which represent questions
class QuestionForm(forms.Form):
    suffix_freetext = "_freetext_answer"

    # for dynamicly add question to forms
    def create_question(
        self,
        question_option,
        incident_workflow=None,
        incident=None,
        is_new_incident_workflow=False,
    ):
        initial_data = None
        field_name = "__question__" + str(question_option.id)
        question = question_option.question
        question_type = question_option.question.question_type
        last_historic_changes = QuestionOptionsHistory.objects.none()
        if is_new_incident_workflow:
            last_historic_changes = QuestionOptionsHistory.objects.filter(questionoptions__id=question_option.id).order_by("-timestamp")
        answer_queryset = Answer.objects.filter(
            question_options__question=question,
            incident_workflow=(incident.get_latest_incident_workflow() if incident else incident_workflow),
        ).order_by("-timestamp")

        if question_type in ["MULTI", "MT", "SO", "ST"]:
            if answer_queryset.exists():
                initial_predefined_answers = list(
                    answer_queryset.exclude(predefined_answers__isnull=True).values_list("predefined_answers", flat=True)
                )
                if last_historic_changes.exists():
                    last_historic = last_historic_changes.first()
                    if last_historic.timestamp > answer_queryset.first().timestamp and last_historic.question != question_option.question:
                        initial_predefined_answers = []
                initial_data = initial_predefined_answers

            choices = [(choice.id, choice) for choice in question.predefinedanswer_set.all().order_by("position")]
            form_attrs = {
                "title": question.tooltip,
                "data-bs-toggle": "tooltip",
            }

            if question_type not in ["MULTI", "MT"]:
                form_attrs["class"] = "form-check-input"

            self.fields[field_name] = forms.MultipleChoiceField(
                required=question_option.is_mandatory,
                choices=choices,
                widget=(
                    forms.CheckboxSelectMultiple(attrs=form_attrs)
                    if question_type in ["MULTI", "MT"]
                    else OtherCheckboxSelectMultiple(input_type="radio", attrs=form_attrs)
                ),
                label=question.label,
                initial=initial_data,
            )

            if question_type in ["ST", "MT"]:
                value = None
                if answer_queryset.exists():
                    answer = answer_queryset.first()
                    if last_historic_changes.exists():
                        last_historic = last_historic_changes.first()
                        if last_historic.timestamp > answer.timestamp and last_historic.question != question_option.question:
                            answer = ""
                    value = str(answer) if str(answer) != "" else None
                self.fields[field_name + self.suffix_freetext] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(
                        attrs={
                            "rows": 3,
                            "title": question.tooltip,
                            "data-bs-toggle": "tooltip",
                        }
                    ),
                    initial=str(value or ""),
                    label=_("Add details"),
                )
        elif question_type == "DATE":
            if answer_queryset.exists():
                answer = answer_queryset.first()
                if last_historic_changes.exists():
                    last_historic = last_historic_changes.first()
                    if last_historic.timestamp > answer.timestamp and last_historic.question != question_option.question:
                        answer = ""
                initial_data = datetime.strptime(str(answer), "%Y-%m-%d %H:%M") if str(answer) != "" else None

            self.fields[field_name] = forms.DateTimeField(
                widget=TempusDominusV6Widget(
                    max_date=datetime.today(),
                    attrs={
                        "title": question.tooltip,
                        "data-bs-toggle": "tooltip",
                        "append": "fa fa-calendar",
                        "icon_toggle": True,
                    },
                ),
                required=question_option.is_mandatory,
                initial=initial_data,
                help_text=_("Date format yyyy-mm-dd hh:mm"),
            )
            self.fields[field_name].label = question.label
        elif question_type == "FREETEXT":
            if answer_queryset.exists():
                answer = answer_queryset.first()
                if last_historic_changes.exists():
                    last_historic = last_historic_changes.first()
                    if last_historic.timestamp > answer.timestamp and last_historic.question != question_option.question:
                        answer = ""
                initial_data = str(answer) if str(answer) != "" else None

            self.fields[field_name] = forms.CharField(
                required=question_option.is_mandatory,
                widget=forms.Textarea(
                    attrs={
                        "rows": 3,
                        "title": question.tooltip,
                        "data-bs-toggle": "tooltip",
                        "class": "empty_field" if not initial_data else "",
                    }
                ),
                initial=str(initial_data or ""),
                label=question.label,
            )
        elif question_type in ["CL", "RL"]:
            if answer_queryset.exists():
                answer = answer_queryset.first()
                if last_historic_changes.exists():
                    last_historic = last_historic_changes.first()
                    if last_historic.timestamp > answer.timestamp and last_historic.question != question_option.question:
                        answer = ""
                initial_data = list(filter(None, str(answer).split(",")))

            self.fields[field_name] = forms.MultipleChoiceField(
                required=question_option.is_mandatory,
                choices=countries if question_type == "CL" else REGIONAL_AREA,
                widget=DropdownCheckboxSelectMultiple(),
                label=question.label,
                initial=initial_data or [],
            )

    def clean(self):
        cleaned_data = super().clean()

        # this loop checks if there is a freetext answer value for a MT/ST question
        for field_name in list(cleaned_data.keys()):
            if self.suffix_freetext in field_name:
                main_question_field = field_name.removesuffix(self.suffix_freetext)
                freetext_value = cleaned_data.get(field_name)
                main_value = cleaned_data.get(main_question_field)

                if freetext_value and main_value in (None, "", []):
                    cleaned_data[main_question_field] = []

                    if self.has_error(main_question_field, code="required"):
                        self._errors.pop(main_question_field, None)

        return cleaned_data

    def __init__(self, *args, **kwargs):
        position = kwargs.pop("position", -1)
        workflow = kwargs.pop("workflow", None)
        incident_workflow = kwargs.pop("incident_workflow", None)
        categories = kwargs.pop("categories_workflow", None)
        incident = kwargs.pop("incident", None)
        is_new_incident_workflow = kwargs.pop("is_new_incident_workflow", False)
        super().__init__(*args, **kwargs)

        if incident_workflow:
            workflow = incident_workflow.workflow

        if position >= len(categories):
            raise ValueError("Position exceeds available categories.")

        category = categories[position]

        if is_new_incident_workflow:
            category_question_options = workflow.questionoptions_set.filter(
                category_option__question_category=category,
                deleted_date=None,
            ).order_by("position")
        else:
            category_question_options = (
                workflow.questionoptions_set.filter(
                    category_option__question_category=category,
                    updated_at__lte=incident_workflow.timestamp,
                )
                .filter(Q(deleted_date__isnull=True) | Q(deleted_date__gte=incident_workflow.timestamp))
                .order_by("position")
            )

            question_options_changed = workflow.questionoptions_set.filter(
                updated_at__gte=incident_workflow.timestamp,
                historic__isnull=False,
            )
            for question_option in question_options_changed:
                historic = question_option.historic.filter(
                    timestamp__gte=incident_workflow.timestamp,
                    category_option__question_category=category,
                ).first()
                if historic:
                    category_question_options = list(category_question_options)
                    old_question_option = {
                        "id": question_option.id,
                        "question": historic.question,
                        "is_mandatory": historic.is_mandatory,
                        "position": historic.position,
                    }
                    category_question_options.append(SimpleNamespace(**old_question_option))
                    category_question_options = sorted(category_question_options, key=lambda c: c.position)

        for question_option in category_question_options:
            self.create_question(question_option, incident_workflow, incident, is_new_incident_workflow)


# the first question for preliminary notification
class ContactForm(forms.Form):
    company_name = forms.CharField(
        required=True,
        label=_("Name of the Operator"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": "company_name"}),
    )

    contact_lastname = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "contact_lastname"}),
    )
    contact_firstname = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "contact_firstname"}),
    )
    contact_title = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "contact_title"}),
    )
    contact_email = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.EmailInput(attrs={"class": "contact_email"}),
    )
    contact_telephone = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "contact_telephone"}),
    )

    is_technical_the_same = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "required checkbox is_technical_the_same",
            }
        ),
        initial=False,
    )
    technical_lastname = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "technical_lastname"}),
    )
    technical_firstname = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "technical_firstname"}),
    )
    technical_title = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "technical_title"}),
    )
    technical_email = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.EmailInput(attrs={"class": "technical_email"}),
    )
    technical_telephone = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "technical_telephone"}),
    )

    incident_reference = forms.CharField(
        max_length=255,
        required=False,
        label=_("Incident reference"),
        widget=forms.TextInput(
            attrs={
                "title": _(
                    "Please include a reference "
                    "(e.g., an identifier, internal reference, CERT reference, etc.) "
                    "to facilitate incident tracking."
                ),
                "data-bs-toggle": "tooltip",
            }
        ),
    )
    complaint_reference = forms.CharField(
        max_length=255,
        required=False,
        label=_("Complaint reference"),
        widget=forms.TextInput(
            attrs={
                "title": _("Insert the file number of a criminal complaint that you have filed with the police."),
                "data-bs-toggle": "tooltip",
            }
        ),
    )

    def prepare_initial_value(self, **kwargs):
        request = kwargs.pop("request")
        user = request.user
        if user.is_authenticated:
            company_name = user.regulators.first() if is_user_regulator(user) else get_active_company_from_session(request)
            return {
                "company_name": company_name,
                "contact_lastname": user.last_name,
                "contact_firstname": user.first_name,
                "contact_email": user.email,
                "contact_telephone": user.phone_number,
            }
        return {}


# prepare an array of sector and services
def construct_services_array(root_sectors):
    categs = {}
    services = Service.objects.filter(Q(sector__in=root_sectors) | Q(sector__parent__in=root_sectors))

    final_categs = []
    for service in services:
        if not categs.get(service.sector):
            categs[service.sector] = [[service.id, service]]
        else:
            categs[service.sector].append([service.id, service])

    for sector, list_of_options in categs.items():
        name = sector.name
        current_sector = sector
        while current_sector.parent is not None:
            name = _(current_sector.parent.name) + " - " + _(name)
            current_sector = current_sector.parent
        final_categs.append([name, list_of_options])

    return final_categs


class RegulationForm(forms.Form):
    regulations = forms.MultipleChoiceField(
        required=True,
        widget=SortedCheckboxSelectMultiple(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields["regulations"].choices = [
                (regulation.id, str(regulation))
                for regulation in Regulation.objects.filter(regulators__isnull=False).distinct("id")
                if regulation.sectorregulation_set.filter(sectorregulationworkflow__isnull=False, active=True).exists()
            ]
        except Exception:
            self.fields["regulations"].choices = []


class RegulatorForm(forms.Form):
    regulators = forms.MultipleChoiceField(
        required=True,
        choices=[],
        widget=SortedCheckboxSelectMultiple(),
        label=_("Send notification to"),
    )

    def __init__(self, *args, **kwargs):
        regulations = kwargs["initial"].get("regulations", [])
        super().__init__(*args, **kwargs)

        self.fields["regulators"].choices = [
            (
                regulator.id,
                format_html(
                    "<strong>{}</strong>{}",
                    str(regulator),
                    (
                        f" - {regulator.safe_translation_getter('full_name', any_language=True)}"
                        if regulator.safe_translation_getter("full_name", any_language=True)
                        else ""
                    ),
                ),
            )
            for regulator in Regulator.objects.filter(regulation__id__in=regulations).distinct("id")
            if regulator.sectorregulation_set.filter(
                regulation__id__in=regulations,
                sectorregulationworkflow__isnull=False,
            ).exists()
        ]


class DetectionDateForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize the 'incident_timezone' field
        self.fields["incident_timezone"] = forms.ChoiceField(
            choices=[(tz, tz) for tz in pytz.common_timezones],
            widget=forms.Select(attrs={"class": "form-control"}),
            required=True,
            label=_("Select the incident time zone"),
            initial=kwargs.get("initial", {}).get("incident_timezone", None) or TIME_ZONE,
        )

        # Initialize the 'detection_date' field
        self.fields["detection_date"] = forms.DateTimeField(
            required=True,
            widget=TempusDominusV6Widget(
                max_date=datetime.today(),
            ),
            label=_("Select date and time"),
            help_text=_("Date format yyyy-mm-dd hh:mm"),
        )


class SectorForm(forms.Form):
    sectors = forms.MultipleChoiceField(
        required=True,
        widget=forms.CheckboxSelectMultiple(),
        label=_("Sectors"),
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {})
        regulations = initial.get("regulations", [])
        regulators = initial.get("regulators", [])
        super().__init__(*args, **kwargs)

        self.fields["sectors"].choices = construct_sectors_array(regulations, regulators)

        if len(self.fields["sectors"].choices) == 0:
            self.fields["sectors"].required = False


def construct_sectors_array(regulations, regulators):
    sector_regulations = SectorRegulation.objects.filter(regulation__id__in=regulations, regulator__id__in=regulators)
    all_sectors = Sector.objects.filter(sectorregulation__in=sector_regulations).distinct().order_by("parent")

    categs = {}

    for sector in all_sectors:
        sector_name = sector.get_safe_translation()

        if sector.parent:
            parent_name = sector.parent.get_safe_translation()
            categs.setdefault(parent_name, []).append([sector.id, sector_name])
        else:
            if not categs.get(sector_name):
                categs.setdefault(sector_name, []).append([sector.id, sector_name])

    final_categs = [[sector, sorted(options, key=lambda item: item[1])] for sector, options in categs.items()]

    return sorted(final_categs, key=lambda item: item[0])


def get_forms_list(
    incident=None,
    workflow=None,
    incident_workflow=None,
    is_regulator=False,
    is_regulator_incident=False,
    read_only=False,
):
    category_tree = []
    if incident is None:
        category_tree = [
            ContactForm,
            RegulationForm,
            RegulatorForm,
            SectorForm,
            DetectionDateForm,
        ]
    else:
        category_tree.append(IncidenteDateForm)
        if workflow is None:
            workflow = incident.get_next_step()

        is_new_incident_workflow = not read_only and (is_regulator == is_regulator_incident)

        categories = get_workflow_categories(
            workflow,
            incident_workflow,
            is_new_incident_workflow,
        )

        for _ in categories:
            category_tree.append(QuestionForm)

        if workflow.is_impact_needed:
            regulation_sector_has_impacts = Impact.objects.filter(
                regulations=incident.sector_regulation.regulation,
                sectors__in=incident.affected_sectors.all(),
            ).exists()
            if regulation_sector_has_impacts:
                category_tree.append(ImpactForm)

        if is_regulator and not is_regulator_incident:
            category_tree.append(RegulatorIncidentWorkflowCommentForm)
    return category_tree


class RegulatorIncidentEditForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = self.instance.id

    class Meta:
        model = Incident
        fields = [
            "id",
            "incident_id",
            "is_significative_impact",
            "review_status",
            "incident_status",
        ]


class RegulatorIncidentWorkflowCommentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = self.instance.id

        self.fields["review_status"].choices = [
            ("", "-------------"),
            ("PASS", _("Passed")),
            ("FAIL", _("Revision required")),
        ]

        initial_review_status = self.initial.get("review_status")

        class_map = {
            "PASS": "fw-bold bg-passed text-white",
            "FAIL": "fw-bold bg-failed text-white",
        }

        select_class = class_map.get(initial_review_status, "")

        self.fields["review_status"].widget.attrs = {
            "class": f"w-25 {select_class} review_status_selector",
        }

        self.fields["comment"].widget.attrs.update(
            {
                "rows": 3,
                "class": "empty_field" if not self.initial["comment"] else "",
            }
        )

    class Meta:
        model = IncidentWorkflow
        fields = [
            "id",
            "comment",
            "review_status",
        ]


class ImpactForm(forms.Form):
    impacts = forms.MultipleChoiceField(
        required=False,
        widget=ServicesListCheckboxSelectMultiple(initial=None),
    )

    # prepare an array of impacts from incident sectorized
    def construct_impact_array(self, incident):
        impacts_array = []
        regulation = incident.sector_regulation.regulation
        for sector in incident.affected_sectors.all():
            subgroup = []
            if sector.impact_set.filter(regulations=regulation).count() > 0:
                for impact in sector.impact_set.filter(regulations=regulation):
                    subgroup.append([impact.id, str(impact.label)])
                impacts_array.append(
                    [
                        sector.get_safe_translation(),
                        sorted(subgroup, key=lambda item: item[1]),
                    ]
                )

        return impacts_array

    def __init__(self, *args, **kwargs):
        incident = None
        incident_workflow = None
        if "incident" in kwargs:
            incident = kwargs.pop("incident")
        if "incident_workflow" in kwargs:
            incident_workflow = kwargs.pop("incident_workflow")
        super().__init__(*args, **kwargs)

        if incident is not None:
            self.fields["impacts"].choices = self.construct_impact_array(incident)
        if incident_workflow is not None:
            # only with ServicesListCheckboxSelectMultiple
            self.fields["impacts"].widget.initial_data = [i.id for i in incident_workflow.impacts.all()]
        else:
            previous_incident_workflow = incident.get_latest_incident_workflow()
            if previous_incident_workflow is not None:
                # only with ServicesListCheckboxSelectMultiple
                self.fields["impacts"].widget.initial_data = [i.id for i in previous_incident_workflow.impacts.all()]


# let the user change the date of his incident
class IncidenteDateForm(forms.ModelForm):
    incident_timezone = forms.ChoiceField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
        label=_("Select the incident time zone"),
        initial=TIME_ZONE,
    )

    incident_notification_date = forms.DateTimeField(
        widget=TempusDominusV6Widget(),
        required=False,
        label=_("Incident notification date"),
        help_text=_("Date format yyyy-mm-dd hh:mm"),
    )

    incident_detection_date = forms.DateTimeField(
        widget=TempusDominusV6Widget(),
        required=False,
        label=_("Incident detection date"),
        help_text=_("Date format yyyy-mm-dd hh:mm"),
    )

    incident_starting_date = forms.DateTimeField(
        widget=TempusDominusV6Widget(),
        required=False,
        label=_("Incident start date"),
        help_text=_("Date format yyyy-mm-dd hh:mm"),
    )

    incident_resolution_date = forms.DateTimeField(
        widget=TempusDominusV6Widget(),
        required=False,
        label=_("Incident resolution date"),
        help_text=_("Date format yyyy-mm-dd hh:mm"),
    )

    def __init__(self, *args, **kwargs):
        self.incident = kwargs.pop("incident", None)
        super().__init__(*args, **kwargs)
        self.report_timeline = self.instance

        self.fields["incident_notification_date"].disabled = True

        i_timezone = None
        i_detection_date = None
        i_resolution_date = None
        i_starting_date = None

        if self.report_timeline.pk:
            i_timezone = self.report_timeline.report_timeline_timezone
            i_detection_date = self.report_timeline.incident_detection_date
            i_starting_date = self.report_timeline.incident_starting_date
            i_resolution_date = self.report_timeline.incident_resolution_date

        if self.incident:
            i_notification_date = self.incident.incident_notification_date or None
            lastest_report = self.incident.get_latest_incident_workflow()
            if lastest_report and not self.report_timeline.pk:
                lastest_report_timeline = lastest_report.report_timeline
                i_timezone = lastest_report_timeline.report_timeline_timezone
                i_detection_date = lastest_report_timeline.incident_detection_date
                i_starting_date = i_starting_date or lastest_report_timeline.incident_starting_date
                i_resolution_date = i_resolution_date or lastest_report_timeline.incident_resolution_date

            if not i_detection_date and self.incident.sector_regulation.is_detection_date_needed:
                i_detection_date = self.incident.incident_detection_date or None

            i_timezone = i_timezone or self.incident.incident_timezone or TIME_ZONE
            timezone = pytz.timezone(i_timezone)

            if i_detection_date:
                limit_date = format_datetime_astimezone(i_detection_date, timezone)
                self.fields["incident_starting_date"].widget = TempusDominusV6Widget(
                    max_date=limit_date,
                )

                self.fields["incident_resolution_date"].widget = TempusDominusV6Widget(
                    min_date=limit_date,
                )

            if i_notification_date:
                maxDate_notification = format_datetime_astimezone(i_notification_date, timezone)
                self.fields["incident_detection_date"].widget = TempusDominusV6Widget(
                    max_date=maxDate_notification,
                )

            if self.incident.sector_regulation.is_detection_date_needed:
                self.fields["incident_detection_date"].disabled = True
                self.fields["incident_timezone"].disabled = True

            if i_timezone != TIME_ZONE:
                self.fields["incident_timezone"].disabled = True

            self.initial["incident_timezone"] = i_timezone

            set_initial_datetime(
                self,
                "incident_notification_date",
                i_notification_date,
                timezone,
            )

            set_initial_datetime(
                self,
                "incident_detection_date",
                i_detection_date,
                timezone,
            )
            set_initial_datetime(
                self,
                "incident_starting_date",
                i_starting_date,
                timezone,
            )
            set_initial_datetime(
                self,
                "incident_resolution_date",
                i_resolution_date,
                timezone,
            )

    def clean(self):
        cleaned_data = super().clean()
        starting_date = cleaned_data.get("incident_starting_date")
        detection_date = cleaned_data.get("incident_detection_date")
        resolution_date = cleaned_data.get("incident_resolution_date")

        if starting_date and detection_date and starting_date > detection_date:
            self.add_error(
                "incident_starting_date",
                ValidationError(_("Starting date cannot be after detection date.")),
            )

        if resolution_date and detection_date and resolution_date < detection_date:
            self.add_error(
                "incident_resolution_date",
                ValidationError(_("Resolution date cannot be before detection date.")),
            )

        return cleaned_data

    class Meta:
        model = ReportTimeline
        fields = [
            "id",
            "incident_timezone",
            "incident_notification_date",
            "incident_detection_date",
            "incident_starting_date",
            "incident_resolution_date",
        ]


class IncidentStatusForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        if "is_significative_impact" not in self.data:
            cleaned_data["is_significative_impact"] = self.instance.is_significative_impact

        for field in ["incident_id", "incident_status", "is_significative_impact"]:
            if cleaned_data.get(field) in [None, ""]:
                cleaned_data[field] = getattr(self.instance, field)
        return cleaned_data

    def get_field_change(self, field_name):
        if field_name in self.changed_data:
            return self.initial.get(field_name), self.cleaned_data.get(field_name)
        return None, None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set fields to not required
        self.fields["incident_id"].required = False
        self.fields["incident_status"].required = False
        self.fields["is_significative_impact"].required = False

        self.fields["incident_id"].widget.attrs = {
            "class": "form-control-sm incident-input-field ",
            "data-incident-id": self.instance.pk,
        }

        self.fields["is_significative_impact"].widget.attrs = {
            "class": "large-checkbox incident-input-field is_significative_impact_checkbox",
            "data-incident-id": self.instance.pk,
        }

        if self.instance.incident_status == "CLOSE":
            self.fields["is_significative_impact"].widget.attrs["disabled"] = "true"

    class Meta:
        model = Incident
        fields = [
            "incident_id",
            "incident_status",
            "is_significative_impact",
        ]


def format_datetime_astimezone(datetime, timezone):
    return datetime.astimezone(timezone).strftime("%Y-%m-%d %H:%M")


def set_initial_datetime(form, field_name, datetime_value, timezone):
    if datetime_value:
        form.initial[field_name] = format_datetime_astimezone(datetime_value, timezone)
    else:
        form.fields[field_name].widget.attrs["class"] = form.fields[field_name].widget.attrs.get("class", "") + " empty_field"


class QuestionOptionsInlineForm(forms.ModelForm):
    class Meta:
        model = QuestionOptions
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["question"].label_from_instance = lambda obj: obj.get_question_label_with_reference()


class ExportIncidentsForm(forms.Form):
    regulation = forms.ModelChoiceField(
        queryset=Regulation.objects.none(),
        label=_("Regulation"),
        required=True,
    )
    sectorregulation = forms.ModelChoiceField(
        queryset=SectorRegulation.objects.none(),
        label=_("Workflow"),
        required=True,
    )

    workflow = forms.ModelChoiceField(
        queryset=Workflow.objects.none(),
        label=_("Report"),
        required=True,
    )

    file_format = forms.ChoiceField(
        choices=[("xlsx", "Excel (.xlsx)"), ("csv", "CSV (.csv)")],
        required=True,
        label=_("File format"),
        initial="xlsx",
    )

    def __init__(self, *args, **kwargs):
        regulation_qs = kwargs.pop("regulation_qs", Regulation.objects.none())
        sectorregulation_qs = kwargs.pop("sectorregulation_qs", Regulation.objects.none())
        workflow_qs = kwargs.pop("workflow_qs", Workflow.objects.none())
        super().__init__(*args, **kwargs)
        # initialize date
        max_dt = datetime.today().date()
        try:
            min_dt = max_dt.replace(year=max_dt.year - 2)
        except ValueError:
            min_dt = max_dt - timedelta(days=730)
        self.fields["from_date"] = forms.DateField(
            required=True,
            widget=TempusDominusV6Widget(
                min_date=min_dt,
                max_date=max_dt,
            ),
            label=_("From"),
        )
        self.fields["to_date"] = forms.DateField(
            required=True,
            widget=TempusDominusV6Widget(
                min_date=min_dt,
                max_date=max_dt,
            ),
            label=_("To"),
        )
        self.fields["regulation"].queryset = regulation_qs
        self.fields["sectorregulation"].queryset = sectorregulation_qs
        self.fields["workflow"].queryset = workflow_qs
