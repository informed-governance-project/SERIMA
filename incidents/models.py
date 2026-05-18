from datetime import datetime, timedelta

import pytz
from django.contrib import admin
from django.db import models
from django.db.models import Deferrable
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from governanceplatform.settings import TIME_ZONE

from .globals import (
    INCIDENT_EMAIL_TRIGGER_EVENT,
    INCIDENT_STATUS,
    QUESTION_TYPES,
    REVIEW_STATUS,
    SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT,
    WORKFLOW_REVIEW_STATUS,
)


# impacts of the incident, they are linked to sector
class Impact(TranslatableModel):
    """Defines an impact."""

    translations = TranslatedFields(
        label=models.TextField(verbose_name=_("Label")),
        headline=models.CharField(
            verbose_name=_("Title"),
            max_length=255,
            blank=True,
            default=None,
            null=True,
        ),
    )

    regulations = models.ManyToManyField(
        "governanceplatform.Regulation",
        default=None,
        blank=True,
        verbose_name=_("Legal basis"),
        related_name="regulations",
    )

    sectors = models.ManyToManyField("governanceplatform.Sector", default=None, blank=True, verbose_name=_("Sectors"))

    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        headline_translation = self.safe_translation_getter("headline", any_language=True)
        return headline_translation or ""

    class Meta:
        verbose_name_plural = _("Impact")
        verbose_name = _("Impacts")


# category for the question (to order)
class QuestionCategory(TranslatableModel):
    translations = TranslatedFields(label=models.CharField(verbose_name=_("Label"), max_length=255))
    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        label_translation = self.safe_translation_getter("label", any_language=True)
        return label_translation or ""

    class Meta:
        verbose_name = _("Step in notification form")
        verbose_name_plural = _("Steps in notification form")


# questions asked during the Incident notification process
class Question(TranslatableModel):
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPES,
        blank=False,
        default=QUESTION_TYPES[0][0],
        verbose_name=_("Question Type"),
    )  # MULTI, FREETEXT, DATE,
    reference = models.CharField(
        verbose_name=_("Reference"),
        max_length=255,
        unique=True,
    )  # reference to add context information on question
    translations = TranslatedFields(
        label=models.TextField(verbose_name=_("Label")),
        tooltip=models.TextField(verbose_name=_("Tooltip"), blank=True, null=True),
    )
    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    @admin.display(description=_("Answers"))
    def get_predefined_answers(self):
        return [predefined_answer.predefined_answer for predefined_answer in self.predefinedanswer_set.all()]

    def get_question_label_with_reference(self):
        if self.reference:
            return f"[{self.reference}] {str(self)}"
        return str(self)

    def __str__(self):
        return (
            self.safe_translation_getter("label", any_language=True)
            if self.language_code and self.safe_translation_getter("label", any_language=True)
            else ""
        )

    class Meta:
        verbose_name_plural = _("Questions")
        verbose_name = _("Question")


# answers for the question
class PredefinedAnswer(TranslatableModel):
    translations = TranslatedFields(predefined_answer=models.TextField(verbose_name=_("Answer")))
    question = models.ForeignKey(
        Question,
        verbose_name=_("Question"),
        on_delete=models.CASCADE,
        default=None,
        null=True,
    )
    position = models.IntegerField(blank=True, default=0, null=True)
    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        return (
            self.safe_translation_getter("predefined_answer", any_language=True)
            if self.language_code and self.safe_translation_getter("predefined_answer", any_language=True)
            else ""
        )

    class Meta:
        verbose_name_plural = _("Question - predefined answers")
        verbose_name = _("Question - predefined answer")


