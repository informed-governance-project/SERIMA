import os
import uuid
from datetime import datetime

import pytz
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.timezone import get_default_timezone, is_naive, make_aware
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from .globals import CELERY_TASK_STATUS, RISK_TREATMENT


# Store company and year of submission risk analysis data
class CompanyReporting(models.Model):
    company = models.ForeignKey(
        "governanceplatform.Company",
        on_delete=models.CASCADE,
        verbose_name=_("Company"),
    )
    year = models.PositiveIntegerField()
    sector = models.ForeignKey(
        "governanceplatform.Sector",
        on_delete=models.CASCADE,
        verbose_name=_("Sector"),
    )
    comment = models.TextField(
        verbose_name=_("Comment"),
        blank=True,
        default=None,
        null=True,
    )

    class Meta:
        unique_together = ["company", "sector", "year"]


# store asset
class AssetData(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(
            verbose_name=_("Name"),
            max_length=255,
            blank=True,
            default=None,
            null=True,
        ),
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name=_("uuid"),
    )

    class Meta:
        verbose_name_plural = _("Asset")
        verbose_name = _("Assets")

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""


# store Vulnerability
class VulnerabilityData(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(
            verbose_name=_("Name"),
            max_length=255,
            blank=True,
            default=None,
            null=True,
        ),
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name=_("uuid"),
    )

    class Meta:
        verbose_name_plural = _("Vulnerabilities")
        verbose_name = _("Vulnerability")

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""


# store Threat
class ThreatData(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(
            verbose_name=_("Name"),
            max_length=255,
            blank=True,
            default=None,
            null=True,
        ),
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name=_("uuid"),
    )

    class Meta:
        verbose_name_plural = _("Threats")
        verbose_name = _("Threat")

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""


# Store the stat for each service in a risk analysis
class ServiceStat(models.Model):
    service = models.ForeignKey(
        AssetData,
        on_delete=models.CASCADE,
        verbose_name=_("Asset"),
    )

    company_reporting = models.ForeignKey(
        CompanyReporting,
        on_delete=models.CASCADE,
        verbose_name=_("Risk Analysis"),
    )

    total_risks = models.IntegerField(verbose_name=_("Total of all risks"), default=0)

    total_untreated_risks = models.IntegerField(verbose_name=_("Total of untreated risks"), default=0)

    total_treated_risks = models.IntegerField(verbose_name=_("Total of treated risks"), default=0)

    total_reduced_risks = models.IntegerField(verbose_name=_("Total of reduced risks"), default=0)

    total_denied_risks = models.IntegerField(verbose_name=_("Total of denied risks"), default=0)

    total_accepted_risks = models.IntegerField(verbose_name=_("Total of accepted risks"), default=0)

    total_shared_risks = models.IntegerField(verbose_name=_("Total of shared risks"), default=0)

    avg_current_risks = models.FloatField(verbose_name=_("Average of current risks"), default=0)

    avg_residual_risks = models.FloatField(verbose_name=_("Average of residual risks"), default=0)

    class Meta:
        verbose_name_plural = _("Risk analysis stats")
        verbose_name = _("Risk analysis stats")


# Store the risk data
class RiskData(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        verbose_name=_("uuid"),
    )
    service = models.ForeignKey(
        ServiceStat,
        on_delete=models.CASCADE,
        verbose_name=_("Service"),
    )
    asset = models.ForeignKey(
        AssetData,
        on_delete=models.CASCADE,
        verbose_name=_("Asset"),
    )
    threat = models.ForeignKey(
        ThreatData,
        on_delete=models.CASCADE,
        verbose_name=_("Threat"),
    )
    threat_value = models.IntegerField(
        verbose_name=_("Threat value"),
    )
    vulnerability = models.ForeignKey(
        VulnerabilityData,
        on_delete=models.CASCADE,
        verbose_name=_("Vulnerability"),
    )
    vulnerability_value = models.IntegerField(
        verbose_name=_("Vulnerability value"),
    )
    residual_risk = models.IntegerField(
        verbose_name=_("Residual risk"),
        default=-1,
    )
    risk_treatment = models.CharField(
        max_length=5,
        verbose_name=_("Risk treatment"),
        choices=RISK_TREATMENT,
        blank=False,
        default=RISK_TREATMENT[1][0],
    )
    max_risk = models.IntegerField(
        verbose_name=_("Maximum risk"),
        default=-1,
    )
    risk_c = models.IntegerField(
        verbose_name=_("Confidentility risk"),
        default=-1,
    )
    risk_i = models.IntegerField(
        verbose_name=_("Integrity risk"),
        default=-1,
    )
    risk_a = models.IntegerField(
        verbose_name=_("Availability risk"),
        default=-1,
    )
    impact_c = models.IntegerField(
        verbose_name=_("Confidentility impact"),
        default=-1,
    )
    impact_i = models.IntegerField(
        verbose_name=_("Integrity impact"),
        default=-1,
    )
    impact_a = models.IntegerField(
        verbose_name=_("Availability impact"),
        default=-1,
    )
    recommendations = models.ManyToManyField("RecommendationData", verbose_name=_("recommendations"))

    class Meta:
        verbose_name_plural = _("Risks")
        verbose_name = _("Risk")


