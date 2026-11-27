"""Administration for self-registration form configuration."""

from collections import Counter
from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.forms.models import BaseInlineFormSet
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from parler.forms import TranslatableBaseInlineFormSet
from parler.models import TranslatableModel
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from governanceplatform.admin import CustomTranslatableAdmin, CustomTranslatableTabularInline, admin_site
from governanceplatform.forms import CustomTranslatableAdminForm
from governanceplatform.helpers import user_in_group
from governanceplatform.models import Regulator, RegulatorUser, User

from .models import (
    PageInTemplate,
    ProcedureTemplate,
    ProcedureTemplateChoice,
    ProcedureTemplateConditionalQuestion,
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateQuestionGroup,
    ProcedureTemplateQuestionPlacement,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from django.contrib.admin.options import InlineModelAdmin
    from django.db.models import ForeignKey, Model, QuerySet
    from django.http import HttpRequest


def administered_regulators(request: HttpRequest) -> QuerySet:
    """Limit access to regulators where the user administers the enabled module."""
    user = request.user
    if not isinstance(user, User):
        return RegulatorUser.objects.none().values("regulator_id")
    return RegulatorUser.objects.filter(
        user=user, is_regulator_administrator=True, regulator__functionalities__type="selfregistration"
    ).values("regulator_id")


def locked_question_placements() -> QuerySet[ProcedureTemplateQuestionPlacement]:
    """Find question uses in both direct placements and repeatable groups on locked versions."""
    states = (ProcedureTemplate.State.PUBLISHED, ProcedureTemplate.State.ARCHIVED)
    return ProcedureTemplateQuestionPlacement.objects.filter(question__isnull=False).filter(
        Q(page__template_version__state__in=states) | Q(parent_group__placement__page__template_version__state__in=states)
    )


class ProcedureConfigurationAdmin[ObjectT: Model](ModelAdmin):
    """Apply the same module access and regulator scope across configuration screens."""

    regulator_field: str
    share_catalogue = False
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
            and (obj is None or self.regulator_scope(request, self.get_queryset(request)).filter(pk=obj.pk).exists())
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet[ObjectT]:
        queryset = super().get_queryset(request)
        if not self.has_view_permission(request):
            return queryset.none()
        return queryset if self.share_catalogue else self.regulator_scope(request, queryset)

    def regulator_scope(self, request: HttpRequest, queryset: QuerySet[ObjectT]) -> QuerySet[ObjectT]:
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
            if issubclass(db_field.remote_field.model, TranslatableModel):
                queryset = queryset.prefetch_related("translations")
            kwargs["queryset"] = queryset.distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedureTemplateAdminForm(CustomTranslatableAdminForm):
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
    """Set the order and answer options of individual questions in a group."""

    model = ProcedureTemplateQuestionPlacement
    fk_name = "parent_group"
    form = OrderedQuestionnaireInlineForm
    fields: tuple[str, ...] = (
        "position",
        "question",
        "is_conditional",
        "mandatory",
        "autofill_allowed",
        "visible_to_observers",
        "visible_to_public",
    )
    verbose_name = _("question")
    verbose_name_plural = _("Questions")
    show_title = False
    extra = 0

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if db_field.name == "question":
            regulator_id = getattr(request, "_sr_questionnaire_regulator_id", None)
            kwargs["queryset"] = ProcedureTemplateQuestion.objects.filter(owner_id=regulator_id).prefetch_related("translations")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedurePageContentInline(ProcedureQuestionInline):
    """Place questions and groups in the same sequence within a page."""

    fk_name = "page"
    fields = (
        "position",
        "question",
        "question_group",
        "edit_group",
        "is_conditional",
        "mandatory",
        "autofill_allowed",
        "visible_to_observers",
        "visible_to_public",
    )
    readonly_fields = ("edit_group",)
    verbose_name = _("page item")
    verbose_name_plural = _("Page contents")

    @admin.display(description=_("Group settings"))
    def edit_group(self, obj: ProcedureTemplateQuestionPlacement | None):
        if obj and obj.question_group_id:
            url = reverse(f"{self.admin_site.name}:selfregistration_proceduretemplatequestiongroup_change", args=[obj.question_group_id])
            return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, _("Edit group"))
        return None

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if db_field.name == "question_group":
            regulator_id = getattr(request, "_sr_questionnaire_regulator_id", None)
            kwargs["queryset"] = ProcedureTemplateQuestionGroup.objects.filter(owner_id=regulator_id).prefetch_related("translations")
            kwargs["help_text"] = _("Choose a question or a group. Answer options apply to individual questions.")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedurePagesFormSet(BaseInlineFormSet):
    """Validate group assignments across every page submitted in the version form."""

    def clean(self) -> None:
        super().clean()
        group_forms = {}
        for page_form in self.forms:
            if page_form.errors or page_form.cleaned_data.get("DELETE"):
                continue
            for inline in getattr(page_form, "nested_formsets", ()):
                for item in inline.formset.forms:
                    if item.errors or item.cleaned_data.get("DELETE") or not (group := item.cleaned_data.get("question_group")):
                        continue
                    if group.pk in group_forms:
                        item.add_error("question_group", _("This group already appears on another row of this version."))
                    else:
                        group_forms[group.pk] = item

        if group_forms:
            # Serialize assignments from different drafts before checking for a competing placement.
            list(ProcedureTemplateQuestionGroup.objects.filter(pk__in=group_forms).order_by("pk").select_for_update())
            for group_id, placement_id in ProcedureTemplateQuestionPlacement.objects.filter(question_group_id__in=group_forms).values_list(
                "question_group_id", "pk"
            ):
                if group_forms[group_id].instance.pk != placement_id:
                    group_forms[group_id].add_error("question_group", _("This group is already placed on a page."))