# Email sent from regulator to operator
class Email(TranslatableModel, models.Model):
    translations = TranslatedFields(
        subject=models.CharField(
            verbose_name=_("Subject"),
            max_length=255,
        ),
        content=models.TextField(
            verbose_name=_("Content"),
            help_text=_(
                """Available placeholders: #INCIDENT_NOTIFICATION_DATE#,
                #INCIDENT_DETECTION_DATE#,
                #INCIDENT_STARTING_DATE#,
                #INCIDENT_ID#,
                #DEADLINE#"""
            ),
        ),
    )
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        return self.name or ""

    class Meta:
        verbose_name_plural = _("Emails")
        verbose_name = _("Email")


# Workflow for each sector_regulation, N workflow for 1 reglementation,
# 1 Workflow for N recommendation ?
class Workflow(TranslatableModel):
    name = models.CharField(verbose_name=_("Name"), max_length=255, unique=True)

    translations = TranslatedFields(
        label=models.CharField(verbose_name=_("Label"), max_length=255),
        description=models.TextField(blank=True, default="", null=True, verbose_name=_("Description")),
    )
    is_impact_needed = models.BooleanField(default=False, verbose_name=_("Impacts disclosure required"))

    submission_email = models.ForeignKey(
        Email,
        verbose_name=_("Submission email"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="submission_email",
    )

    # name of the regulator who create the object
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        label_translation = self.safe_translation_getter("label", any_language=True)
        return label_translation or ""

    class Meta:
        verbose_name_plural = _("Incident reports")
        verbose_name = _("Incident report")


# link between a regulation and a regulator,
# a regulator can only create a sector_regulation for the regulation the
# admin platform has designated him
class SectorRegulation(TranslatableModel):
    translations = TranslatedFields(
        # for exemple NIS for energy sector
        name=models.CharField(verbose_name=_("Name"), max_length=255)
    )
    active = models.BooleanField(
        verbose_name=_("Active"),
        default=True,
    )
    regulation = models.ForeignKey(
        "governanceplatform.Regulation",
        on_delete=models.CASCADE,
        verbose_name=_("Legal basis"),
    )
    regulator = models.ForeignKey(
        "governanceplatform.Regulator",
        on_delete=models.CASCADE,
        verbose_name=_("Regulator"),
    )
    workflows = models.ManyToManyField(Workflow, through="SectorRegulationWorkflow", verbose_name=_("Incident reports"))

    sectors = models.ManyToManyField("governanceplatform.Sector", verbose_name=_("Sectors"), default=None, blank=True)
    is_detection_date_needed = models.BooleanField(default=False, verbose_name=_("Incident detection date required"))
    # email
    opening_email = models.ForeignKey(
        Email,
        verbose_name=_("Opening email"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="opening_email",
    )
    closing_email = models.ForeignKey(
        Email,
        verbose_name=_("Closing email"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="closing_email",
    )
    report_status_changed_email = models.ForeignKey(
        Email,
        verbose_name=_("Status update email"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="report_status_changed_email",
    )

    class Meta:
        verbose_name_plural = _("Incident notification workflows")
        verbose_name = _("Incident notification workflow")

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""


# link between sector regulation and workflows
class SectorRegulationWorkflow(models.Model):
    sector_regulation = models.ForeignKey(SectorRegulation, verbose_name=_("Workflow"), on_delete=models.CASCADE)
    workflow = models.ForeignKey(Workflow, verbose_name=_("Incident report"), on_delete=models.CASCADE)
    position = models.IntegerField(verbose_name=_("Position"), blank=True, default=0, null=True)
    # the delay after the trigger event
    delay_in_hours_before_deadline = models.IntegerField(verbose_name=_("Deadline in hours"), default=0)
    trigger_event_before_deadline = models.CharField(
        verbose_name=_("Event triggering deadline"),
        max_length=15,
        choices=SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT,
        blank=False,
        default=SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT[0][0],
    )
    emails = models.ManyToManyField(Email, verbose_name=_("Emails"), through="SectorRegulationWorkflowEmail")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sector_regulation", "position"],
                name="Unique_SectorRegulationWorkflowPosition",
                deferrable=Deferrable.DEFERRED,
            ),
        ]
        verbose_name_plural = _("Report")
        verbose_name = _("Reports")

    def __str__(self):
        return self.sector_regulation.name + " : " + self.workflow.name if self.workflow and self.sector_regulation else ""

    def get_previous_report(self):
        previous = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.sector_regulation,
                position__lt=self.position,
            )
            .order_by("-position")
            .first()
        )

        if previous is not None:
            return previous
        return False

    # calculates the time between an incident update and actual_time
    # TO DO : if needed make a function get_incident_detection_date
    # to have the right date depending of the IncidentWorkflow and not
    # incident
    def how_late_is_the_report(self, incident, actual_time=None):
        if actual_time is None:
            actual_time = timezone.now()

        trigger_event = self.trigger_event_before_deadline
        dt = None
        # check notif date
        if trigger_event == "NOTIF_DATE":
            dt = actual_time - incident.incident_notification_date

        # detection date
        elif trigger_event == "DETECT_DATE" and incident.incident_detection_date is not None:
            dt = actual_time - incident.incident_detection_date

        # previous incident_workflow
        elif trigger_event == "PREV_WORK":
            prev_workflow = self.get_previous_report()
            if prev_workflow:
                previous_incident_workflow = (
                    IncidentWorkflow.objects.filter(
                        incident=incident,
                        workflow=prev_workflow.workflow,
                    )
                    .order_by("-timestamp")
                    .first()
                )
                if previous_incident_workflow:
                    dt = actual_time - previous_incident_workflow.timestamp

        return dt


