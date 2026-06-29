import re

from diff_match_patch import diff_match_patch
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ExportActionModelAdmin
from import_export.exceptions import ImportExportError
from import_export.resources import Diff
from import_export_extensions.admin import CeleryImportExportMixin
from import_export_extensions.resources import CeleryModelResource
from markdown import markdown
from parler.forms import TranslatableModelForm

from governanceplatform.admin import CustomTranslatableAdmin, admin_site
from governanceplatform.helpers import (
    generate_display_methods,
    is_user_regulator,
    sanitize_html,
)
from governanceplatform.mixins import (
    FunctionalityMixin,
    PermissionMixin,
    TranslationUpdateMixin,
)
from governanceplatform.models import Regulation, User
from governanceplatform.settings import PARLER_DEFAULT_LANGUAGE_CODE
from governanceplatform.widgets import TranslatedNameWidget
from securityobjectives.models import (
    Domain,
    MaturityLevel,
    SecurityMeasure,
    SecurityObjective,
    SecurityObjectiveEmail,
    SecurityObjectivesInStandard,
    Standard,
)

from .mixins import CreatorMixin


class DomainResource(TranslationUpdateMixin, resources.ModelResource):
    id = fields.Field(column_name="id", attribute="id", readonly=True)
    position = fields.Field(
        column_name="position",
        attribute="position",
    )
    label = fields.Field(
        column_name="label",
        attribute="label",
    )

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        if instance and creator:
            instance.creator = creator
            instance.creator_name = creator.name

    class Meta:
        model = Domain
        fields = ("id", "label", "position")


@admin.register(Domain, site=admin_site)
class DomainAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CreatorMixin,
    CustomTranslatableAdmin,
    ExportActionModelAdmin,
):
    resource_class = DomainResource
    should_escape_html = False
    exclude = ["creator_name"]
    search_fields = [
        "translations__label",
        "creator__translations__name",
        "position",
        "standard__translations__label",
    ]
    list_display = [
        "standard_display",
        "position",
        "label_display",
        "creator",
    ]

    fields = [
        "standard",
        "label",
        "position",
    ]

    list_filter = ["standard", "position", "translations__label", "creator"]
    translated_fields = ["label"]
    related_fields = [("standard", "label")]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("creator",)
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:
            return fields + ["creator"]
        return fields


for name, method in generate_display_methods(["label"], [("standard", "label")]).items():
    setattr(DomainAdmin, name, method)


# class to show the difference when importing a standard to go through the subclass
class StandardDiff(Diff):
    def __init__(self, resource, instance, new):
        super().__init__(resource, instance, new)
        self.resource = resource
        self.left_extra = []
        self.right_extra = []

    def compare_with(self, resource, instance):
        super().compare_with(resource, instance)

    def compare_with_row(self, row):
        """Manualy called by import row to calculate custom diff"""
        resource = self.resource

        # Domain
        existing_domain = Domain.objects.filter(
            standard=resource.standard,
            position=row.get("domain_position"),
        ).first()
        before_domain = ""
        if existing_domain:
            existing_domain.set_current_language(resource.lang)
            before_domain = existing_domain.label or ""
        after_domain = row.get("domain") or ""

        # security objective
        before_so_objective = ""
        before_so_description = ""
        before_so_position = ""
        before_so_priority = ""
        existing_so = SecurityObjective.objects.filter(
            unique_code=row.get("security_objective_unique_code"), creator=resource.regulator
        ).first()
        if existing_so:
            existing_so.set_current_language(resource.lang)
            before_so_objective = existing_so.objective or ""
            before_so_description = existing_so.description or ""
            existing_sois = SecurityObjectivesInStandard.objects.filter(standard=resource.standard, security_objective=existing_so).first()
            if existing_sois:
                before_so_position = existing_sois.position or ""
                before_so_priority = existing_sois.priority or ""
        after_so_obejctive = row.get("security_objective_objective") or ""
        after_so_description = row.get("security_objective_description") or ""
        after_so_position = row.get("security_objective_position") or ""
        after_so_priority = row.get("security_objective_priority") or ""

        # Maturity level
        existing_ml = MaturityLevel.objects.filter(
            standard=resource.standard,
            level=row.get("maturity_level_level"),
        ).first()
        before_ml = ""
        if existing_ml:
            existing_ml.set_current_language(resource.lang)
            before_ml = existing_ml.label or ""
        after_ml = row.get("maturity_level") or ""

        # security measures
        before_sm_evidence = ""
        before_sm_description = ""
        existing_sm = None
        if existing_so and existing_ml:
            existing_sm = SecurityMeasure.objects.filter(
                security_objective=existing_so, maturity_level=existing_ml, position=row.get("security_measure_position")
            ).first()
        if existing_sm:
            existing_sm.set_current_language(resource.lang)
            before_sm_evidence = existing_sm.evidence or ""
            before_sm_description = existing_sm.description or ""
        after_sm_evidence = row.get("security_measure_evidence")
        after_sm_description = row.get("security_measure_description")

        self.left_extra = [
            before_domain,
            before_so_objective,
            before_so_description,
            before_so_position,
            before_so_priority,
            before_ml,
            before_sm_description,
            before_sm_evidence,
        ]
        self.right_extra = [
            after_domain,
            after_so_obejctive,
            after_so_description,
            after_so_position,
            after_so_priority,
            after_ml,
            after_sm_description,
            after_sm_evidence,
        ]

    def as_html(self):
        # Diff standard
        data = super().as_html()

        # Diff custom
        dmp = diff_match_patch()
        for v1, v2 in zip(self.left_extra, self.right_extra):
            original = v1
            if original != v2 and self.new:
                original = ""
            diff = dmp.diff_main(force_str(original), force_str(v2))
            dmp.diff_cleanupSemantic(diff)
            data.append(mark_safe(dmp.diff_prettyHtml(diff)))

        return data


