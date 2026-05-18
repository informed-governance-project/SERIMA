import logging
import math

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from markdown import markdown
from parler.models import TranslatableModel

from governanceplatform.admin import (
    CustomTranslatableAdmin,
    CustomTranslatableTabularInline,
    admin_site,
)
from governanceplatform.globals import ACTION_FLAG_CHOICES
from governanceplatform.helpers import (
    can_change_or_delete_obj,
    generate_display_methods,
    sanitize_html,
    set_creator,
    translated_queryset,
    user_in_group,
)
from governanceplatform.mixins import PermissionMixin
from governanceplatform.models import Regulation, Regulator, Sector, User
from governanceplatform.settings import (
    LOG_RETENTION_TIME_IN_DAY,
    PARLER_DEFAULT_LANGUAGE_CODE,
)
from incidents.forms import QuestionOptionsInlineForm
from incidents.models import (
    Answer,
    Email,
    Impact,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulation,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
    Workflow,
)

from .globals import QUESTION_TYPES

logger = logging.getLogger(__name__)


# get the id of a group by name
def get_group_id(name=""):
    try:
        group_id = Group.objects.get(name=name).id
    except ObjectDoesNotExist:
        group_id = None

    return group_id


# filter by user
class LogUserFilter(SimpleListFilter):
    title = _("Users")
    parameter_name = "user"

    def lookups(self, request, model_admin):
        user = request.user
        user_ids = LogEntry.objects.values_list("user", flat=True).distinct()
        users = User.objects.filter(id__in=user_ids)
        PlatformAdminGroupId = get_group_id(name="PlatformAdmin")

        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            users = users.filter(groups__in=[PlatformAdminGroupId])

        # Regulator Admin
        if user_in_group(user, "RegulatorAdmin"):
            users = users.exclude(
                groups__in=[
                    PlatformAdminGroupId,
                ]
            )

        users = users.distinct()

        return [(user.id, user.email) for user in users]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(user=value)
        return queryset


# filter by action
class ActionFlagFilter(SimpleListFilter):
    title = _("Activity")
    parameter_name = "action_flag"

    def lookups(self, request, model_admin):
        return [(af, ACTION_FLAG_CHOICES[af]) for af in ACTION_FLAG_CHOICES]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(action_flag=value)
        return queryset


# add a view to see the logs
@admin.register(LogEntry, site=admin_site)
class LogEntryAdmin(admin.ModelAdmin):
    # to have a date-based drilldown navigation in the admin page
    date_hierarchy = "action_time"

    # to filter the resultes by users, content types and action flags
    list_filter = [LogUserFilter, ActionFlagFilter]

    # when searching the user will be able to search in both object_repr and change_message
    search_fields = ["object_repr", "change_message"]

    list_display = [
        "action_time",
        "user",
        "content_type",
        "_action_flag",
    ]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "user",
                    "action_time",
                    "content_type",
                    "object_id",
                    "object_repr",
                    "_action_flag",
                    "change_message",
                ],
            },
        ),
    ]

    def has_delete_permission(self, request, obj=None):
        module_permission = super().has_module_permission(request)
        if module_permission and obj is not None and obj.action_time:
            actual_time = timezone.now()
            dt = actual_time - obj.action_time
            if math.floor(dt.total_seconds() / 60 / 60 / 24) >= LOG_RETENTION_TIME_IN_DAY:
                return True
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        user = request.user
        return user_in_group(user, "PlatformAdmin") or user_in_group(user, "RegulatorAdmin")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user

        PlatformAdminGroupId = get_group_id(name="PlatformAdmin")

        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            return queryset.filter(Q(action_flag=7) | Q(user__groups__in=[PlatformAdminGroupId])).distinct()

        # Regulator Admin
        if user_in_group(user, "RegulatorAdmin"):
            return queryset.exclude(
                user__groups__in=[
                    PlatformAdminGroupId,
                ]
            )

        return queryset

    @admin.display(description=_("Activity"))
    def _action_flag(self, obj):
        return ACTION_FLAG_CHOICES[obj.action_flag]


@admin.register(PredefinedAnswer, site=admin_site)
class PredefinedAnswerAdmin(PermissionMixin, CustomTranslatableAdmin):
    list_display = ["predefined_answer", "creator"]
    search_fields = ["translations__predefined_answer"]
    exclude = ["creator_name", "creator"]

    # Hidden from register models list
    def has_module_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