# for emailing during each workflow
class SectorRegulationWorkflowEmail(TranslatableModel):
    translations = TranslatedFields(
        headline=models.CharField(verbose_name=_("Email subject"), max_length=255),
    )

    sector_regulation_workflow = models.ForeignKey(
        SectorRegulationWorkflow,
        verbose_name=_("Report"),
        on_delete=models.CASCADE,
    )
    email = models.ForeignKey(Email, verbose_name=_("Email"), on_delete=models.CASCADE)
    # the trigger event which send the email
    trigger_event = models.CharField(
        verbose_name=_("Trigger event"),
        max_length=15,
        choices=INCIDENT_EMAIL_TRIGGER_EVENT,
        blank=False,
        default=INCIDENT_EMAIL_TRIGGER_EVENT[0][0],
    )
    # the delay after the trigger event
    delay_in_hours = models.IntegerField(verbose_name=_("Delay in hours"), default=0)

    class Meta:
        verbose_name_plural = _("Reminder emails")
        verbose_name = _("Reminder email")

    def __str__(self):
        headline_translation = self.safe_translation_getter("headline", any_language=True)
        return headline_translation or ""

    @admin.display(
        description=_("Regulation"),
        ordering="sector_regulation_workflow__sector_regulation__regulation__translations__label",
    )
    def regulation(self):
        return self.sector_regulation_workflow.sector_regulation.regulation