class ProcedurePageInline(StackedInline):
    """Place a reusable page in a version and edit its contents in the same save."""

    model = PageInTemplate
    form = OrderedQuestionnaireInlineForm
    formset = ProcedurePagesFormSet
    fields = ("position", "category")
    inlines = [ProcedurePageContentInline]
    verbose_name = _("page")
    verbose_name_plural = _("Pages")
    extra = 0

    def formfield_for_foreignkey(self, db_field: ForeignKey, request: HttpRequest, **kwargs):
        if db_field.name == "category":
            regulator_id = getattr(request, "_sr_questionnaire_regulator_id", None)
            kwargs["queryset"] = ProcedureTemplatePage.objects.filter(owner_id=regulator_id).prefetch_related("translations")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProcedureTemplate, site=admin_site)
class ProcedureTemplateAdmin(ProcedureConfigurationAdmin[ProcedureTemplate], CustomTranslatableAdmin):
    """Edit dated drafts and manage their publication lifecycle."""

    form = ProcedureTemplateAdminForm
    regulator_field = "regulator_id"
    relation_scopes = {"regulator": "pk", "regulation": "regulators__pk"}
    fixed_fields = ("regulator", "regulation", "creation_date", "last_update")
    add_readonly_fields = ("state", "published_at")
    list_display = ("name", "regulator", "regulation", "state", "last_update", "creation_date", "active")
    list_select_related = ("regulator", "regulation")
    list_filter = ("state", "active", "public_registry_enabled", "signature_required")
    search_fields = ("translations__name", "reference")
    actions = ("publish_procedure", "archive_procedure")
    inlines = [ProcedurePageInline]

    @admin.action(description=_("Publish procedure"), permissions=["change"])
    def publish_procedure(self, request: HttpRequest, queryset: QuerySet[ProcedureTemplate]) -> None:
        with transaction.atomic():
            # Lock the regulator before checking its published versions so concurrent requests cannot publish the same pair.
            regulator_ids = list(queryset.values_list("regulator_id", flat=True).distinct())
            list(Regulator.objects.filter(pk__in=regulator_ids).order_by("pk").select_for_update())
            drafts = list(queryset.filter(state=ProcedureTemplate.State.DRAFT).values_list("pk", "regulator_id", "regulation_id"))
            selected = Counter((regulator_id, regulation_id) for _, regulator_id, regulation_id in drafts)
            published = set(
                ProcedureTemplate.objects.filter(regulator_id__in=regulator_ids, state=ProcedureTemplate.State.PUBLISHED).values_list(
                    "regulator_id", "regulation_id"
                )
            )
            eligible = [pk for pk, reg, rule in drafts if selected[reg, rule] == 1 and (reg, rule) not in published]
            now = timezone.now()
            count = queryset.filter(pk__in=eligible, state=ProcedureTemplate.State.DRAFT).update(
                state=ProcedureTemplate.State.PUBLISHED, published_at=now, last_update=now
            )
        if count:
            self.message_user(request, _("Procedures published: %(count)s") % {"count": count}, messages.SUCCESS)
        if count < len(drafts) or not count:
            self.message_user(
                request,
                _("Select one draft per regulator and regulation and archive any currently published procedure first."),
                messages.WARNING,
            )

    @admin.action(description=_("Archive procedure"), permissions=["change"])
    def archive_procedure(self, request: HttpRequest, queryset: QuerySet[ProcedureTemplate]) -> None:
        count = queryset.filter(state=ProcedureTemplate.State.PUBLISHED).update(
            state=ProcedureTemplate.State.ARCHIVED, last_update=timezone.now()
        )
        if count:
            self.message_user(request, _("Procedures archived: %(count)s") % {"count": count}, messages.SUCCESS)
        else:
            self.message_user(request, _("Select a published procedure to archive."), messages.WARNING)

    def get_readonly_fields(self, request: HttpRequest, obj: ProcedureTemplate | None = None) -> tuple[str, ...]:
        fields = super().get_readonly_fields(request, obj)
        if obj and self.is_editable(obj) and request.user.has_perm("selfregistration.add_proceduretemplateconditionalquestion"):
            return (*fields, "add_conditional_rule")
        return fields

    @admin.display(description=_("Conditional questions"))
    def add_conditional_rule(self, obj: ProcedureTemplate):
        url = reverse(
            f"{self.admin_site.name}:selfregistration_proceduretemplateconditionalquestion_add", query={"template_version": obj.pk}
        )
        return format_html('<a href="{}">{}</a>', url, _("Add a conditional question to this procedure"))

    def is_editable(self, obj: ProcedureTemplate | None) -> bool:
        return obj is None or obj.state == ProcedureTemplate.State.DRAFT

    def save_model(self, request, obj, form, change):
        # A publication may have finished while the draft's form was being validated.
        if change and not self.get_queryset(request).filter(pk=obj.pk, state=ProcedureTemplate.State.DRAFT).select_for_update().exists():
            raise PermissionDenied
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request: HttpRequest, obj: ProcedureTemplate | None = None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None:
            return fieldsets
        title, options = fieldsets[0]
        return [
            (title, {**options, "description": _("Save the procedure and continue editing to start building its questionnaire.")}),
            *fieldsets[1:],
        ]

    def get_inline_instances(self, request: HttpRequest, obj: ProcedureTemplate | None = None) -> list[InlineModelAdmin]:
        if obj is None:
            return []
        # Unfold also builds question formsets for unsaved pages, so scope their choices to the saved version's regulator.
        request._sr_questionnaire_regulator_id = obj.regulator_id  # type: ignore[attr-defined]
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
        return obj is None or not obj.pages.exclude(template_version__state=ProcedureTemplate.State.DRAFT).exists()