# Store the recommendation data
class RecommendationData(models.Model):
    code = models.CharField(
        max_length=255,
        verbose_name=_("Recommendation name"),
    )
    description = models.TextField(verbose_name=_("Recommendation description"))

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name=_("uuid"),
    )
    status = models.BooleanField(default=False, verbose_name=_("Status of the recommendation"))
    due_date = models.DateTimeField(verbose_name=_("Due date"), null=True)

    class Meta:
        verbose_name_plural = _("Recommendations")
        verbose_name = _("Recommendation")

    def save(self, *args, **kwargs):
        if isinstance(self.due_date, dict):
            naive_due_date = datetime.strptime(self.due_date["date"], "%Y-%m-%d %H:%M:%S.%f")
            timezone = pytz.timezone(self.due_date["timezone"])
            self.due_date = timezone.localize(naive_due_date)
        elif isinstance(self.due_date, str):
            try:
                naive_due_date = datetime.strptime(self.due_date, "%Y-%m-%d")
                self.due_date = make_aware(naive_due_date, timezone=get_default_timezone())
            except ValueError:
                raise ValueError(f"Invalid date format: {self.due_date}")

        elif self.due_date and is_naive(self.due_date):
            self.due_date = make_aware(self.due_date)

        super().save(*args, **kwargs)


# store the configuration
class SectorReportConfiguration(models.Model):
    sector = models.ForeignKey(
        "governanceplatform.Sector",
        on_delete=models.CASCADE,
        verbose_name=_("Sector"),
    )

    number_of_year = models.PositiveSmallIntegerField(
        verbose_name=_("Number of years to compare"),
        choices=[(nb_year, str(nb_year)) for nb_year in range(1, 4)],
    )

    threshold_for_high_risk = models.IntegerField(
        verbose_name=_("High risk rate threshold"),
    )

    top_ranking = models.PositiveSmallIntegerField(
        verbose_name=_("Ranking"),
        choices=[(3, _("Top 3")), (5, _("Top 5")), (10, _("Top 10"))],
    )

    so_excluded = models.ManyToManyField(
        "securityobjectives.SecurityObjective",
        verbose_name=_("Security objectives excluded"),
    )

    class Meta:
        verbose_name_plural = _("Configurations")
        verbose_name = _("Configuration")


# recommendation for observation
class ObservationRecommendation(TranslatableModel):
    translations = TranslatedFields(
        description=models.TextField(
            verbose_name=_("description"),
            blank=True,
            default=None,
            null=True,
        ),
    )
    code = models.CharField(
        max_length=255,
        verbose_name=_("Recommendation name"),
    )
    sectors = models.ManyToManyField(
        "governanceplatform.Sector",
        verbose_name=_("Sectors"),
        blank=True,
    )
    creation_date = models.DateTimeField(verbose_name=_("Creation date"), default=timezone.now)

    def __str__(self):
        return self.code or ""

    class Meta:
        verbose_name_plural = _("Recommendations for observation")
        verbose_name = _("Recommendation for observation")


# observation of regulator
class Observation(models.Model):
    company_reporting = models.ForeignKey(
        CompanyReporting,
        on_delete=models.CASCADE,
        verbose_name=_("Risk Analysis"),
    )
    observation_recommendations = models.ManyToManyField(
        ObservationRecommendation,
        through="ObservationRecommendationThrough",
        verbose_name=_("Observation recommendations"),
    )

    class Meta:
        verbose_name_plural = _("Observations")
        verbose_name = _("Observation")


class ObservationRecommendationThrough(models.Model):
    observation = models.ForeignKey("Observation", on_delete=models.CASCADE)
    observation_recommendation = models.ForeignKey("ObservationRecommendation", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = _("Observations order")
        verbose_name = _("Observation order")
        unique_together = ("observation", "observation_recommendation")
        ordering = ["order"]


# reporting logs
class LogReporting(models.Model):
    user = models.ForeignKey(
        "governanceplatform.User",
        on_delete=models.SET_NULL,
        verbose_name=_("User"),
        null=True,
    )
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), auto_now=True)
    # save full name in case of the user is deleted to keep the name
    user_full_name = models.CharField(max_length=250, verbose_name=_("User full name"))
    role = models.CharField(max_length=250, verbose_name=_("Role"))
    entity_name = models.CharField(max_length=250, verbose_name=_("Entity name"))
    project = models.ForeignKey(
        "reporting.Project",
        verbose_name=_("Project"),
        on_delete=models.CASCADE,
        null=True,
        default=None,
    )
    action = models.CharField(max_length=50, verbose_name=_("Action performed"))

    def save(self, *args, **kwargs):
        self.user_full_name = self.user.get_full_name()
        super().save(*args, **kwargs)