# incident
class Incident(models.Model):
    # XXXXXXXXXX-SSS-SSS-NNNN-YYYY
    incident_id = models.CharField(max_length=28, verbose_name=_("Incident Reference"))
    incident_timezone = models.CharField(
        max_length=50,
        choices=[(tz, tz) for tz in pytz.all_timezones],
        default=TIME_ZONE,
    )
    incident_notification_date = models.DateTimeField(default=timezone.now)
    incident_detection_date = models.DateTimeField(blank=True, null=True)
    incident_last_update = models.DateTimeField(blank=True, null=True)
    company_name = models.CharField(max_length=100, verbose_name=_("Name of the Operator"))
    company = models.ForeignKey(
        "governanceplatform.Company",
        verbose_name=_("Operator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    regulator = models.ForeignKey(
        "governanceplatform.Regulator",
        verbose_name=_("Regulator"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    # we allo to store user in case he is registered
    contact_user = models.ForeignKey(
        "governanceplatform.User",
        verbose_name=_("Contact user"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    contact_lastname = models.CharField(max_length=100, verbose_name=_("Contact last name"))
    contact_firstname = models.CharField(max_length=100, verbose_name=_("Contact first name"))
    contact_title = models.CharField(max_length=100, verbose_name=_("Contact job title"))
    contact_email = models.CharField(max_length=100, verbose_name=_("Contact email"))
    contact_telephone = models.CharField(max_length=100, verbose_name=_("Contact telephone"))
    # technical contact
    technical_lastname = models.CharField(max_length=100, verbose_name=_("Technical last name"))
    technical_firstname = models.CharField(max_length=100, verbose_name=_("Technical first name"))
    technical_title = models.CharField(max_length=100, verbose_name=_("Technical job title"))
    technical_email = models.CharField(max_length=100, verbose_name=_("Technical email"))
    technical_telephone = models.CharField(max_length=100, verbose_name=_("Technical telephone"))

    incident_reference = models.CharField(verbose_name=_("Internal incident reference"), max_length=255)
    complaint_reference = models.CharField(verbose_name=_("Criminal complaint file number"), max_length=255)

    affected_services = models.ManyToManyField("governanceplatform.Service", verbose_name=_("Impacted service"))
    sector_regulation = models.ForeignKey(
        SectorRegulation,
        verbose_name=_("Workflow"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    # keep a trace of selected sectors
    affected_sectors = models.ManyToManyField("governanceplatform.Sector", verbose_name=_("Impacted sectors"))
    workflows = models.ManyToManyField(Workflow, through="IncidentWorkflow", verbose_name=_("Incident reports"))
    impacts = models.ManyToManyField(
        Impact,
        verbose_name=_("Impacts"),
        default=None,
    )
    is_significative_impact = models.BooleanField(default=False, verbose_name=_("Significant impact"))

    # notification dispatching
    authorities = models.ManyToManyField(
        "governanceplatform.Regulator",
        related_name="authorities",
        verbose_name=_("Regulators"),
    )

    # status
    review_status = models.CharField(
        max_length=5,
        choices=REVIEW_STATUS,
        blank=False,
        default=REVIEW_STATUS[0][0],
        verbose_name=_("Report status"),
    )
    incident_status = models.CharField(
        max_length=5,
        verbose_name=_("Incident status"),
        choices=INCIDENT_STATUS,
        blank=False,
        default=INCIDENT_STATUS[1][0],
    )

    # update the incident_last_update of incident
    def save(self, *args, **kwargs):
        self.incident_last_update = timezone.now()
        super().save(*args, **kwargs)

    def get_incident_root_sector(self):
        return list({sector.parent for sector in self.affected_sectors.all()})

    def get_no_childrens_sectors(self):
        return list(self.affected_sectors.filter(parent__isnull=True))

    def get_next_sector_regulation_workflow(self):
        current_workflow = (
            IncidentWorkflow.objects.all()
            .filter(
                incident=self,
            )
            .values_list("workflow")
        )
        regulation = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.sector_regulation,
            )
            .exclude(workflow__in=current_workflow)
            .order_by("position")
        )
        if len(regulation) > 0:
            return regulation[0]
        return None

    def get_next_step(self):
        current_workflow = (
            IncidentWorkflow.objects.all()
            .filter(
                incident=self,
            )
            .values_list("workflow")
        )
        regulation = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.sector_regulation,
            )
            .exclude(workflow__in=current_workflow)
            .order_by("position")
        )
        if len(regulation) > 0:
            return regulation[0].workflow
        return None

    def are_impacts_present(self):
        impacts = Impact.objects.filter(
            regulations=self.sector_regulation.regulation,
            sectors__in=self.affected_sectors.all(),
        )
        return impacts.count() > 0

    def get_all_workflows(self):
        workflows = self.sector_regulation.workflows.all().order_by("sectorregulationworkflow__position")
        return list(workflows)

    def get_workflows_completed(self):
        return self.incidentworkflow_set.all().order_by("workflow__sectorregulationworkflow__position", "-timestamp").distinct()

    def get_latest_incident_workflows(self, timestamp_order="-timestamp"):
        return (
            IncidentWorkflow.objects.filter(
                incident=self,
            )
            .order_by("workflow", timestamp_order)
            .distinct("workflow")
        )

    def get_latest_incident_workflow(self):
        return (
            IncidentWorkflow.objects.filter(
                incident=self,
            )
            .order_by("-timestamp")
            .first()
        )

    def get_latest_incident_workflow_by_workflow(self, workflow):
        return (
            IncidentWorkflow.objects.filter(
                incident=self,
                workflow=workflow,
            )
            .order_by("-timestamp")
            .first()
        )

    def get_previous_workflow(self, workflow):
        current = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.sector_regulation,
                workflow=workflow,
            )
            .first()
        )

        previous = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.sector_regulation,
                position__lt=current.position,
            )
            .order_by("-position")
            .first()
        )

        if previous is not None:
            return previous
        return False

    # check if the previous workflow is filled and no next workflow filled
    def is_fillable(self, workflow):
        if self.incident_status != "CLOSE":
            current = (
                SectorRegulationWorkflow.objects.all()
                .filter(
                    sector_regulation=self.sector_regulation,
                    workflow=workflow,
                )
                .first()
            )
            previous = (
                SectorRegulationWorkflow.objects.all()
                .filter(
                    sector_regulation=self.sector_regulation,
                    position__lt=current.position,
                )
                .order_by("-position")
                .first()
            )
            # i am first
            if previous is None:
                # check if there are other record than me
                existing_workflow = (
                    IncidentWorkflow.objects.all()
                    .filter(
                        incident=self,
                    )
                    .exclude(workflow=workflow)
                    .first()
                )
                if existing_workflow is None:
                    return True
            # i am not first
            else:
                previous_incident_workflow = (
                    IncidentWorkflow.objects.all()
                    .filter(
                        incident=self,
                        workflow=previous.workflow,
                    )
                    .first()
                )
                if previous_incident_workflow is not None:
                    next_workflows = (
                        SectorRegulationWorkflow.objects.all()
                        .filter(
                            sector_regulation=self.sector_regulation,
                            position__gt=current.position,
                        )
                        .order_by("-position")
                        .values_list("workflow", flat=True)
                    )
                    next_incident_workflows = (
                        IncidentWorkflow.objects.all()
                        .filter(
                            incident=self,
                            workflow__in=next_workflows,
                        )
                        .first()
                    )
                    # There are previous and no next sor we are good
                    if next_incident_workflows is None:
                        return True
            return False
        return False

    # calculate the deadline of the incident
    def get_deadline(self):
        next_srw = self.get_next_sector_regulation_workflow()
        if next_srw is None:
            return None
        deadline = None
        if next_srw.trigger_event_before_deadline is not None and next_srw.delay_in_hours_before_deadline is not None:
            if next_srw.trigger_event_before_deadline == "DETECT_DATE":
                if self.incident_detection_date is not None:
                    deadline = self.incident_detection_date + timedelta(hours=next_srw.delay_in_hours_before_deadline)
            elif next_srw.trigger_event_before_deadline == "NOTIF_DATE":
                deadline = self.incident_notification_date + timedelta(hours=next_srw.delay_in_hours_before_deadline)
            elif next_srw.trigger_event_before_deadline == "PREV_WORK":
                previous_workflow = self.get_previous_workflow(next_srw.workflow)
                if previous_workflow:
                    previous_incident_workflow = (
                        IncidentWorkflow.objects.all()
                        .filter(incident=self, workflow=previous_workflow.workflow)
                        .order_by("-timestamp")
                        .first()
                    )
                    if previous_incident_workflow is not None:
                        deadline = previous_incident_workflow.timestamp + timedelta(hours=next_srw.delay_in_hours_before_deadline)
        return deadline

    @property
    def company_or_regulator_name(self):
        if self.company:
            return self.company.name
        if self.regulator:
            return self.regulator.full_name
        return self.company_name

    @property
    def company_or_regulator_acronym(self):
        if self.company:
            return self.company.identifier
        if self.regulator:
            return self.regulator
        return ""

    class meta:
        verbose_name_plural = _("Incident")
        verbose_name = _("Incidents")