class StandardResource(CeleryModelResource, TranslationUpdateMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = self.resource_init_kwargs.get("user_id")
        self.lang = self.resource_init_kwargs.get("lang")
        self.regulator = self._get_creator(kwargs)

    label = fields.Field(
        column_name="label",
        attribute="label",
    )
    description = fields.Field(
        column_name="description",
        attribute="description",
    )
    regulation = fields.Field(
        column_name="regulation",
        attribute="regulation",
        widget=TranslatedNameWidget(Regulation, field="label"),
    )

    # manage header for export
    EXTRA_EXPORT_COLUMNS = [
        "domain",
        "domain_position",
        "security_objective_unique_code",
        "security_objective_objective",
        "security_objective_description",
        "security_objective_position",
        "security_objective_priority",
        "maturity_level",
        "maturity_level_level",
        "maturity_level_color",
        "security_measure_position",
        "security_measure_description",
        "security_measure_evidence",
    ]

    def get_export_order(self):
        """Inject extra columns."""
        base_order = super().get_export_order()
        return base_order + tuple(self.EXTRA_EXPORT_COLUMNS)

    def get_export_fields(self, selected_fields=None):
        """
        Override to include the extra columns that are not
        in self.fields (no actual fields declared for them)
        """
        from import_export.fields import Field

        base_fields = super().get_export_fields(selected_fields)

        # filter user selection
        for col in self.EXTRA_EXPORT_COLUMNS:
            if selected_fields is None or col in selected_fields:
                f = Field(column_name=col, attribute=col, readonly=True)
                base_fields.append(f)

        return base_fields

    def get_or_init_instance(self, instance_loader, row):
        """
        Use the standard get in before_import function
        """
        return self.standard, False

    def _get_creator(self, kwargs):
        """Resolve creator from kwargs or fall back to user_id (Celery path)."""
        creator = kwargs.get("creator")
        if creator is None and self.user_id:
            try:
                user = User.objects.get(pk=self.user_id)
                creator = user.regulators.first()
            except User.DoesNotExist:
                pass
        return creator

    def get_diff_headers(self):
        headers = super().get_diff_headers()[:3]
        headers += [
            _("domain"),
            _("Security objective objective"),
            _("Security objective description"),
            _("Security objective position"),
            _("Security objective priority"),
            _("maturity_level"),
            _("Security measure description"),
            _("Security measure evidence"),
        ]
        return headers

    def import_row(self, row, instance_loader, **kwargs):
        # Patch : use the class for diff
        original_diff_class = self.get_diff_class()

        class PatchedDiff(original_diff_class):
            def compare_with(self, resource, instance):
                super().compare_with(resource, instance)
                # Inject custom diff
                self.compare_with_row(row)

        self._patched_diff_class = PatchedDiff
        result = super().import_row(row, instance_loader, **kwargs)
        self._patched_diff_class = None
        return result

    def get_diff_class(self):
        if hasattr(self, "_patched_diff_class") and self._patched_diff_class:
            return self._patched_diff_class
        return StandardDiff

    def before_import(self, dataset, **kwargs):
        lang = self.lang
        first_row = dataset[0]
        regulator = self.regulator
        standard_label = first_row[dataset.headers.index("label")]
        regulation = Regulation.objects.filter(
            regulators=regulator,
            translations__label=first_row[dataset.headers.index("regulation")],
            translations__language_code=lang,
        ).first()
        if not regulation:
            raise ImportExportError(
                _("Regulation '%(label)s' does not exist. Check your data.")
                % {
                    "label": first_row[dataset.headers.index("regulation")],
                }
            )

        try:
            standard = Standard.objects.get(
                regulation=regulation,
                translations__label=standard_label,
                translations__language_code=lang,
                regulator=regulator,
            )
        except Standard.DoesNotExist:
            raise ImportExportError(
                _("The standard '%(label)s' is not find for regulation '%(regulation)s' and this regulator.")
                % {
                    "label": standard_label,
                    "regulation": regulation,
                }
            )
        except Standard.MultipleObjectsReturned:
            raise ImportExportError(
                _("Several '%(label)s' have been found. Check your data.")
                % {
                    "label": standard_label,
                }
            )

        self.standard = standard

    def before_import_row(self, row, **kwargs):
        dry_run = kwargs.get("dry_run", False)

        if dry_run:
            return super().before_import_row(row, **kwargs)
        if self.standard and self.regulator and self.lang:
            # Domain
            if row["domain"] and row["domain_position"]:
                domain, _created = Domain.objects.update_or_create(
                    standard=self.standard,
                    position=row["domain_position"],
                    creator=self.regulator,
                )
                domain.set_current_language(self.lang)
                domain.label = row["domain"]
                domain.save()
                row["domain_obj"] = domain
            # security objective
            if (
                row["domain_obj"]
                and row["security_objective_unique_code"]
                and row["security_objective_objective"]
                and row["security_objective_position"]
                and row["security_objective_priority"]
                and row["security_objective_description"]
            ):
                so, _created = SecurityObjective.objects.update_or_create(
                    unique_code=row["security_objective_unique_code"],
                    domain=row["domain_obj"],
                    creator=self.regulator,
                )
                so.set_current_language(self.lang)
                so.description = row["security_objective_description"]
                so.objective = row["security_objective_objective"]
                so.save()
                row["so_obj"] = so
                sois, _created = SecurityObjectivesInStandard.objects.update_or_create(
                    security_objective=so,
                    standard=self.standard,
                    position=row["security_objective_position"],
                    priority=row["security_objective_priority"],
                )
                row["sois_obj"] = sois
            # maturity level
            if row["maturity_level"] and row["maturity_level_level"] is not None:
                ml, _created = MaturityLevel.objects.update_or_create(
                    standard=self.standard,
                    creator=self.regulator,
                    level=row["maturity_level_level"],
                )
                ml.set_current_language(self.lang)
                ml.label = row["maturity_level"]
                if row["maturity_level_color"]:
                    match = re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", row["maturity_level_color"])
                    if match:
                        ml.color = row["maturity_level_color"]
                ml.save()
                row["ml_obj"] = ml
            # security measure
            if (
                row["ml_obj"]
                and row["so_obj"]
                and row["security_measure_description"]
                and row["security_measure_evidence"]
                and row["security_measure_position"]
            ):
                sm, _created = SecurityMeasure.objects.update_or_create(
                    security_objective=row["so_obj"],
                    maturity_level=row["ml_obj"],
                    position=row["security_measure_position"],
                    creator=self.regulator,
                )
                sm.set_current_language(self.lang)
                sm.description = row["security_measure_description"]
                sm.evidence = row["security_measure_evidence"]
                sm.save()
                row["sm_obj"] = sm

        return super().before_import_row(row, **kwargs)

    def after_init_instance(self, instance, new, row, **kwargs):
        regulator = kwargs.get("creator")
        lang = self.lang
        # Derive regulator from user_id when running inside a Celery task
        if regulator is None and self.user_id:
            try:
                user = User.objects.get(pk=self.user_id)
                regulator = user.regulators.first()
            except User.DoesNotExist:
                pass
        if instance and regulator:
            instance.regulator = regulator
            instance.set_current_language(lang)

    def export(self, queryset=None, *args, **kwargs):
        from tablib import Dataset

        lang = self.lang

        # CeleryModelResource inject selected field in kwargs
        user_selected = kwargs.get("export_fields", None)

        if user_selected:
            selected_field_names = list(user_selected)
        else:
            # nothing selected, export all
            selected_field_names = ["label", "description", "regulation"] + self.EXTRA_EXPORT_COLUMNS

        base_headers = [col for col in ["label", "description", "regulation"] if col in selected_field_names]
        selected_extra = [col for col in self.EXTRA_EXPORT_COLUMNS if col in selected_field_names]

        headers = base_headers + selected_extra
        dataset = Dataset(headers=headers)

        if queryset is None:
            queryset = self.get_queryset()

        # progress bar calculation
        measures_qs = SecurityMeasure.objects.filter(security_objective__standard_link__standard__in=queryset)
        self.total_objects_count = measures_qs.count() or queryset.count()
        self.current_object_number = 0

        for standard in queryset:
            measures = (
                SecurityMeasure.objects.filter(security_objective__standard_link__standard=standard)
                .select_related(
                    "security_objective__domain",
                    "security_objective__standard_link",
                    "maturity_level",
                )
                .order_by(
                    "security_objective__domain__position",
                    "security_objective__unique_code",
                    "maturity_level__level",
                    "position",
                )
            )

            if not measures.exists():
                dataset.append(self._build_row(standard, lang, selected_field_names=selected_field_names))
                self.update_task_state(state="EXPORTING")
                continue

            for measure in measures:
                dataset.append(self._build_row(standard, lang, measure, selected_field_names=selected_field_names))
                self.update_task_state(state="EXPORTING")

        return dataset

    def _build_row(self, standard, lang, measure=None, selected_field_names=None):
        standard.set_current_language(lang)

        # All possible values, sorted by column name
        all_values = {
            "label": standard.label or "",
            "description": standard.description or "",
            "regulation": (standard.regulation.safe_translation_getter("label", language_code=lang) or "" if standard.regulation else ""),
        }

        if measure is not None:
            so = measure.security_objective
            so.set_current_language(lang)
            domain = so.domain
            domain.set_current_language(lang)
            ml = measure.maturity_level
            ml.set_current_language(lang)
            sois = SecurityObjectivesInStandard.objects.filter(security_objective=so, standard=standard).first()

            all_values.update(
                {
                    "domain": domain.label or "",
                    "domain_position": domain.position or "",
                    "security_objective_unique_code": so.unique_code or "",
                    "security_objective_objective": so.objective or "",
                    "security_objective_description": so.description or "",
                    "security_objective_position": sois.position if sois else "",
                    "security_objective_priority": sois.priority if sois else "",
                    "maturity_level": ml.label or "",
                    "maturity_level_level": ml.level if ml.level is not None else "",
                    "maturity_level_color": ml.color or "",
                    "security_measure_position": measure.position or "",
                    "security_measure_description": measure.description or "",
                    "security_measure_evidence": measure.evidence or "",
                }
            )
        else:
            # Leave this line blank for extras if no measures are available
            all_values.update({col: "" for col in self.EXTRA_EXPORT_COLUMNS})

        # Returns only the selected columns, in the correct order
        if selected_field_names:
            return [all_values.get(col, "") for col in selected_field_names if col in all_values]
        return list(all_values.values())

    class Meta:
        model = Standard
        fields = ("label", "description", "regulation")
        exclude = ("regulator",)


class SecurityObjectiveInline(admin.TabularInline):
    model = SecurityObjectivesInStandard
    ordering = ["position"]
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if db_field.name == "security_objective" and is_user_regulator(user):
            standard_id = request.resolver_match.kwargs.get("object_id")
            # update we have the standard
            if standard_id:
                linked_to_other_standards = SecurityObjectivesInStandard.objects.exclude(standard_id=standard_id).values(
                    "security_objective_id"
                )

                kwargs["queryset"] = (
                    SecurityObjective.objects.filter(creator__in=user.regulators.all())
                    .exclude(id__in=linked_to_other_standards)
                    .exclude(~Q(domain__standard__id=standard_id))
                    .order_by("unique_code")
                    .distinct()
                )
            # creation we don't have the standard
            else:
                kwargs["queryset"] = (
                    SecurityObjective.objects.filter(creator__in=user.regulators.all())
                    .exclude(id__in=SecurityObjectivesInStandard.objects.values("security_objective_id"))
                    .exclude(~Q(domain__standard__id=standard_id))
                    .order_by("unique_code")
                    .distinct()
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Standard, site=admin_site)
class StandardAdmin(CeleryImportExportMixin, FunctionalityMixin, PermissionMixin, CustomTranslatableAdmin):
    resource_class = StandardResource
    should_escape_html = False
    list_display = ["label_display", "description_display", "regulator"]
    search_fields = [
        "translations__label",
        "translations__description",
        "regulator__translations__name",
    ]
    exclude = ("regulator",)
    inlines = (SecurityObjectiveInline,)
    list_filter = ["translations__label", "regulator"]
    translated_fields = ["description", "label"]
    fieldsets = [
        (
            _("General"),
            {
                "classes": ["wide", "extrapretty"],
                "fields": ["regulation", "label", "description"],
            },
        ),
        (
            _("Notification Email"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "submission_email",
                    "security_objective_status_changed_email",
                    "security_objective_closure_email",
                ],
            },
        ),
    ]

    def has_import_permission(self, request):
        return request.user.has_perm("securityobjectives.add_standard")

    def has_export_permission(self, request):
        return request.user.has_perm("securityobjectives.view_standard")

    def get_import_resource_kwargs(self, request, **kwargs):
        kwargs = super().get_import_resource_kwargs(request, **kwargs)
        kwargs["user_id"] = request.user.pk
        kwargs["lang"] = get_language() or PARLER_DEFAULT_LANGUAGE_CODE
        return kwargs

    def get_export_resource_kwargs(self, request, **kwargs):
        kwargs = super().get_export_resource_kwargs(request, **kwargs)
        kwargs["lang"] = get_language() or PARLER_DEFAULT_LANGUAGE_CODE
        return kwargs

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if obj is None:
            return []
        return inline_instances

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("regulator",)
        return ()

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))

        title, opts = fieldsets[0]
        opts = opts.copy()
        opts["fields"] = list(opts["fields"])

        if obj:
            opts["fields"].append("regulator")

        fieldsets[0] = (title, opts)
        return fieldsets

    # limit regulation to the one authorized by paltformadmin
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "regulation":
            regulator = request.user.regulators.first()
            kwargs["queryset"] = Regulation.objects.filter(regulators=regulator).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # save by default the regulator
    def save_model(self, request, obj, form, change):
        user = request.user
        obj.regulator = user.regulators.first()
        super().save_model(request, obj, form, change)

    # ensure to use the normal delete to go through the function which also delete SO
    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            for standard in queryset:
                standard.delete()  # appelle ton delete() custom


