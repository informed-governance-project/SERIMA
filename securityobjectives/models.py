from colorfield.fields import ColorField
from django.db import models
from django.db.models import Deferrable
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from .globals import STANDARD_ANSWER_REVIEW_STATUS


# Maturity level : define a matury (e.g. sophisticated)
class MaturityLevel(TranslatableModel):
    translations = TranslatedFields(
        label=models.CharField(verbose_name=_("Label"), max_length=255, blank=True, default=None, null=True),
    )
    level = models.IntegerField(verbose_name=_("Level"), default=0)
    standard = models.ForeignKey(
        "Standard",
        on_delete=models.CASCADE,
    )
    color = ColorField(
        default="#FFFFFF",
        verbose_name=_("Color"),
        help_text=_("Color used in reporting module (hexadecimal format)"),
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
        return self.label if self.label is not None else ""

    class Meta:
        verbose_name_plural = _("Maturity levels")
        verbose_name = _("Maturity level")
        constraints = [
            models.UniqueConstraint(
                fields=["level", "standard"],
                name="level_standard",
                deferrable=Deferrable.DEFERRED,
            ),
        ]


# Domain : To categorize the security objectives
class Domain(TranslatableModel):
    translations = TranslatedFields(
        label=models.CharField(verbose_name=_("Label"), max_length=255, blank=True, default=None, null=True),
    )
    position = models.IntegerField(verbose_name=_("Position"), default=0)
    standard = models.ForeignKey(
        "Standard",
        verbose_name=_("Standard"),
        on_delete=models.CASCADE,
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
        return self.label if self.label is not None else ""

    # override save, when we change the standard all the SOs under the domain
    # must be unlinked from the previous standard
    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            return

        old_standard_id = Domain.objects.values_list("standard_id", flat=True).get(pk=self.pk)

        super().save(*args, **kwargs)
        if (self.standard is not None and old_standard_id != self.standard.id) or (self.standard is None and old_standard_id is not None):
            SecurityObjectivesInStandard.objects.filter(security_objective__domain=self).delete()

    class Meta:
        verbose_name_plural = _("Domains")
        verbose_name = _("Domain")
        ordering = ["position"]


# SecurityObjective (SO)
class SecurityObjective(TranslatableModel, models.Model):
    translations = TranslatedFields(
        objective=models.CharField(
            verbose_name=_("Objective"),
            max_length=255,
            blank=True,
            default=None,
            null=True,
        ),
        description=models.TextField(verbose_name=_("Description")),
    )
    unique_code = models.CharField(
        verbose_name=_("Unique code"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    # when we want to delete a SO we need to check if it has been answered if yes, archived instead of delete
    is_archived = models.BooleanField(default=False, verbose_name=_("is archived"))
    domain = models.ForeignKey(
        Domain,
        verbose_name=_("Domain"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="securityobjective",
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

    # override save, when we change the standard all the SOs under the domain
    # must be unlinked from the previous standard
    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            return

        old_domain_id = SecurityObjective.objects.values_list("domain_id", flat=True).get(pk=self.pk)

        super().save(*args, **kwargs)
        if (self.domain is not None and old_domain_id != self.domain.id) or (self.domain is None and old_domain_id is not None):
            old_domain = None
            if old_domain_id:
                old_domain = Domain.objects.get(pk=old_domain_id)
            if old_domain and self.domain and (old_domain.standard.id == self.domain.standard.id):
                return
            SecurityObjectivesInStandard.objects.filter(security_objective=self).delete()

    class Meta:
        verbose_name_plural = _("Security Objectives")
        verbose_name = _("Security Objective")
        constraints = [
            models.UniqueConstraint(
                fields=["unique_code", "creator"],
                name="Unique_unique_code",
                deferrable=Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        objective_translation = self.safe_translation_getter("objective", any_language=True)
        return f"{self.unique_code}:{objective_translation}" or ""


# Email sent from regulator to operator
class SecurityObjectiveEmail(TranslatableModel, models.Model):
    translations = TranslatedFields(
        subject=models.CharField(
            verbose_name=_("Subject"),
            max_length=255,
        ),
        content=models.TextField(
            verbose_name=_("Content"),
            help_text=_("""Available placeholders: #SO_REFERENCE#"""),
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
        verbose_name_plural = _("Email templates")
        verbose_name = _("Email template")


# Standard : A group of security objectives
class Standard(TranslatableModel):
    translations = TranslatedFields(
        label=models.CharField(verbose_name=_("Label"), max_length=255, blank=True, default=None, null=True),
        description=models.TextField(verbose_name=_("Description")),
    )
    regulator = models.ForeignKey(
        "governanceplatform.regulator",
        verbose_name=_("Regulator"),
        on_delete=models.CASCADE,
    )
    regulation = models.ForeignKey(
        "governanceplatform.regulation",
        verbose_name=_("Regulation"),
        on_delete=models.CASCADE,
    )
    security_objectives = models.ManyToManyField(
        SecurityObjective,
        verbose_name=_("Security objectives"),
        through="SecurityObjectivesInStandard",
    )
    # email
    submission_email = models.ForeignKey(
        SecurityObjectiveEmail,
        verbose_name=_("Submission e-mail"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="security_objective_submission_email",
    )
    security_objective_status_changed_email = models.ForeignKey(
        SecurityObjectiveEmail,
        verbose_name=_("Email for status change"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="security_objective_status_changed_email",
    )
    security_objective_closure_email = models.ForeignKey(
        SecurityObjectiveEmail,
        verbose_name=_("Email for closure"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="security_objective_closure_email",
    )

    def __str__(self):
        label_translation = self.safe_translation_getter("label", any_language=True)
        if label_translation:
            return label_translation

        fallback_languages = self.get_fallback_languages() or []

        if fallback_languages:
            label_translation = self.get_translation(fallback_languages[0]).label
        return label_translation or ""

    class Meta:
        verbose_name_plural = _("Standards")
        verbose_name = _("Standard")


class SecurityObjectivesInStandard(models.Model):
    security_objective = models.OneToOneField(
        SecurityObjective,
        verbose_name=_("Security Objective"),
        on_delete=models.CASCADE,
        related_name="standard_link",
    )
    standard = models.ForeignKey(
        Standard,
        on_delete=models.CASCADE,
        related_name="security_objectives_set",
    )
    position = models.IntegerField(verbose_name=_("Position"), default=0)
    priority = models.IntegerField(verbose_name=_("Priority"), default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["security_objective", "standard"],
                name="unique_security_objective_per_standard",
            ),
        ]
        ordering = ["position"]

    def __str__(self):
        return str(self.security_objective)


# link between security measure, SO and maturity
class SecurityMeasure(TranslatableModel):
    security_objective = models.ForeignKey(
        SecurityObjective,
        verbose_name=_("Security Objective"),
        on_delete=models.CASCADE,
    )
    maturity_level = models.ForeignKey(MaturityLevel, verbose_name=_("Level"), on_delete=models.SET_NULL, null=True)
    translations = TranslatedFields(
        description=models.TextField(verbose_name=_("Description")),
        evidence=models.TextField(verbose_name=_("Evidence")),
    )
    position = models.IntegerField(verbose_name=_("Position"), default=0)
    # when we want to delete a Security Measure we need to check if it has been answered if yes, archived instead of delete
    is_archived = models.BooleanField(default=False, verbose_name=_("is archived"))

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
        return self.description if self.description is not None else ""

    class Meta:
        verbose_name_plural = _("Security Measures")
        verbose_name = _("Security Measure")


# A group of StandardAnswer to have the versionning functionnality
class StandardAnswerGroup(models.Model):
    notification_date = models.DateTimeField(verbose_name=_("Notification date"), default=timezone.now)
    # we save the company
    company = models.ForeignKey(
        "governanceplatform.Company",
        verbose_name=_("Company"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    # XXXXXXXXXX-FFFFFFFFFF-SSS-SSS-NNNN-YYYY
    # XXXXXXXXXX = operator
    # SSS-SSS = sector and subsector
    # FFFFFFFFFF = framework limited to 10 chars
    # YYYY = Year
    # NNNN = Number
    group_id = models.CharField(max_length=39, verbose_name=_("Group ID"), unique=True)


# The answers of the operator
class StandardAnswer(models.Model):
    standard = models.ForeignKey(
        Standard,
        verbose_name=_("Standard"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="standardanswer",
    )
    creation_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation date"))

    last_update = models.DateTimeField(auto_now=True, verbose_name=_("Last update"))
    submit_date = models.DateTimeField(blank=True, default=None, null=True, verbose_name=_("Submission date"))
    status = models.CharField(
        max_length=5,
        choices=STANDARD_ANSWER_REVIEW_STATUS,
        blank=False,
        default=STANDARD_ANSWER_REVIEW_STATUS[0][0],
        verbose_name=_("Status"),
    )
    submitter_user = models.ForeignKey(
        "governanceplatform.user",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Submitter"),
    )
    submitter_company = models.ForeignKey(
        "governanceplatform.company",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Submitter"),
    )
    # to display in case we delete the user or the company
    creator_name = models.CharField(
        verbose_name=_("Creator name"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    creator_company_name = models.CharField(
        verbose_name=_("Company of creator"),
        max_length=255,
        blank=True,
        default=None,
        null=True,
    )
    # the year for the one
    year_of_submission = models.PositiveIntegerField(verbose_name=_("Year of submission"))
    sectors = models.ManyToManyField("governanceplatform.sector", verbose_name=_("Sectors"))
    review_comment = models.TextField(blank=True, default=None, null=True, verbose_name=_("Review comment"))
    group = models.ForeignKey(StandardAnswerGroup, on_delete=models.CASCADE, verbose_name=_("Group"))

    def get_root_sectors(self):
        return list({sector.parent for sector in self.sectors.all()})

    def get_no_childrens_sectors(self):
        return list(self.sectors.filter(parent__isnull=True))


# the answer of the operator by SM
class SecurityMeasureAnswer(models.Model):
    security_measure_notification_date = models.DateTimeField(verbose_name=_("Notification date"), default=timezone.now)
    standard_answer = models.ForeignKey(
        StandardAnswer,
        verbose_name=_("Standard Answer"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="securitymeasureanswers",
    )
    security_measure = models.ForeignKey(
        SecurityMeasure,
        verbose_name=_("Security Measure"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="securitymeasureanswers",
    )
    justification = models.TextField(verbose_name=_("Justification"))
    is_implemented = models.BooleanField(default=False, verbose_name=_("Implemented"))
    review_comment = models.TextField(verbose_name=_("Review comment"))


# SO Status set by regulator
class SecurityObjectiveStatus(models.Model):
    standard_answer = models.ForeignKey(
        StandardAnswer,
        verbose_name=_("Security objectives statement"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
    )
    security_objective = models.ForeignKey(
        SecurityObjective,
        verbose_name=_("Security Objective"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
    )
    status = models.CharField(
        choices=[
            ("NOT_REVIEWED", _("Not reviewed")),
            ("PASS", _("Passed")),
            ("FAIL", _("Fail")),
        ],
        blank=False,
        default="NOT_REVIEWED",
        verbose_name=_("Status"),
    )

    score = models.DecimalField(
        verbose_name=_("Score"),
        default=0,
        max_digits=4,
        decimal_places=2,
    )

    actions = models.TextField(
        blank=True,
        default=None,
        null=True,
        verbose_name=_("Planned Measures"),
    )

    is_completely_filled_out = models.BooleanField(default=False, verbose_name=_("It is completely filled out"))

    def __str__(self):
        return str(self.security_objective)


class LogStandardAnswer(models.Model):
    user = models.ForeignKey(
        "governanceplatform.User",
        on_delete=models.SET_NULL,
        verbose_name=_("User"),
        null=True,
    )
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"), default=timezone.now)
    # save full name in case of the user is deleted to keep the name
    user_full_name = models.CharField(max_length=250, verbose_name=_("User full name"))
    role = models.CharField(max_length=250, verbose_name=_("Role"))
    entity_name = models.CharField(max_length=250, verbose_name=_("Entity name"))
    standard_answer = models.ForeignKey(
        StandardAnswer,
        on_delete=models.CASCADE,
        null=True,
        default=None,
    )
    action = models.CharField(max_length=250, verbose_name=_("Action performed"))

    def save(self, *args, **kwargs):
        self.user_full_name = self.user.get_full_name()
        super().save(*args, **kwargs)