class ReportTimeline(models.Model):
    incident_detection_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Incident detection date"))
    incident_starting_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Incident starting date"))
    incident_resolution_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Incident resolution date"))
    report_timeline_timezone = models.CharField(
        max_length=50,
        choices=[(tz, tz) for tz in pytz.all_timezones],
        default=TIME_ZONE,
        verbose_name=_("Report timeline timezone"),
    )


# link between incident and workflow
class IncidentWorkflow(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, verbose_name=_("Incident"))
    workflow = models.ForeignKey(
        Workflow,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Incident report"),
    )
    # for versionning
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), default=timezone.now)
    review_status = models.CharField(
        verbose_name=_("Report status"),
        max_length=5,
        choices=WORKFLOW_REVIEW_STATUS,
        blank=False,
        default=WORKFLOW_REVIEW_STATUS[0][0],
    )
    impacts = models.ManyToManyField(
        Impact,
        verbose_name=_("Impacts"),
        default=None,
    )
    comment = models.TextField(verbose_name=_("Comment/Explanation"), null=True, blank=True)
    report_timeline = models.ForeignKey(
        ReportTimeline,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Timeline"),
        related_name="incident_workflow",
    )

    class meta:
        verbose_name_plural = _("Incident")
        verbose_name = _("Incidents")

    def get_previous_workflow(self):
        current = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.incident.sector_regulation,
                workflow=self.workflow,
            )
            .first()
        )

        if not current:
            return False

        previous = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.incident.sector_regulation,
                position__lt=current.position,
            )
            .order_by("-position")
            .first()
        )

        if previous is not None:
            return previous.workflow
        return False

    def get_next_workflow(self):
        current = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.incident.sector_regulation,
                workflow=self.workflow,
            )
            .first()
        )
        if not current:
            return False

        next = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=self.incident.sector_regulation,
                position__gt=current.position,
            )
            .order_by("position")
            .first()
        )

        if next is not None:
            return next.workflow
        return False

    # define is a submission is late or not
    def is_late(self):
        report = SectorRegulationWorkflow.objects.filter(
            workflow=self.workflow,
            sector_regulation=self.incident.sector_regulation,
        ).first()
        delay_in_hours = report.delay_in_hours_before_deadline

        dt = report.how_late_is_the_report(self.incident)

        if dt and dt.total_seconds() / 60 / 60 >= delay_in_hours:
            return True
        return False

    def save(self, *args, **kwargs):
        if self.is_late() and self.review_status == WORKFLOW_REVIEW_STATUS[0][0]:
            self.review_status = WORKFLOW_REVIEW_STATUS[5][0]
        elif not self.is_late() and self.review_status == WORKFLOW_REVIEW_STATUS[0][0]:
            self.review_status = WORKFLOW_REVIEW_STATUS[1][0]
        super().save(*args, **kwargs)


