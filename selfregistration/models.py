"""Configuration models for self-registration forms."""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields


class ProcedureTemplate(TranslatableModel):
    """Defines a dated procedure edition and its regulatory and submission settings."""

    class State(models.TextChoices):
        """Distinguishes draft, live, and archived editions of a form."""

        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    regulator = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    regulation = models.ForeignKey("governanceplatform.Regulation", on_delete=models.PROTECT)
    sectors = models.ManyToManyField("governanceplatform.Sector", blank=True)
    active = models.BooleanField(default=True)
    public_registry_enabled = models.BooleanField(default=False)
    create_operator_account = models.BooleanField(default=True)
    state = models.CharField(max_length=12, choices=State, default=State.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    periodic_update = models.DurationField(null=True, blank=True, validators=[MinValueValidator(timedelta())])
    delay = models.PositiveIntegerField(default=0, verbose_name=_("Delay (days)"))
    creation_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    signature_required = models.BooleanField(default=True)
    translations = TranslatedFields(
        name=models.CharField(max_length=255),
        description=models.TextField(blank=True),
    )

    def __str__(self) -> str:
        name = self.safe_translation_getter("name", any_language=True)
        scope = " - ".join(str(item) for item in (getattr(self, "regulator", None), getattr(self, "regulation", None)) if item)
        edition = formats.date_format(timezone.localtime(self.last_update), "Y-m-d H:i:s") if self.last_update else ""
        return " — ".join(filter(None, (name, scope, edition))) or str(self.reference)

    def clean(self) -> None:
        super().clean()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list("regulator_id", "regulation_id").first()
            if previous is not None and previous != (self.regulator_id, self.regulation_id):
                raise ValidationError(_("The regulator and regulation cannot be changed after creation."))

    class Meta:
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        ordering = ["-last_update", "-pk"]
        indexes = [models.Index(fields=["regulator", "regulation", "active"])]
        constraints = [
            models.UniqueConstraint(
                fields=["regulator", "regulation"], condition=models.Q(state="published"), name="sr_template_one_published"
            ),
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

    template_version = models.ForeignKey(ProcedureTemplate, on_delete=models.CASCADE, related_name="pages", verbose_name=_("Procedure"))
    category = models.ForeignKey(ProcedureTemplatePage, on_delete=models.CASCADE, related_name="pages")
    position = models.PositiveIntegerField()

    def clean(self) -> None:
        super().clean()
        if self.template_version_id and self.category_id and self.template_version.regulator_id != self.category.owner_id:
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

    CHOICE_TYPES = (Kind.SINGLE_CHOICE, Kind.MULTIPLE_CHOICE, Kind.SINGLE_WITH_COMMENT, Kind.MULTIPLE_WITH_COMMENT)

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    question_type = models.CharField(max_length=20, choices=Kind, default=Kind.TEXT)
    translations = TranslatedFields(
        label=models.TextField(),
        help_text=models.TextField(blank=True),
    )

    def __str__(self) -> str:
        return self.safe_translation_getter("label", any_language=True) or str(self.reference)

    def clean(self) -> None:
        super().clean()
        if (
            self.pk
            and self.question_type not in self.CHOICE_TYPES
            and ProcedureTemplateConditionalQuestion.objects.filter(trigger_question__question=self).exists()
        ):
            raise ValidationError({"question_type": _("Remove the conditional rules using this question before changing its type.")})

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")


class ProcedureTemplateChoice(TranslatableModel):
    """Provides a stable identifier and translated label for a selectable answer."""

    question = models.ForeignKey(ProcedureTemplateQuestion, on_delete=models.CASCADE, related_name="choices")
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    position = models.PositiveIntegerField()
    translations = TranslatedFields(label=models.TextField())

    def __str__(self) -> str:
        return self.safe_translation_getter("label", any_language=True) or str(self.reference)

    class Meta:
        verbose_name = _("answer choice")
        verbose_name_plural = _("answer choices")
        ordering = ["position", "pk"]


class ProcedureTemplateQuestionGroup(TranslatableModel):
    """Defines an ordered set of questions that can repeat within one form edition."""

    owner = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT)
    min_occurrences = models.PositiveIntegerField(default=1)
    max_occurrences = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1)])
    translations = TranslatedFields(title=models.CharField(max_length=255))

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or str(_("Question group"))

    class Meta:
        verbose_name = _("question group")
        verbose_name_plural = _("question groups")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_occurrences__gte=1) & models.Q(max_occurrences__gte=models.F("min_occurrences")),
                name="sr_group_occurrence_bounds",
            ),
        ]