for name, method in generate_display_methods(["label", "description"]).items():
    setattr(StandardAdmin, name, method)


class MaturityLevelResource(TranslationUpdateMixin, resources.ModelResource):
    label = fields.Field(
        column_name="label",
        attribute="label",
    )
    level = fields.Field(
        column_name="level",
        attribute="level",
    )

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        if instance and creator:
            instance.creator = creator
            instance.creator_name = creator.name

    class Meta:
        model = MaturityLevel
        fields = ("level", "label")


@admin.register(MaturityLevel, site=admin_site)
class MaturityLevelAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CreatorMixin,
    CustomTranslatableAdmin,
):
    resource_class = MaturityLevelResource
    should_escape_html = False
    exclude = ["creator_name", "creator"]
    search_fields = [
        "translations__label",
        "creator__translations__name",
        "level",
        "standard__translations__label",
    ]
    list_display = [
        "standard_display",
        "level",
        "color_preview",
        "label_display",
        "creator",
    ]
    list_filter = ["standard", "level", "creator"]
    translated_fields = ["label"]
    related_fields = [("standard", "label")]
    fields = [
        "standard",
        "label",
        "level",
        "color",
    ]

    @admin.display(description=_("Color"))
    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block; width:16px; height:16px; background:{}; border:1px solid #ccc;"></span> {}',
            obj.color,
            obj.color,
        )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "standard",
                "level",
                "creator",
            )
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:
            return fields + ["creator"]
        return fields