@admin.register(QuestionCategory, site=admin_site)
class QuestionCategoryAdmin(PermissionMixin, CustomTranslatableAdmin):
    list_display = ["label", "creator"]
    search_fields = ["translations__label"]
    exclude = ["creator_name", "creator"]

    # Hidden from register models list
    def has_module_permission(self, request):
        return False


class QuestionOptionsInline(PermissionMixin, admin.TabularInline):
    model = QuestionOptions
    form = QuestionOptionsInlineForm
    verbose_name = _("Question")
    verbose_name_plural = _("Questionnaire")
    ordering = ["category_option__position", "position"]
    exclude = ["updated_at", "deleted_date", "historic"]
    extra = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(deleted_date=None)

    def get_max_num(self, request, obj=None, **kwargs):
        max_num = super().get_max_num(request, obj, **kwargs)
        if obj and not can_change_or_delete_obj(request, obj):
            max_num = 0
        return max_num

    # filter the question category option on the report_id to avoid mixing report categories
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category_option" and not request.POST:
            kwargs["queryset"] = (
                QuestionCategoryOptions.objects.filter(questionoptions__report=self.parent_obj)
                .exclude(questionoptions__report=None)
                .distinct()
            )

        if db_field.name == "question" and not request.POST:
            lang = getattr(request, "LANGUAGE_CODE", "en")
            queryset = Question.objects.all()
            qs = translated_queryset(queryset, lang, PARLER_DEFAULT_LANGUAGE_CODE, ["label", "tooltip"], True)
            kwargs["queryset"] = qs.order_by("_label_sort")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PredefinedAnswerInline(CustomTranslatableTabularInline):
    model = PredefinedAnswer
    fields = ["predefined_answer", "position"]
    verbose_name = _("Predefined answer")
    verbose_name_plural = _("Predefined answers")
    ordering = ["position"]
    extra = 0


@admin.action(description=_("Duplicate selected items"))
def duplicate_objects(modeladmin, request, queryset):
    config_by_model = {
        "Question": {
            "related_objects": ["predefinedanswer_set"],
            "label_field": "label",
            "unique_fields": ["reference"],
        },
    }

    for obj in queryset:
        many_to_many_data = {}
        reverse_fk_data = {}
        model_name = obj.__class__.__name__

        if model_name not in config_by_model:
            messages.error(request, f"Duplication not supported for {model_name} model")
            continue

        config = config_by_model[model_name]
        related_objects_to_copy = config.get("related_objects", [])
        unique_fields_to_copy = config.get("unique_fields", [])
        label_field = config.get("label_field")

        try:
            with transaction.atomic():
                for field_name in unique_fields_to_copy:
                    try:
                        value = getattr(obj, field_name, None)
                        if isinstance(value, str) and value:
                            setattr(obj, field_name, f"{value} (copy)")
                        else:
                            setattr(obj, field_name, None)
                    except FieldDoesNotExist:
                        continue

                if isinstance(obj, TranslatableModel):
                    obj_translations = list(obj.translations.all())

                for field in obj._meta.many_to_many:
                    many_to_many_data[field.name] = list(getattr(obj, field.name).all())

                for related_object in obj._meta.related_objects:
                    accessor_name = related_object.get_accessor_name()

                    if accessor_name in related_objects_to_copy and related_object.one_to_many and related_object.auto_created:
                        reverse_fk_data[accessor_name] = list(getattr(obj, accessor_name).all())
                original_label = getattr(obj, label_field)
                obj.pk = None

                if hasattr(obj, "creator"):
                    set_creator(request, obj, False)

                obj.save()

                if obj_translations:
                    for t in obj_translations:
                        t.pk = None
                        if hasattr(t, label_field):
                            original_label = getattr(t, label_field)
                            setattr(t, label_field, f"{original_label} (copy)")
                        t.master = obj
                        t.save()

                for field_name, items in many_to_many_data.items():
                    getattr(obj, field_name).set(items)

                for related_objs in reverse_fk_data.values():
                    for related_obj in related_objs:
                        if isinstance(related_obj, TranslatableModel):
                            related_translations = list(related_obj.translations.all())

                        related_obj.pk = None
                        field_name = related_obj._meta.get_field(related_object.field.name).name
                        setattr(related_obj, field_name, obj)
                        related_obj.save()

                        if related_translations:
                            for t in related_translations:
                                t.pk = None
                                t.master = related_obj
                                t.save()

                messages.success(request, f"Successfully duplicated {original_label} {model_name}")
        except Exception as e:
            logger.exception("Error duplicating object %s: %s", obj.pk, e)
            messages.error(request, f"Error duplicating '{obj}': {str(e)}")


