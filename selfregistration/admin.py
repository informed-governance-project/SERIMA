"""Administration for self-registration form configuration."""

from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from governanceplatform.admin import CustomTranslatableAdmin, admin_site
from governanceplatform.helpers import user_in_group
from governanceplatform.models import RegulatorUser, User

from .models import (
    PageInTemplate,
    ProcedureTemplate,
    ProcedureTemplateChoice,
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateQuestionPlacement,
    ProcedureTemplateVersion,
)

if TYPE_CHECKING:
    from typing import Any

    from django.contrib.admin.options import InlineModelAdmin
    from django.db.models import ForeignKey, Model, QuerySet
    from django.forms.models import BaseInlineFormSet
    from django.http import HttpRequest


def administered_regulators(request: HttpRequest) -> QuerySet:
    """Limit access to regulators where the user administers the enabled module."""
    user = request.user
    if not isinstance(user, User):
        return RegulatorUser.objects.none().values("regulator_id")
    return RegulatorUser.objects.filter(
        user=user, is_regulator_administrator=True, regulator__functionalities__type="selfregistration"
    ).values("regulator_id")


class ProcedureConfigurationAdmin[ObjectT: Model](ModelAdmin):
    """Apply the same module access and regulator scope across configuration screens."""

    actions = None
    regulator_field: str
    fixed_fields: tuple[str, ...] = ()
    add_readonly_fields: tuple[str, ...] = ()
    relation_scopes: dict[str, str] = {}

    def has_module_permission(self, request: HttpRequest) -> bool:
        return self.has_view_permission(request)

    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        return self.has_sr_access(request) and super().has_view_permission(request, obj)

    def has_sr_access(self, request: HttpRequest) -> bool:
        return (
            isinstance(request.user, User)
            and user_in_group(request.user, "RegulatorAdmin")
            and "selfregistration" in request.user.get_module_permissions()
            and administered_regulators(request).exists()
        )

    def has_delete_permission(self, request: HttpRequest, obj: ObjectT | None = None) -> bool:
        return (
            self.has_sr_access(request)
            and self.has_configuration_permission(request, "delete")
            and (obj is None or self.get_queryset(request).filter(pk=obj.pk).exists())
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet[ObjectT]:
        queryset = super().get_queryset(request)
        if not self.has_view_permission(request):
            return queryset.none()
        return queryset.filter(**{f"{self.regulator_field}__in": administered_regulators(request)})

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self.has_sr_access(request) and self.has_configuration_permission(request, "add")

    def has_change_permission(self, request: HttpRequest, obj: ObjectT | None = None) -> bool:
        return self.has_sr_access(request) and self.has_configuration_permission(request, "change") and self.is_editable(obj)

    def has_configuration_permission(self, request: HttpRequest, action: str) -> bool:
        return request.user.has_perm(f"selfregistration.{action}_{self.model._meta.model_name}")

    def is_editable(self, obj: ObjectT | None) -> bool:
        return True

    def get_readonly_fields(self, request: HttpRequest, obj: ObjectT | None = None) -> tuple[str, ...]:
        return (*self.add_readonly_fields, *self.fixed_fields) if obj else self.add_readonly_fields

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if scope := self.relation_scopes.get(db_field.name):
            queryset = db_field.remote_field.model._default_manager.filter(**{f"{scope}__in": administered_regulators(request)})
            if self.model is ProcedureTemplateChoice and db_field.name == "question":
                # Adding a choice would also change every published or archived version using that question.
                queryset = queryset.exclude(
                    proceduretemplatequestionplacement__page__template_version__state__in=(
                        ProcedureTemplateVersion.State.PUBLISHED,
                        ProcedureTemplateVersion.State.ARCHIVED,
                    )
                )
            if db_field.remote_field.model is ProcedureTemplate:
                queryset = queryset.select_related("regulator", "regulation").prefetch_related(
                    "regulator__translations", "regulation__translations"
                )
            elif issubclass(db_field.remote_field.model, TranslatableModel):
                queryset = queryset.prefetch_related("translations")
            kwargs["queryset"] = queryset.distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedureTemplateAdminForm(forms.ModelForm):
    """Validate the selected regulation against the template's regulator."""

    def clean(self) -> dict:
        data = super().clean() or self.cleaned_data
        regulator = data.get("regulator")
        regulation = data.get("regulation")
        if regulator and regulation and not regulation.regulators.filter(pk=regulator.pk).exists():
            self.add_error("regulation", _("Select a regulation assigned to this regulator."))
        return data


class OrderedQuestionnaireInlineForm(forms.ModelForm):
    """Defer position conflicts until the formset can validate the final order."""

    def validate_constraints(self) -> None:
        # The formset validates final positions together, including swaps. Keep
        # per-row validation for constraints unrelated to the parent or position.
        try:
            exclusions = self._get_validation_exclusions()  # type: ignore[attr-defined]
            self.instance.validate_constraints(exclude=exclusions | {"position"})
        except forms.ValidationError as error:
            self.add_error(None, error)


class ProcedureQuestionInline(TabularInline):
    """Set a question's order and options for its placement on a page."""

    model = ProcedureTemplateQuestionPlacement
    form = OrderedQuestionnaireInlineForm
    fields = ("position", "question", "mandatory", "autofill_allowed", "visible_to_observers", "visible_to_public")
    verbose_name = _("question")
    verbose_name_plural = _("Questions")
    show_title = False
    extra = 0

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if db_field.name == "question":
            regulator_id = getattr(request, "_sr_questionnaire_regulator_id", None)
            kwargs["queryset"] = ProcedureTemplateQuestion.objects.filter(owner_id=regulator_id).prefetch_related("translations")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedurePageInline(StackedInline):
    """Place a reusable page in a version and edit its questions in the same save."""

    model = PageInTemplate
    form = OrderedQuestionnaireInlineForm
    fields = ("position", "category")
    inlines = [ProcedureQuestionInline]
    verbose_name = _("page")
    verbose_name_plural = _("Pages")
    extra = 0

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if db_field.name == "category":
            regulator_id = getattr(request, "_sr_questionnaire_regulator_id", None)
            kwargs["queryset"] = ProcedureTemplatePage.objects.filter(owner_id=regulator_id).prefetch_related("translations")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProcedureTemplate, site=admin_site)