for name, method in generate_display_methods(["label"], [("standard", "label")]).items():
    setattr(MaturityLevelAdmin, name, method)


class SecurityObjectiveResource(TranslationUpdateMixin, resources.ModelResource):
    objective = fields.Field(
        column_name="objective",
        attribute="objective",
    )
    description = fields.Field(
        column_name="description",
        attribute="description",
    )
    unique_code = fields.Field(
        column_name="unique_code",
        attribute="unique_code",
    )
    domain = fields.Field(
        column_name="domain",
        attribute="domain",
        widget=TranslatedNameWidget(Domain, field="label"),
    )
    domain_position = fields.Field(column_name="domain_position", attribute="domain__position")

    standard = fields.Field(
        column_name="standard",
        attribute="standard",
    )
    position = fields.Field(
        column_name="position",
        attribute="position",
    )
    priority = fields.Field(column_name="priority", attribute="priority")

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        if instance and creator:
            instance.creator = creator
            instance.creator_name = creator.name

    class Meta:
        model = SecurityObjective
        fields = (
            "objective",
            "description",
            "unique_code",
            "domain",
            "domain_position",
            "standard",
            "position",
            "priority",
        )
        import_id_fields = ("unique_code",)


@admin.register(SecurityObjective, site=admin_site)
class SecurityObjectiveAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CreatorMixin,
    CustomTranslatableAdmin,
):
    resource_class = SecurityObjectiveResource
    should_escape_html = False
    list_display = [
        "standard_display",
        "unique_code",
        "objective_display",
        "description_display",
        "domain",
        "creator",
    ]
    exclude = ["is_archived", "creator_name", "creator"]
    list_filter = [
        "standard",
        "unique_code",
        "translations__objective",
        "domain",
        "creator",
    ]
    translated_fields = ["description", "objective"]
    related_fields = [("domain", "label")]
    search_fields = [
        "unique_code",
        "translations__objective",
        "translations__description",
        "domain__translations__label",
        "creator__translations__name",
    ]

    fields = [
        "domain",
        "unique_code",
        "objective",
        "description",
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("creator",)
        return ()

    @admin.display(description=_("Standard"))
    def standard_display(self, obj):
        return obj.standard_link.standard if obj.standard_link else "-"

    # filter only the standards that belongs to the regulators'user
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "standards":
            kwargs["queryset"] = Standard.objects.filter(regulator=request.user.regulators.first())
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if db_field.name == "domain":
            # Regulator
            if is_user_regulator(user):
                kwargs["queryset"] = Domain.objects.filter(creator__in=user.regulators.all()).distinct()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


for name, method in generate_display_methods(["description", "objective"], [("domain", "label")]).items():
    setattr(SecurityObjectiveAdmin, name, method)


class SecurityMeasureResource(TranslationUpdateMixin, resources.ModelResource):
    standard = fields.Field(
        column_name="standard",
        attribute="standard",
    )
    security_objective = fields.Field(
        column_name="security_objective",
        attribute="security_objective",
    )
    maturity_level = fields.Field(
        column_name="maturity_level",
        attribute="maturity_level",
        widget=TranslatedNameWidget(MaturityLevel, field="label"),
    )
    maturity_level_level = fields.Field(column_name="maturity_level_level", attribute="maturity_level_level")
    maturity_level_color = fields.Field(column_name="maturity_level_color", attribute="maturity_level_color")
    position = fields.Field(
        column_name="position",
        attribute="position",
    )
    description = fields.Field(
        column_name="description",
        attribute="description",
    )
    evidence = fields.Field(
        column_name="evidence",
        attribute="evidence",
    )

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        lang = self.lang
        # Derive creator from user_id when running inside a Celery task
        if creator is None and self.user_id:
            try:
                user = User.objects.get(pk=self.user_id)
                creator = user.regulators.first()
            except User.DoesNotExist:
                pass
        if instance and creator:
            instance.creator = creator
            instance.creator_name = creator.name
            instance.set_current_language(lang)

    class Meta:
        model = SecurityMeasure
        fields = (
            "standard",
            "security_objective",
            "maturity_level",
            "maturity_level_level",
            "maturity_level_color",
            "position",
            "description",
            "evidence",
        )


# add a custom form for SecurityMeasure to ensure that
# all the standard are the same
class SecurityMeasureAdminForm(TranslatableModelForm, PermissionMixin):
    class Meta:
        model = SecurityMeasure
        exclude = ["creator_name", "creator", "is_archived"]

    def clean(self):
        cleaned_data = super().clean()

        so = cleaned_data.get("security_objective")
        ml = cleaned_data.get("maturity_level")
        sois = None
        if so:
            sois = SecurityObjectivesInStandard.objects.get(security_objective=so)

        if sois and ml:
            if sois.standard_id != ml.standard_id:
                raise ValidationError(_("Standard of security objective and maturity level must be the same"))

        return cleaned_data


@admin.register(SecurityMeasure, site=admin_site)
class SecurityMeasureAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CreatorMixin,
    CustomTranslatableAdmin,
):
    form = SecurityMeasureAdminForm
    resource_class = SecurityMeasureResource
    should_escape_html = False
    list_display = [
        "standard_display",
        "security_objective",
        "maturity_level",
        "position",
        "description_display",
        "creator",
    ]
    search_fields = [
        "security_objective__standard_link__standard__translations__label",
        "security_objective__unique_code",
        "security_objective__translations__objective",
        "translations__description",
        "position",
    ]
    ordering = ["security_objective__unique_code", "position"]
    list_filter = [
        "security_objective__standard_link__standard",
        "security_objective",
        "creator",
    ]

    fields = [
        "security_objective",
        "maturity_level",
        "position",
        "description",
        "evidence",
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("creator", "security_objective")
        return ()

    translated_fields = ["description"]

    @admin.display(description=_("Standard"))
    def standard_display(self, obj):
        return obj.security_objective.standard_link.standard if obj.security_objective.standard_link else "-"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        user = request.user
        if db_field.name == "security_objective":
            # Regulator
            if is_user_regulator(user):
                kwargs["queryset"] = (
                    SecurityObjective.objects.filter(creator__in=user.regulators.all(), standard_link__isnull=False)
                    .order_by("unique_code")
                    .distinct()
                )

        if db_field.name == "maturity_level":
            # Regulator filter
            if is_user_regulator(user):
                qs = MaturityLevel.objects.filter(creator__in=user.regulators.all())

                # in edition filter with the standard
                object_id = request.resolver_match.kwargs.get("object_id")
                if object_id:
                    try:
                        security_measure = SecurityMeasure.objects.select_related("security_objective__standard_link__standard").get(
                            pk=object_id
                        )

                        standard = security_measure.security_objective.standard_link.standard

                        qs = qs.filter(standard=standard)

                    except SecurityMeasure.DoesNotExist:
                        pass

                kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


for name, method in generate_display_methods(["description"], []).items():
    setattr(SecurityMeasureAdmin, name, method)


class SOEmailResource(TranslationUpdateMixin, resources.ModelResource):
    subject = fields.Field(
        column_name="subject",
        attribute="subject",
    )

    content = fields.Field(
        column_name="content",
        attribute="content",
    )

    name = fields.Field(
        column_name="name",
        attribute="name",
    )

    class Meta:
        model = SecurityObjectiveEmail
        fields = ("id", "name", "subject", "content")
        export_order = fields


@admin.register(SecurityObjectiveEmail, site=admin_site)
class SOEmailAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CreatorMixin,
    CustomTranslatableAdmin,
    ExportActionModelAdmin,
):
    list_display = [
        "name",
        "subject_display",
        "content_display",
        "creator",
    ]
    search_fields = [
        "translations__subject",
        "translations__content",
        "creator__translations__name",
    ]
    translated_fields = ["subject", "content"]
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
    resource_class = SOEmailResource
    should_escape_html = False
    list_filter = ["name", "translations__subject", "creator"]

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


for name, method in generate_display_methods(["subject", "content"]).items():
    setattr(SOEmailAdmin, name, method)