class QuestionTypeListFilter(SimpleListFilter):
    title = _("Question Type")
    parameter_name = "question_type"

    def lookups(self, request, model_admin):
        return QUESTION_TYPES

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(question_type=self.value())
        return queryset


@admin.register(Question, site=admin_site)
class QuestionAdmin(
    PermissionMixin,
    CustomTranslatableAdmin,
):
    actions = [duplicate_objects]
    list_display = [
        "reference",
        "label_display",
        "question_type",
        "get_predefined_answers",
        "creator",
    ]
    translated_fields = ["label"]
    list_display_links = ["reference", "label_display"]
    search_fields = [
        "translations__label",
        "translations__tooltip",
        "reference",
        "creator__translations__name",
        "predefinedanswer__translations__predefined_answer",
    ]
    fields = [
        "question_type",
        "reference",
        "label",
        "tooltip",
    ]
    inlines = [PredefinedAnswerInline]
    list_filter = [QuestionTypeListFilter]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and "creator" not in readonly_fields:
            readonly_fields.append("creator")
        return readonly_fields

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj and "creator" not in fields:
            fields.append("creator")
        return fields

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(
    [
        "label",
    ]
).items():
    setattr(QuestionAdmin, name, method)


@admin.register(QuestionOptions, site=admin_site)
class QuestionOptionsAdmin(admin.ModelAdmin):
    list_display = ["position", "question", "is_mandatory", "category_option"]
    list_display_links = ["position", "question"]
    ordering = ["position"]
    fields = [
        ("position", "is_mandatory"),
        "question",
        "category_option",
    ]
    exclude = ["updated_at", "deleted_date", "historic"]

    # Hidden from register models list
    def has_module_permission(self, request):
        return False


@admin.register(QuestionCategoryOptions, site=admin_site)
class QuestionCategoryOptionsAdmin(PermissionMixin, admin.ModelAdmin):
    list_display = ["question_category", "position"]
    list_display_links = ["position", "question_category"]
    fields = ["question_category", "position"]

    # Hidden from register models list
    def has_module_permission(self, request):
        return False


class ImpactSectorListFilter(SimpleListFilter):
    title = _("Sectors")
    parameter_name = "sectors"

    def lookups(self, request, model_admin):
        sectors = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)
        sectors_list = []

        for sector in sectors:
            sectors_list.append((sector.id, sector))
        return sorted(sectors_list, key=lambda item: str(item[1]))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(Q(sectors=self.value()) | Q(sectors__parent=self.value())).distinct()
        return queryset


class ImpactRegulationListFilter(SimpleListFilter):
    title = _("Legal basis")
    parameter_name = "regulation"

    def lookups(self, request, model_admin):
        return [
            (regulation.id, regulation.label)
            for regulation in Regulation.objects.translated(get_language()).order_by("translations__label")
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(Q(regulations=self.value()))
        return queryset


@admin.register(Impact, site=admin_site)
class ImpactAdmin(CustomTranslatableAdmin):
    list_display = [
        "get_regulations",
        "get_sector_name",
        "get_subsector_name",
        "headline_display",
    ]
    translated_fields = ["headline"]
    search_fields = [
        "translations__label",
        "regulations__translations__label",
        "sectors__translations__name",
    ]
    list_filter = [ImpactSectorListFilter, ImpactRegulationListFilter]
    exclude = ["creator_name", "creator"]
    filter_horizontal = ("sectors", "regulations")
    fieldsets = [
        (
            _("General"),
            {
                "classes": ["wide", "extrapretty"],
                "fields": ["label", "headline"],
            },
        ),
        (
            _("Supervision"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "regulations",
                ],
            },
        ),
        (
            _("Sectors"),
            {
                "fields": ["sectors"],
            },
        ),
    ]

    def get_queryset(self, request):
        lang = get_language()
        sector_subquery = (
            Sector.objects.filter(
                impact=OuterRef("pk"),
            )
            .values("parent__translations__name")
            .filter(parent__translations__language_code=lang)
            .distinct()[:1]
        )
        subsector_subquery = (
            Sector.objects.filter(
                impact=OuterRef("pk"),
            )
            .values("translations__name")
            .filter(translations__language_code=lang)
            .distinct()[:1]
        )
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                "regulations",
            )
            .annotate(sector_sort=Subquery(sector_subquery))
            .annotate(subsector_sort=Subquery(subsector_subquery))
            .distinct()
        )

    @admin.display(description=_("Regulations"), ordering="regulations__translations__label")
    def get_regulations(self, obj):
        return ", ".join([c.label for c in obj.regulations.all()])

    @admin.display(description=_("Sector"), ordering="sector_sort")
    def get_sector_name(self, obj):
        sectors = []
        for sector in obj.sectors.all():
            sector_name = sector.parent.get_safe_translation() if sector.parent else sector.get_safe_translation()
            sectors.append(sector_name)

        return sectors

    @admin.display(description=_("Sub-sector"), ordering="subsector_sort")
    def get_subsector_name(self, obj):
        sectors = []
        for sector in obj.sectors.all():
            sector_name = sector.get_safe_translation() if sector.parent else ""
            sectors.append(sector_name)
        return sectors

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(
    [
        "headline",
    ]
).items():
    setattr(ImpactAdmin, name, method)