class ProcedureTemplateQuestionPlacement(models.Model):
    """Orders page content and the individual questions within a repeatable group."""

    page = models.ForeignKey(PageInTemplate, on_delete=models.CASCADE, related_name="placements", null=True, blank=True)
    parent_group = models.ForeignKey(
        ProcedureTemplateQuestionGroup, on_delete=models.CASCADE, related_name="questions", null=True, blank=True
    )
    question = models.ForeignKey(ProcedureTemplateQuestion, on_delete=models.CASCADE, null=True, blank=True)
    question_group = models.OneToOneField(
        ProcedureTemplateQuestionGroup, on_delete=models.CASCADE, related_name="placement", null=True, blank=True
    )
    position = models.PositiveIntegerField()
    mandatory = models.BooleanField(default=True)
    autofill_allowed = models.BooleanField(default=True)
    visible_to_observers = models.BooleanField(default=True)
    visible_to_public = models.BooleanField(default=False)
    is_conditional = models.BooleanField(default=False, verbose_name=_("Conditional display"))

    @property
    def group_placement(self):
        return getattr(self.parent_group, "placement", None)

    @property
    def containing_page(self) -> PageInTemplate | None:
        group_placement = self.group_placement
        return group_placement.page if group_placement else self.page

    def clean(self) -> None:
        super().clean()
        if not self.question_id and not self.question_group_id:
            raise ValidationError({"question": _("Select a question or a question group.")})
        if self.question_group_id and (self.question_id or self.parent_group_id):
            raise ValidationError({"question_group": _("A group occupies its own row on a page.")})

        if self.parent_group is not None:
            regulator_id = self.parent_group.owner_id
        elif self.page is not None:
            regulator_id = self.page.template_version.regulator_id
        else:
            return

        for field in ("question", "question_group"):
            if getattr(self, f"{field}_id") and getattr(self, field).owner_id != regulator_id:
                raise ValidationError({field: _("Select an item owned by the same regulator.")})

        if not self.pk:
            return
        previous = type(self).objects.get(pk=self.pk)
        question_changed = (self.question_id, self.page_id, self.parent_group_id) != (
            previous.question_id,
            previous.page_id,
            previous.parent_group_id,
        )
        group_changed = self.question_group_id != previous.question_group_id
        conditional_changed = self.is_conditional != previous.is_conditional
        if (question_changed or conditional_changed) and self.conditional_triggers.exists():
            raise ValidationError(
                _("Remove the rules using this question as a trigger before changing its question or conditional status.")
            )
        if (question_changed or group_changed or conditional_changed) and self.conditional_targets.exists():
            raise ValidationError(_("Remove the rules targeting this item before changing its question, group or conditional status."))
        if group_changed and self.group_conditional_rules.exists():
            raise ValidationError(_("Remove the group's conditional rules before replacing the group on this page."))

    def __str__(self) -> str:
        return str(self.question_group or self.question or _("Page item"))

    class Meta:
        verbose_name = _("question order")
        verbose_name_plural = _("question orders")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["page", "position"], name="sr_placement_position", deferrable=models.Deferrable.DEFERRED),
            models.UniqueConstraint(
                fields=["parent_group", "position"], name="sr_group_question_position", deferrable=models.Deferrable.DEFERRED
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(page__isnull=False, parent_group__isnull=True)
                    & (
                        models.Q(question__isnull=False, question_group__isnull=True)
                        | models.Q(question__isnull=True, question_group__isnull=False)
                    )
                    | models.Q(page__isnull=True, parent_group__isnull=False, question__isnull=False, question_group__isnull=True)
                ),
                name="sr_questionnaire_placement_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(visible_to_public=False) | models.Q(visible_to_observers=True),
                name="sr_public_field_observer_visible",
            ),
        ]


class ProcedureTemplateConditionalQuestion(models.Model):
    """Shows a specific questionnaire placement when a selected choice is answered."""

    template_version = models.ForeignKey(
        ProcedureTemplate, on_delete=models.CASCADE, related_name="conditional_questions", verbose_name=_("Procedure")
    )
    trigger_question = models.ForeignKey(
        ProcedureTemplateQuestionPlacement,
        on_delete=models.CASCADE,
        related_name="conditional_triggers",
        verbose_name=_("Trigger question"),
    )
    trigger_choice = models.ForeignKey(ProcedureTemplateChoice, on_delete=models.CASCADE, verbose_name=_("Selected answer"))
    target = models.ForeignKey(
        ProcedureTemplateQuestionPlacement, on_delete=models.CASCADE, related_name="conditional_targets", verbose_name=_("Conditional item")
    )
    # Removing a group from a page also removes rules involving its questions.
    group_placement = models.ForeignKey(
        ProcedureTemplateQuestionPlacement, on_delete=models.CASCADE, related_name="group_conditional_rules", null=True, editable=False
    )

    def clean(self) -> None:
        super().clean()
        source = getattr(self, "trigger_question", None)
        target = getattr(self, "target", None)
        choice = getattr(self, "trigger_choice", None)
        if not source or not target or not self.template_version_id:
            return

        if not source.question or source.question.question_type not in ProcedureTemplateQuestion.CHOICE_TYPES or source.is_conditional:
            raise ValidationError({"trigger_question": _("Select an unconditional question with predefined answer choices.")})
        if choice and choice.question_id != source.question_id:
            raise ValidationError({"trigger_choice": _("The selected answer must belong to the trigger question.")})
        if not target.is_conditional:
            raise ValidationError({"target": _("Mark this item as conditional in the template version first.")})

        source_page, target_page = source.containing_page, target.containing_page
        if not source_page or source_page.template_version_id != self.template_version_id:
            raise ValidationError({"trigger_question": _("The trigger question must be placed in the selected template version.")})
        if not target_page or target_page.pk != source_page.pk:
            raise ValidationError({"target": _("The conditional item must be on the same page as the trigger question.")})
        if source.parent_group_id and source.parent_group_id != target.parent_group_id:
            raise ValidationError({"target": _("A trigger inside a repeatable group must target a question in that same group.")})
        self.group_placement = target.group_placement or source.group_placement

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.trigger_question} → [{self.trigger_choice}] → {self.target}"

    class Meta:
        verbose_name = _("conditional question")
        verbose_name_plural = _("conditional questions")
        constraints = [
            models.UniqueConstraint(fields=["trigger_question", "trigger_choice"], name="sr_one_conditional_target_per_answer"),
            models.CheckConstraint(condition=~models.Q(trigger_question=models.F("target")), name="sr_conditional_distinct_placements"),
        ]