class ProcedureTemplateAdmin(ProcedureConfigurationAdmin[ProcedureTemplate]):
    """Manage the template associated with a regulator and regulation pair."""

    form = ProcedureTemplateAdminForm
    regulator_field = "regulator_id"
    relation_scopes = {"regulator": "pk", "regulation": "regulators__pk"}
    fixed_fields = ("regulator", "regulation")
    list_display = ("reference", "regulator", "regulation", "active", "public_registry_enabled")
    list_filter = ("active", "public_registry_enabled")
    list_select_related = ("regulator", "regulation")
    search_fields = ("reference",)


@admin.register(ProcedureTemplateVersion, site=admin_site)
class ProcedureTemplateVersionAdmin(ProcedureConfigurationAdmin[ProcedureTemplateVersion], CustomTranslatableAdmin):
    """Edit the questionnaire on saved drafts and display published versions as read-only."""

    regulator_field = "template__regulator_id"
    relation_scopes = {"template": "regulator_id"}
    fixed_fields = ("template",)
    add_readonly_fields = ("state", "published_at")
    list_display = ("template", "version_number", "name", "state", "published_at")
    list_select_related = ("template__regulator", "template__regulation")
    list_filter = ("state", "signature_required")
    search_fields = ("translations__name", "template__reference")
    inlines = [ProcedurePageInline]

    def is_editable(self, obj: ProcedureTemplateVersion | None) -> bool:
        return obj is None or obj.state == ProcedureTemplateVersion.State.DRAFT

    def get_fieldsets(self, request: HttpRequest, obj: ProcedureTemplateVersion | None = None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None:
            return fieldsets
        title, options = fieldsets[0]
        return [
            (title, {**options, "description": _("Save the version and continue editing to start building its questionnaire.")}),
            *fieldsets[1:],
        ]

    def get_inline_instances(self, request: HttpRequest, obj: ProcedureTemplateVersion | None = None) -> list[InlineModelAdmin]:
        if obj is None:
            return []
        # Unfold also builds question formsets for unsaved pages, so scope their choices to the saved version's regulator.
        request._sr_questionnaire_regulator_id = obj.template.regulator_id  # type: ignore[attr-defined]
        return super().get_inline_instances(request, obj)

    def construct_change_message(
        self, request: HttpRequest, form: forms.ModelForm, formsets: list[BaseInlineFormSet], add: bool = False
    ) -> list[dict[str, Any]]:
        # Django's change log only sees top-level formsets unless the saved question formsets are supplied explicitly.
        nested_formsets = [
            inline.formset
            for formset in formsets
            for page_form in formset.forms
            for inline in getattr(page_form, "nested_formsets", ())
            if hasattr(inline.formset, "new_objects")
        ]
        return super().construct_change_message(request, form, [*formsets, *nested_formsets], add)


@admin.register(ProcedureTemplatePage, site=admin_site)
class ProcedureTemplatePageAdmin(ProcedureConfigurationAdmin[ProcedureTemplatePage], CustomTranslatableAdmin):
    """Manage shared page definitions without changing pages used by published or archived versions."""

    regulator_field = "owner_id"
    relation_scopes = {"owner": "pk"}
    fixed_fields = ("owner",)
    list_display = ("title", "owner")
    search_fields = ("translations__title",)

    def is_editable(self, obj: ProcedureTemplatePage | None) -> bool:
        return obj is None or not obj.pages.exclude(template_version__state=ProcedureTemplateVersion.State.DRAFT).exists()


def question_is_editable(question: ProcedureTemplateQuestion) -> bool:
    """Use the same version lock for a reusable question and its answer choices."""
    return (
        not ProcedureTemplateQuestionPlacement.objects.filter(question=question)
        .exclude(page__template_version__state=ProcedureTemplateVersion.State.DRAFT)
        .exists()
    )


@admin.register(ProcedureTemplateQuestion, site=admin_site)
class ProcedureTemplateQuestionAdmin(ProcedureConfigurationAdmin[ProcedureTemplateQuestion], CustomTranslatableAdmin):
    """Manage reusable questions whose wording may be shared by several questionnaires."""

    regulator_field = "owner_id"
    relation_scopes = {"owner": "pk", "copied_from": "owner_id"}
    fixed_fields = ("owner",)
    list_display = ("label", "question_type", "owner", "active", "reference")
    list_filter = ("question_type", "active")
    search_fields = ("translations__label", "reference")

    def is_editable(self, obj: ProcedureTemplateQuestion | None) -> bool:
        return obj is None or question_is_editable(obj)


@admin.register(ProcedureTemplateChoice, site=admin_site)
class ProcedureTemplateChoiceAdmin(ProcedureConfigurationAdmin[ProcedureTemplateChoice], CustomTranslatableAdmin):
    """Manage answer choices under the same version lock as their question."""

    regulator_field = "question__owner_id"
    relation_scopes = {"question": "owner_id"}
    fixed_fields = ("question",)
    list_display = ("label", "question", "position", "active")
    list_filter = ("active",)
    search_fields = ("translations__label", "reference")

    def is_editable(self, obj: ProcedureTemplateChoice | None) -> bool:
        return obj is None or question_is_editable(obj.question)