class EmailRegulatorListFilter(SimpleListFilter):
    title = _("Regulator")
    parameter_name = "creator_id"

    def lookups(self, request, model_admin):
        return [(regulator.id, regulator.name) for regulator in Regulator.objects.translated(get_language()).order_by("translations__name")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(Q(creator_id=self.value()))
        return queryset


class EmailTypeListFilter(SimpleListFilter):
    title = _("Email type")
    parameter_name = ""

    def lookups(self, request, model_admin):
        return [
            ("REMINDER", "Reminder"),
            ("OPEN", "Opening Email"),
            ("CLOSE", "Closing Email"),
            ("STATUS", "Status changed"),
        ]

    def queryset(self, request, queryset):
        emails_ids = None
        if self.value() == "REMINDER":
            emails_ids = SectorRegulationWorkflowEmail.objects.values_list("email__id", flat=True)
        elif self.value() == "OPEN":
            emails_ids = SectorRegulation.objects.values_list("opening_email__id", flat=True)
        elif self.value() == "CLOSE":
            emails_ids = SectorRegulation.objects.values_list("closing_email__id", flat=True)
        elif self.value() == "STATUS":
            emails_ids = SectorRegulation.objects.values_list("report_status_changed_email__id", flat=True)
        if emails_ids is None:
            return queryset
        return queryset.filter(pk__in=emails_ids)


@admin.register(Email, site=admin_site)
class EmailAdmin(CustomTranslatableAdmin):
    list_display = [
        "name",
        "subject_display",
        "content_display",
    ]
    translated_fields = ["subject", "content"]

    search_fields = ["translations__subject", "translations__content", "name"]
    list_filter = [EmailRegulatorListFilter, EmailTypeListFilter]
    readonly_fields = ("html_preview",)

    fieldsets = (
        (
            None,
            {
                "fields": ("name", "subject"),
            },
        ),
        (
            _("Content"),
            {
                "fields": ("content", "html_preview"),
            },
        ),
    )

    @admin.display(description=_("HTML preview"))
    def html_preview(self, obj):
        if not obj or not obj.content:
            return _("No preview yet")
        html_content = markdown(
            text=obj.content,
            extensions=["extra", "sane_lists", "legacy_attrs", "nl2br"],
            output_format="html",
        )
        html_content = sanitize_html(html_content)
        return mark_safe(
            f"""
            <div class="markdown-html-preview">
                {html_content}
            </div>
            """
        )

    class Media:
        css = {"all": ("admin/css/markdown_preview.css",)}

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(["subject", "content"]).items():
    setattr(EmailAdmin, name, method)


@admin.register(Workflow, site=admin_site)
class WorkflowAdmin(PermissionMixin, CustomTranslatableAdmin):
    list_display = [
        "name",
        "label_display",
        "description_display",
        "is_impact_needed",
        "submission_email",
        "creator",
    ]
    translated_fields = ["label", "description"]
    search_fields = [
        "translations__label",
        "name",
        "translations__description",
        "creator__translations__name",
    ]
    inlines = (QuestionOptionsInline,)
    save_as = True
    exclude = ["creator_name"]
    fieldsets = [
        (
            _("General"),
            {
                "classes": ["wide", "extrapretty"],
                "fields": ["name", "label", "description", "is_impact_needed"],
            },
        ),
        (
            _("Notification Email"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "submission_email",
                ],
            },
        ),
    ]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and "creator" not in readonly_fields:
            readonly_fields.append("creator")
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))

        title, opts = fieldsets[0]
        opts = opts.copy()
        opts["fields"] = list(opts["fields"])

        if obj:
            opts["fields"].append("creator")

        fieldsets[0] = (title, opts)
        return fieldsets

    # give the parent object to the inlines
    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        for inline_instance in inline_instances:
            inline_instance.parent_obj = obj
        return inline_instances

    def get_form(self, request, obj=None, **kwargs):
        if obj and not self.has_change_permission(request, obj):
            self.save_as = False
        return super().get_form(request, obj, **kwargs)

    def has_delete_permission(self, request, obj=None):
        permission = super().has_delete_permission(request, obj)
        if obj and permission:
            permission = bool(
                can_change_or_delete_obj(request, obj) and not Answer.objects.filter(incident_workflow__workflow=obj).exists()
            )
            if not permission and request._can_change_or_delete_obj:
                message = _("<strong>Deletion forbidden</strong><br>- This {object_name} is either in use.<br>")
                object_name = obj._meta.verbose_name.lower()

                messages.warning(request, format_html(message, object_name=object_name))
        return permission

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(["label", "description"]).items():
    setattr(WorkflowAdmin, name, method)