# record who has read the reports
class LogReportRead(models.Model):
    user = models.ForeignKey(
        "governanceplatform.User",
        on_delete=models.SET_NULL,
        verbose_name=_("User"),
        null=True,
    )
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), default=timezone.now)
    # save full name in case of the user is deleted to keep the name
    user_full_name = models.CharField(max_length=250, verbose_name=_("Full username"))
    role = models.CharField(max_length=250, verbose_name=_("Role"))
    entity_name = models.CharField(max_length=250, verbose_name=_("Entity name"))
    incident_report = models.ForeignKey(
        IncidentWorkflow,
        verbose_name=_("Incident report processed"),
        on_delete=models.CASCADE,
        null=True,
        default=None,
    )
    incident = models.ForeignKey(
        Incident,
        verbose_name=_("Incident report processed"),
        on_delete=models.CASCADE,
        null=True,
        default=None,
    )
    # the action performed e.g. : read, download
    action = models.CharField(max_length=250, verbose_name=_("Action performed"))

    def save(self, *args, **kwargs):
        self.user_full_name = self.user.get_full_name()
        super().save(*args, **kwargs)

        # update the incident_last_update of incident
        if self.action not in ("READ", "DOWNLOAD") and self.incident:
            self.incident.incident_last_update = self.timestamp
            self.incident.save(update_fields=["incident_last_update"])