class Configuration(models.Model):
    regulator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Regulator"),
        on_delete=models.CASCADE,
    )

    standard = models.ForeignKey(
        "securityobjectives.standard",
        verbose_name=_("Standard"),
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name_plural = _("Configurations")
        verbose_name = _("Configuration")
        unique_together = ("regulator", "standard")

    def __str__(self):
        return f"{self.standard.regulation} - {self.standard}"

    def clean(self):
        if Configuration.objects.filter(regulator=self.standard.regulator, standard=self.standard).exclude(pk=self.pk).exists():
            raise ValidationError(_("This regulator already has this standard configured."))


class Color(models.Model):
    configuration = models.ForeignKey(
        Configuration,
        on_delete=models.CASCADE,
        related_name="colors",
    )
    color = ColorField(default="#FFFFFF", verbose_name=_("Color"))
    position = models.PositiveIntegerField(default=0, verbose_name=_("Position"))

    class Meta:
        verbose_name_plural = _("Colors")
        verbose_name = _("Color")
        ordering = ["position"]

    def __str__(self):
        return self.color


class Template(models.Model):
    configuration = models.ForeignKey(
        Configuration,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    language = models.CharField(max_length=2, verbose_name=_("Language"))

    template_file = models.BinaryField(
        verbose_name=_("File"),
        editable=True,
    )

    class Meta:
        verbose_name_plural = _("Templates DOCX")
        verbose_name = _("Template DOCX")
        unique_together = ("configuration", "language")
        ordering = ["language"]

    def __str__(self):
        languages = dict(settings.LANGUAGES)
        return str(languages.get(self.language, self.language))


class Project(models.Model):
    task_id = models.UUIDField(blank=True, null=True)
    task_status = models.CharField(
        max_length=10,
        verbose_name=_("Task Status"),
        choices=CELERY_TASK_STATUS,
        null=True,
        default=CELERY_TASK_STATUS[1][0],
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )
    updated_at = models.DateTimeField(verbose_name=_("Updated at"), auto_now=True)
    author = models.ForeignKey(
        "governanceplatform.User",
        verbose_name=_("Author"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    standard = models.ForeignKey(
        "securityobjectives.standard",
        verbose_name=_("Standard"),
        on_delete=models.CASCADE,
    )
    sectors = models.ManyToManyField(
        "governanceplatform.Sector",
        verbose_name=_("Sectors"),
        blank=True,
    )
    years = ArrayField(models.IntegerField(), verbose_name=_("Years"))
    threshold_for_high_risk = models.IntegerField(
        verbose_name=_("High risk rate threshold"),
        null=True,
    )

    top_ranking = models.PositiveSmallIntegerField(
        verbose_name=_("Ranking"),
        choices=[(3, _("Top 3")), (5, _("Top 5")), (10, _("Top 10"))],
        null=True,
    )
    companies = models.ManyToManyField(
        "governanceplatform.Company",
        through="CompanyProject",
        blank=True,
    )
    selected_file_format = models.CharField(
        verbose_name=_("Export format"),
        choices=[("docx", "docx"), ("pdf", "pdf")],
    )
    selected_languages = ArrayField(models.CharField(), verbose_name=_("Languages"), default=list)
    reference_year = models.PositiveIntegerField(verbose_name=_("Base year"))

    def get_root_sectors(self):
        return list({sector.parent for sector in self.sectors.all()})

    def get_no_childrens_sectors(self):
        return list(self.sectors.filter(parent__isnull=True))

    def __str__(self):
        return self.name or ""

    class Meta:
        verbose_name_plural = _("Projects")
        verbose_name = _("Project")


class CompanyProject(models.Model):
    company = models.ForeignKey(
        "governanceplatform.Company",
        on_delete=models.CASCADE,
        verbose_name=_("Company"),
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("Project"),
    )
    sector = models.ForeignKey(
        "governanceplatform.Sector",
        on_delete=models.CASCADE,
        verbose_name=_("Sector"),
    )
    year = models.PositiveIntegerField()
    is_selected = models.BooleanField(default=False, verbose_name=_("Is selected"))
    has_security_objectives = models.BooleanField(default=False, verbose_name=_("Has security objectives"))
    has_risk_assessment = models.BooleanField(default=False, verbose_name=_("Has risk assessment"))
    statistic_selected = models.BooleanField(default=False, verbose_name=_("Statistics"))
    governance_report_selected = models.BooleanField(default=False, verbose_name=_("Governance report"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "sector", "year"],
                name="unique_company_project_sector",
            )
        ]
        ordering = ["company", "sector", "year"]


# store link for the generated file.
# filename for the project when the files are stored on the end user device
# file_uuid when store on the server to prevent conflict
class GeneratedReport(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name=_("Project"),
        null=True,
        related_name="generated_report",
    )
    file_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name=_("uuid"),
    )
    filename = models.CharField(max_length=255, verbose_name=_("Filename"))
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), auto_now=True)

    def __str__(self):
        return f"{self.filename} ({self.user.email})"

    def get_file_path(self):
        return os.path.join(settings.PATH_FOR_REPORTING_PDF, str(self.project.id), str(self.file_uuid))