class SectorRegulationInline(admin.TabularInline):
    model = SectorRegulation.workflows.through
    verbose_name = _("Incident report")
    verbose_name_plural = _("Incident reports")
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "workflow":
            kwargs["queryset"] = Workflow.objects.order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.action(description=_("Toggle active status of selected items"))
def toggle_active_status(modeladmin, request, queryset):
    for obj in queryset:
        user = request.user
        if user.regulators.exists() and obj.regulator not in user.regulators.all():
            messages.warning(
                request,
                _("You don't have permission to change the status of %s.") % obj,
            )
            continue
        obj.active = not obj.active
        obj.save()


@admin.register(SectorRegulation, site=admin_site)
class SectorRegulationAdmin(PermissionMixin, CustomTranslatableAdmin):
    list_display = ["active", "name", "regulation", "regulator", "is_detection_date_needed"]
    list_display_links = ["name"]
    search_fields = [
        "translations__name",
        "regulator__translations__name",
        "regulation__translations__label",
    ]
    actions = [toggle_active_status]
    inlines = (SectorRegulationInline,)
    save_as = True
    filter_horizontal = ("sectors",)
    fieldsets = [
        (
            _("General"),
            {
                "classes": ["wide", "extrapretty"],
                "fields": [
                    "active",
                    "name",
                    "is_detection_date_needed",
                ],
            },
        ),
        (
            _("Supervision"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "regulation",
                    "regulator",
                ],
            },
        ),
        (
            _("Sectors"),
            {
                "fields": ["sectors"],
            },
        ),
        (
            _("Notification Email"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "opening_email",
                    "closing_email",
                    "report_status_changed_email",
                ],
            },
        ),
    ]

    # prevent other regulator to save the current workflow but they can duplicate
    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = SectorRegulation.objects.get(pk=object_id)
            if obj.regulator != request.user.regulators.all().first():
                extra_context["show_save"] = False
                extra_context["show_save_and_continue"] = False
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if db_field.name == "regulation":
            # Regulator Admin
            if user_in_group(user, "RegulatorAdmin"):
                kwargs["queryset"] = Regulation.objects.filter(regulators__in=user.regulators.all())

        if db_field.name == "regulator":
            # Regulator Admin
            if user_in_group(user, "RegulatorAdmin"):
                kwargs["queryset"] = user.regulators.all()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        permission = super().has_delete_permission(request, obj)
        header_message = _(
            "<strong>Deletion is not allowed.</strong><br>"
            "- This {object_name} is either in use.<br>"
            "- You are not its creator ({creator_name})"
        )
        if obj and permission:
            permission = can_change_or_delete_obj(request, obj, header_message)

            if not permission and request._can_change_or_delete_obj:
                message = _("<strong>Deletion forbidden</strong><br>- This {object_name} is either in use.<br>")
                object_name = obj._meta.verbose_name.lower()

                messages.warning(request, format_html(message, object_name=object_name))
        return permission


@admin.register(SectorRegulationWorkflowEmail, site=admin_site)
class SectorRegulationWorkflowEmailAdmin(CustomTranslatableAdmin):
    list_display = [
        "regulation",
        "sector_regulation_workflow",
        "headline_display",
        "trigger_event",
        "delay_in_hours",
    ]
    translated_fields = ["headline"]
    search_fields = [
        "sector_regulation_workflow__sector_regulation__regulation__translations__label",
        "translations__headline",
        "sector_regulation_workflow__workflow__name",
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sector_regulation_workflow":
            # Regulator Admin
            kwargs["queryset"] = (
                SectorRegulationWorkflow.objects.all().order_by("sector_regulation__translations__name", "workflow__name").distinct()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


for name, method in generate_display_methods(
    [
        "headline",
    ]
).items():
    setattr(SectorRegulationWorkflowEmailAdmin, name, method)