class QuestionCategoryOptions(models.Model):
    question_category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE)
    position = models.IntegerField(verbose_name=_("Position"))

    def __str__(self):
        return self.question_category.label or ""

    class Meta:
        verbose_name_plural = _("Question category options")
        verbose_name = _("Question category option")


# save the history of the question inside a report
# we save only the changes, the deletion is managed
# in QuestionOptions
class QuestionOptionsHistory(models.Model):
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), default=timezone.now)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=False, verbose_name=_("Mandatory"))
    position = models.IntegerField(verbose_name=_("Position"))
    category_option = models.ForeignKey(
        QuestionCategoryOptions,
        on_delete=models.PROTECT,
        default=None,
    )

    def __str__(self):
        return str(self.question) or ""


class QuestionOptions(models.Model):
    report = models.ForeignKey(Workflow, on_delete=models.CASCADE, null=True, blank=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=False, verbose_name=_("Mandatory"))
    position = models.IntegerField(verbose_name=_("Position"))
    category_option = models.ForeignKey(
        QuestionCategoryOptions,
        on_delete=models.PROTECT,
    )
    # creation date by default before the creation of app
    updated_at = models.DateTimeField(verbose_name=_("Updated at"), default=timezone.make_aware(datetime(2000, 1, 1)))
    historic = models.ManyToManyField(QuestionOptionsHistory, blank=True)
    deleted_date = models.DateTimeField(verbose_name=_("Deleted date"), default=None, blank=True, null=True)

    def is_deleted(self):
        if self.deleted_date is not None:
            return True
        return False

    def delete(self, *args, **kwargs):
        in_use = self.answer_set.exists()
        if in_use:
            self.deleted_date = timezone.now()
            self.save()
        else:
            super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.pk and self.answer_set.exists() and not self.is_deleted():
            old = QuestionOptions.objects.get(pk=self.pk)

            if (
                old.question != self.question
                or old.is_mandatory != self.is_mandatory
                or old.position != self.position
                or old.category_option != self.category_option
            ):
                history = QuestionOptionsHistory.objects.create(
                    question=old.question,
                    is_mandatory=old.is_mandatory,
                    position=old.position,
                    category_option=old.category_option,
                )
                self.historic.add(history)

        if not self.is_deleted():
            self.updated_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.question) or ""


# answers
class Answer(models.Model):
    incident_workflow = models.ForeignKey(
        IncidentWorkflow,
        verbose_name=_("Incident report processed"),
        on_delete=models.CASCADE,
    )
    answer = models.TextField(verbose_name=_("Answer"), null=True, blank=True)
    question_options = models.ForeignKey(
        QuestionOptions,
        verbose_name=_("Questionnaire"),
        on_delete=models.CASCADE,
        null=True,
    )
    predefined_answers = models.ManyToManyField(PredefinedAnswer, blank=True)

    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), default=timezone.now)

    def __str__(self):
        return self.answer or ""

    class meta:
        verbose_name_plural = _("Answer")
        verbose_name = _("Answers")


class RTTicket(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE)
    ticket_id = models.CharField(max_length=50)
    observer = models.ForeignKey("governanceplatform.Observer", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
