"""Configuration models for self-registration forms."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields


class ProcedureTemplate(models.Model):
    """Identifies a procedure form across versions and defines its regulatory scope."""

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    regulator = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    regulation = models.ForeignKey("governanceplatform.Regulation", on_delete=models.PROTECT)
    sectors = models.ManyToManyField("governanceplatform.Sector", blank=True)
    active = models.BooleanField(default=True)
    public_registry_enabled = models.BooleanField(default=False)
    create_operator_account = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        regulator = str(self.regulator) if self.regulator_id else ""
        regulation = str(self.regulation) if self.regulation_id else ""
        return " - ".join(filter(None, (regulator, regulation))) or str(self.reference)

    class Meta:
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        indexes = [models.Index(fields=["regulator", "regulation", "active"])]


class ProcedureTemplateVersion(TranslatableModel):
    """Defines a numbered form edition with its own pages and submission settings."""

    class State(models.TextChoices):
        """Distinguishes draft, live, and archived editions of a form."""

        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    template = models.ForeignKey(ProcedureTemplate, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    state = models.CharField(max_length=12, choices=State, default=State.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    initial_deadline = models.DateField(null=True, blank=True)
    signature_required = models.BooleanField(default=True)
    translations = TranslatedFields(
        name=models.CharField(max_length=255),
        description=models.TextField(blank=True),
    )

    def __str__(self) -> str:
        name = self.safe_translation_getter("name", any_language=True)
        if name:
            return _("%(name)s (version %(number)s)") % {"name": name, "number": self.version_number}
        return _("Version %(number)s") % {"number": self.version_number}

    class Meta:
        verbose_name = _("template version")
        verbose_name_plural = _("template versions")
        constraints = [
            models.UniqueConstraint(fields=["template", "version_number"], name="sr_template_version_number"),
            models.UniqueConstraint(fields=["template"], condition=models.Q(state="published"), name="sr_template_one_published"),
        ]


class ProcedureTemplatePage(TranslatableModel):
    """Provides a reusable page title and description for a regulator's forms."""

    owner = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    translations = TranslatedFields(
        title=models.CharField(max_length=255),
        description=models.TextField(blank=True),
    )

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or str(_("Template page"))

    class Meta:
        verbose_name = _("template page")
        verbose_name_plural = _("template pages")


class PageInTemplate(models.Model):
    """Places a reusable page category and its questions in one form edition."""

    template_version = models.ForeignKey(ProcedureTemplateVersion, on_delete=models.CASCADE, related_name="pages")
    category = models.ForeignKey(ProcedureTemplatePage, on_delete=models.CASCADE, related_name="pages")
    position = models.PositiveIntegerField()

    def clean(self) -> None:
        super().clean()
        if self.template_version_id and self.category_id and self.template_version.template.regulator_id != self.category.owner_id:
            raise ValidationError({"category": _("Select a page category owned by the form's regulator.")})

    def __str__(self) -> str:
        return str(self.category) if self.category_id else _("Page %(position)s") % {"position": self.position}

    class Meta:
        verbose_name = _("page in template")
        verbose_name_plural = _("pages in template")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_version", "position"], name="sr_page_position", deferrable=models.Deferrable.DEFERRED
            ),
        ]


class ProcedureTemplateQuestion(TranslatableModel):
    """Defines a reusable, regulator-owned question independently of where it appears."""

    class Kind(models.TextChoices):
        """Answer types used to select a question's input and validation rules."""

        TEXT = "text", _("Free text")
        INTEGER = "integer", _("Integer")
        EMAIL = "email", _("Email address")
        PHONE = "phone", _("Phone number")
        DATE = "date", _("Date")
        SINGLE_CHOICE = "single_choice", _("Single choice")
        MULTIPLE_CHOICE = "multiple_choice", _("Multiple choice")
        SINGLE_WITH_COMMENT = "single_comment", _("Single choice with comment")
        MULTIPLE_WITH_COMMENT = "multi_comment", _("Multiple choice with comment")
        COUNTRY = "country", _("Country")
        REGION = "region", _("Region")

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    question_type = models.CharField(max_length=20, choices=Kind, default=Kind.TEXT)
    active = models.BooleanField(default=True)
    copied_from = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)
    translations = TranslatedFields(
        label=models.TextField(),
        help_text=models.TextField(blank=True),
    )

    def __str__(self) -> str:
        return self.safe_translation_getter("label", any_language=True) or str(self.reference)

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")


class ProcedureTemplateChoice(TranslatableModel):
    """Provides a stable identifier and translated label for a selectable answer."""

    question = models.ForeignKey(ProcedureTemplateQuestion, on_delete=models.CASCADE, related_name="choices")
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    position = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    translations = TranslatedFields(label=models.TextField())

    def __str__(self) -> str:
        return self.safe_translation_getter("label", any_language=True) or str(self.reference)

    class Meta:
        verbose_name = _("answer choice")
        verbose_name_plural = _("answer choices")
        ordering = ["position", "pk"]


class ProcedureTemplateQuestionPlacement(models.Model):
    """Places a question on a page and defines disclosure and autofill rules for that use."""

    page = models.ForeignKey(PageInTemplate, on_delete=models.CASCADE, related_name="placements")
    question = models.ForeignKey(ProcedureTemplateQuestion, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    mandatory = models.BooleanField(default=True)
    autofill_allowed = models.BooleanField(default=True)
    visible_to_observers = models.BooleanField(default=True)
    visible_to_public = models.BooleanField(default=False)

    def __str__(self) -> str:
        return str(self.question)

    class Meta:
        verbose_name = _("question order")
        verbose_name_plural = _("question orders")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["page", "position"], name="sr_placement_position", deferrable=models.Deferrable.DEFERRED),
            models.CheckConstraint(
                condition=models.Q(visible_to_public=False) | models.Q(visible_to_observers=True),
                name="sr_public_field_observer_visible",
            ),
        ]