@admin.register(ProcedureTemplateQuestionGroup, site=admin_site)
class ProcedureTemplateQuestionGroupAdmin(ProcedureConfigurationAdmin[ProcedureTemplateQuestionGroup], CustomTranslatableAdmin):
    """Configure a repeatable group's bounds and the order of its questions."""

    regulator_field = "owner_id"
    relation_scopes = {"owner": "pk"}
    fixed_fields = ("owner",)
    list_display = ("title", "owner", "min_occurrences", "max_occurrences")
    search_fields = ("translations__title",)
    inlines = [ProcedureQuestionInline]

    def get_inline_instances(self, request: HttpRequest, obj: ProcedureTemplateQuestionGroup | None = None) -> list[InlineModelAdmin]:
        if obj is None:
            return []
        request._sr_questionnaire_regulator_id = obj.owner_id  # type: ignore[attr-defined]
        return super().get_inline_instances(request, obj)

    def is_editable(self, obj: ProcedureTemplateQuestionGroup | None) -> bool:
        return (
            obj is None
            or not ProcedureTemplateQuestionPlacement.objects.filter(
                question_group=obj,
                page__template_version__state__in=(ProcedureTemplate.State.PUBLISHED, ProcedureTemplate.State.ARCHIVED),
            ).exists()
        )


@admin.register(ProcedureTemplateConditionalQuestion, site=admin_site)
class ProcedureTemplateConditionalQuestionAdmin(ProcedureConfigurationAdmin[ProcedureTemplateConditionalQuestion]):
    """Configure the answer that reveals a question or group on the same page."""

    regulator_field = "template_version__regulator_id"
    fields = ("template_version", "target", "trigger_question", "trigger_choice")
    list_display = ("template_version", "trigger_question", "trigger_choice", "target")
    list_display_links = ("trigger_question",)
    list_select_related = ("template_version", "trigger_question__question", "trigger_choice", "target__question", "target__question_group")
    search_fields = (
        "template_version__translations__name",
        "trigger_question__question__translations__label",
        "trigger_choice__translations__label",
        "target__question__translations__label",
        "target__question_group__translations__title",
    )

    class Media:
        js = ["js/selfregistration/conditional_question.js"]

    def is_editable(self, obj: ProcedureTemplateConditionalQuestion | None) -> bool:
        return obj is None or obj.template_version.state == ProcedureTemplate.State.DRAFT

    def has_delete_permission(self, request: HttpRequest, obj: ProcedureTemplateConditionalQuestion | None = None) -> bool:
        return self.is_editable(obj) and super().has_delete_permission(request, obj)

    def get_list_display(self, request: HttpRequest):
        fields = super().get_list_display(request)
        return (*fields, "delete_rule_link") if self.has_delete_permission(request) else fields

    @admin.display(description=_("Actions"))
    def delete_rule_link(self, obj: ProcedureTemplateConditionalQuestion):
        if self.is_editable(obj):
            url = reverse(f"{self.admin_site.name}:selfregistration_proceduretemplateconditionalquestion_delete", args=[obj.pk])
            return format_html(
                '<a class="admin-button admin-button--danger" href="{}">'
                '<span class="material-symbols-outlined" aria-hidden="true">delete</span>{}</a>',
                url,
                _("Delete rule"),
            )
        return None

    @staticmethod
    def placement_label(item: ProcedureTemplateQuestionPlacement) -> str:
        page = item.containing_page
        location = [str(page)] if page else []
        if item.parent_group:
            location.append(str(item.parent_group))
        return " / ".join([*location, str(item)])

    def option_querysets(self, request: HttpRequest, selected: Mapping[str, object]):
        versions = (
            ProcedureTemplate.objects.filter(state=ProcedureTemplate.State.DRAFT, regulator_id__in=administered_regulators(request))
            .filter(Q(pages__placements__is_conditional=True) | Q(pages__placements__question_group__questions__is_conditional=True))
            .select_related("regulator", "regulation")
            .prefetch_related("translations", "regulator__translations", "regulation__translations")
            .distinct()
        )
        ids = {
            field: int(value)
            for field in self.fields[:-1]
            if (value := str(selected.get(field, ""))).isascii() and value.isdecimal() and len(value) <= 19
        }
        selected_version = versions.filter(pk=ids.get("template_version"))
        placements = (
            ProcedureTemplateQuestionPlacement.objects.filter(
                Q(page__template_version__in=selected_version) | Q(parent_group__placement__page__template_version__in=selected_version)
            )
            .select_related(
                "page__category",
                "parent_group__placement__page__category",
                "question",
                "question_group",
            )
            .prefetch_related(
                "page__category__translations",
                "parent_group__translations",
                "parent_group__placement__page__category__translations",
                "question__translations",
                "question_group__translations",
            )
        )
        targets = placements.filter(is_conditional=True)
        target = targets.filter(pk=ids["target"]).first() if "target" in ids else None
        triggers = placements.none()
        if target and (page := target.containing_page):
            triggers = placements.filter(
                Q(page_id=page.pk) | Q(parent_group_id=target.parent_group_id, parent_group__isnull=False),
                is_conditional=False,
                question__question_type__in=ProcedureTemplateQuestion.CHOICE_TYPES,
                question__choices__isnull=False,
            ).distinct()
        selected_trigger = triggers.filter(pk=ids["trigger_question"]) if "trigger_question" in ids else triggers.none()
        choices = ProcedureTemplateChoice.objects.filter(question_id__in=selected_trigger.values("question_id")).prefetch_related(
            "translations"
        )
        return dict(template_version=versions, target=targets, trigger_question=triggers, trigger_choice=choices)

    def get_form(self, request: HttpRequest, obj: ProcedureTemplateConditionalQuestion | None = None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "template_version" not in form.base_fields:
            return form

        selected: Mapping[str, object]
        if request.method == "POST":
            selected = request.POST
        elif obj is not None:
            selected = dict(template_version=obj.template_version_id, target=obj.target_id, trigger_question=obj.trigger_question_id)
        else:
            selected = request.GET
        for name, queryset in self.option_querysets(request, selected).items():
            form.base_fields[name].queryset = queryset
        for name in ("target", "trigger_question"):
            form.base_fields[name].label_from_instance = self.placement_label
        form.base_fields["trigger_question"].error_messages["invalid_choice"] = _(
            "Select an eligible trigger question on the same page as the conditional item."
        )
        form.base_fields["template_version"].widget.attrs.update(
            {
                "data-conditional-options": reverse(f"{self.admin_site.name}:selfregistration_conditional_options"),
                "data-loading-error": _("Could not load the available options. Change the selection to retry."),
                "data-no-options": _("No options are available for this selection."),
            }
        )
        return form

    def get_urls(self):
        return [
            path("options/", self.admin_site.admin_view(self.options_view), name="selfregistration_conditional_options"),
            *super().get_urls(),
        ]

    def options_view(self, request: HttpRequest):
        field = request.GET.get("field")
        if field not in self.fields[1:] or not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise Http404
        queryset = self.option_querysets(request, request.GET)[field]
        label = str if field == "trigger_choice" else self.placement_label
        return JsonResponse({"options": [{"id": item.pk, "label": label(item)} for item in queryset]})


class ProcedureTemplateChoicesFormSet(TranslatableBaseInlineFormSet):
    """Validate choices against the question type submitted in the parent form."""

    def clean(self) -> None:
        super().clean()
        if self.instance.question_type not in ProcedureTemplateQuestion.CHOICE_TYPES and any(
            (form.instance.pk or form.has_changed()) and not form.cleaned_data.get("DELETE") for form in self.forms
        ):
            raise forms.ValidationError(_("Answer choices are only available for single- and multiple-choice questions."))


class ProcedureTemplateChoiceInline(CustomTranslatableTabularInline):
    """Edit translated answer choices with the question that owns them."""

    model = ProcedureTemplateChoice
    formset = ProcedureTemplateChoicesFormSet
    fields = ("position", "label")
    extra = 0


@admin.register(ProcedureTemplateQuestion, site=admin_site)
class ProcedureTemplateQuestionAdmin(ProcedureConfigurationAdmin[ProcedureTemplateQuestion], CustomTranslatableAdmin):
    """Manage reusable questions whose wording may be shared by several questionnaires."""

    regulator_field = "owner_id"
    share_catalogue = True
    relation_scopes = {"owner": "pk"}
    fixed_fields = ("owner",)
    list_display = ("label", "question_type", "owner", "reference")
    list_filter = ("question_type",)
    list_select_related = ("owner",)
    search_fields = ("translations__label", "reference")
    inlines = [ProcedureTemplateChoiceInline]

    def has_change_permission(self, request: HttpRequest, obj: ProcedureTemplateQuestion | None = None) -> bool:
        return super().has_change_permission(request, obj) and (
            obj is None or administered_regulators(request).filter(regulator_id=obj.owner_id).exists()
        )

    def is_editable(self, obj: ProcedureTemplateQuestion | None) -> bool:
        return obj is None or not locked_question_placements().filter(question=obj).exists()

    def get_readonly_fields(self, request: HttpRequest, obj: ProcedureTemplateQuestion | None = None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "save_as_new") if obj is not None and self.has_add_permission(request) else fields

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj is not None and self.has_add_permission(request):
            context["adminform"].form.instance._sr_copy_regulators = (
                Regulator.objects.filter(pk__in=administered_regulators(request)).prefetch_related("translations").order_by("pk")
            )
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    @admin.display(description=_("Copy question"))
    def save_as_new(self, question: ProcedureTemplateQuestion):
        url = reverse(f"{self.admin_site.name}:selfregistration_proceduretemplatequestion_copy", args=[question.pk])
        regulators = getattr(question, "_sr_copy_regulators", ())
        owner_widget = forms.Select(
            attrs={"aria-label": _("Regulator for the new question"), "class": "border rounded px-2 py-2"},
            choices=[(regulator.pk, str(regulator)) for regulator in regulators],
        )
        return format_html(
            '{} <button type="submit" formaction="{}" formnovalidate class="admin-button admin-button--secondary">{}</button>',
            owner_widget.render("copy_owner", question.owner_id),
            url,
            _("Save as new"),
        )

    def get_urls(self):
        return [
            path(
                "<int:object_id>/copy/",
                self.admin_site.admin_view(self.copy_question),
                name="selfregistration_proceduretemplatequestion_copy",
            ),
            *super().get_urls(),
        ]

    def copy_question(self, request: HttpRequest, object_id: int):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self.has_add_permission(request):
            raise PermissionDenied
        source = get_object_or_404(self.get_queryset(request).prefetch_related("translations", "choices__translations"), pk=object_id)
        owner_id = request.POST.get("copy_owner", "")
        if not owner_id.isascii() or not owner_id.isdecimal() or len(owner_id) > 19:
            raise Http404
        owner = get_object_or_404(Regulator, pk=int(owner_id), pk__in=administered_regulators(request))

        with transaction.atomic():
            copied = ProcedureTemplateQuestion.objects.create(owner=owner, question_type=source.question_type)
            for translation in source.translations.all():
                copied.create_translation(translation.language_code, label=translation.label, help_text=translation.help_text)
            for choice in source.choices.all():
                new_choice = copied.choices.create(position=choice.position)
                for translation in choice.translations.all():
                    new_choice.create_translation(translation.language_code, label=translation.label)
            self.log_addition(request, copied, _("Copied question %(source)s.") % {"source": source})
        self.message_user(request, _("Question saved as new."), messages.SUCCESS)
        return redirect(f"{self.admin_site.name}:selfregistration_proceduretemplatequestion_change", copied.pk)
