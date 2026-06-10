import re

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ExportActionModelAdmin, ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from import_export_extensions.admin import CeleryImportExportMixin
from import_export_extensions.resources import CeleryModelResource
from markdown import markdown
from parler.forms import TranslatableModelForm

from governanceplatform.admin import CustomTranslatableAdmin, admin_site
from governanceplatform.helpers import (
    can_change_or_delete_obj,
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

from .mixins import ImportMixin


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

    # save by default the regulator
    def save_model(self, request, obj, form, change):
        user = request.user
        obj.creator = user.regulators.first()
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(["label"], [("standard", "label")]).items():
    setattr(DomainAdmin, name, method)


class StandardResource(TranslationUpdateMixin, resources.ModelResource):
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

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        if instance and creator:
            instance.regulator = creator

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
class StandardAdmin(
    FunctionalityMixin,
    PermissionMixin,
    CustomTranslatableAdmin,
):
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

    # save by default the regulator
    def save_model(self, request, obj, form, change):
        user = request.user
        obj.creator = user.regulators.first()
        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(["label"], [("standard", "label")]).items():
    setattr(MaturityLevelAdmin, name, method)


class SecurityObjectiveResource(TranslationUpdateMixin, resources.ModelResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = kwargs.pop("request", None)
        self._row_cache = {}
        self._importing = False

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

    def get_instance(self, instance_loader, row):
        """
        Allows to define uniqueness: (unique_code, creator)
        without needing ‘creator’ in the file.
        """
        if not self.request:
            return None
        user = self.request.user
        cr = None
        if user:
            cr = user.regulators.first()
        if cr is None:
            return None
        return self._meta.model.objects.filter(
            unique_code=row.get("unique_code"),
            creator=cr,
        ).first()

    def dehydrate_standard(self, obj):
        standard = None
        if self._importing:
            cached = self._row_cache.get(id(self._current_import_row), {})
            standard = cached.get("standard")
        elif obj and obj.pk and not self._importing:
            sois = SecurityObjectivesInStandard.objects.filter(security_objective=obj).first()
            if sois:
                standard = sois.standard

        if standard:
            standard.set_current_language(get_language())
            return standard.label
        current_row = getattr(self, "_current_import_row", None)

        if current_row:
            return current_row.get("standard", "")

        return ""

    def dehydrate_position(self, obj):
        if obj and obj.pk and not self._importing:
            sois = SecurityObjectivesInStandard.objects.filter(
                security_objective=obj,
            ).first()
            if sois:
                return sois.position
            return None
        return self._current_import_row["position"]

    def dehydrate_priority(self, obj):
        if obj and obj.pk and not self._importing:
            sois = SecurityObjectivesInStandard.objects.filter(
                security_objective=obj,
            ).first()
            if sois:
                return sois.priority
            return None
        return self._current_import_row["priority"]

    def dehydrate_domain_position(self, obj):
        if obj.domain and obj.domain.pk:
            return obj.domain.position

        current_row = getattr(self, "_current_import_row", None)

        if current_row:
            return current_row.get("domain_position", "")

        return ""

    def before_import(self, dataset, **kwargs):
        self._importing = True

    def after_import(self, dataset, result, **kwargs):
        self._importing = False

    def skip_row(self, instance, original, row, import_validation_errors=None):
        # Object already in used we don't change
        if instance and instance.pk and self.request:
            return not can_change_or_delete_obj(self.request, instance)

        return super().skip_row(
            instance,
            original,
            row,
            import_validation_errors=import_validation_errors,
        )

    def after_init_instance(self, instance, new, row, **kwargs):
        creator = kwargs.get("creator")
        if instance and creator:
            instance.creator = creator
            instance.creator_name = creator.name

    # link the correct object to the row
    def before_import_row(self, row, **kwargs):
        self._current_import_row = row
        creator = kwargs.get("creator")
        lang = get_language() or "en"
        row["creator"] = creator
        if row["standard"]:
            standard = (
                Standard.objects.filter(
                    regulator=creator,
                )
                .translated(lang, label=row["standard"])
                .first()
            )
            if standard:
                self._row_cache[id(row)] = {
                    "standard": standard,
                }
            if standard:
                if row["domain"] and row["domain_position"]:
                    domain = Domain.objects.filter(standard=standard, position=row["domain_position"]).first()
                    if not domain:
                        domain = Domain.objects.create(
                            standard=standard,
                            position=row["domain_position"],
                            creator=creator,
                        )
                    domain.set_current_language(lang)
                    domain.label = row["domain"]
                    domain.save()
                    row["domain_object"] = domain

        return super().before_import_row(row, **kwargs)

    # if there is a standard get it and save the SO
    def after_import_row(self, row, row_result, **kwargs):
        if hasattr(self, "_current_import_row"):
            del self._current_import_row
        so = SecurityObjective.objects.get(pk=row_result.object_id)
        cached = self._row_cache.pop(id(row), {})
        standard = cached.get("standard")
        if standard and so:
            # force to link to the correct domain
            if row["domain_object"]:
                domain = row["domain_object"]
                so.domain = domain
                so.save()
                domain.standard = standard
                domain.save()
            sois = SecurityObjectivesInStandard.objects.filter(
                security_objective=so,
                standard=standard,
            ).first()
            if not sois:
                sois = SecurityObjectivesInStandard.objects.create(
                    security_objective=so,
                    standard=standard,
                )
            if row["priority"] and row["priority"] is not None:
                sois.priority = row["priority"]
            if row["position"] and row["position"] is not None:
                sois.position = row["position"]
            sois.save()

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
    CustomTranslatableAdmin,
    ImportMixin,
    ImportExportModelAdmin,
    ExportActionModelAdmin,
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

    def has_import_permission(self, request):
        return request.user.has_perm("securityobjectives.add_securityobjective")

    def has_export_permission(self, request):
        return request.user.has_perm("securityobjectives.view_securityobjective")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("creator",)
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:
            return fields + ["creator"]
        return fields

    def get_resource_kwargs(self, request, *args, **kwargs):
        # This passes the current request object to the Resource's __init__
        return {"request": request}

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


class SecurityObjectiveWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        # Already resolved to an instance in before_import_row — pass through
        if isinstance(value, SecurityObjective):
            return value

        if not value:
            return None

        resource = kwargs.get("resource")
        creator_id = getattr(resource, "user_id", None)
        if not creator_id:
            return None

        try:
            user = User.objects.get(pk=creator_id)
        except User.DoesNotExist:
            return None

        creator = user.regulators.first()
        if not creator:
            return None

        return SecurityObjective.objects.filter(
            unique_code=value,
            creator=creator,
        ).first()


class SecurityMeasureResource(CeleryModelResource, TranslationUpdateMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = self.resource_init_kwargs.get("user_id")
        self.lang = self.resource_init_kwargs.get("lang")

    standard = fields.Field(
        column_name="standard",
        attribute="standard",
    )
    security_objective = fields.Field(
        column_name="security_objective",
        attribute="security_objective",
        widget=SecurityObjectiveWidget(
            SecurityObjective,
            field="unique_code",
        ),
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

    def get_or_init_instance(self, instance_loader, row):
        """
        Use the already-resolved SO and ML instances from before_import_row
        to find or create a SecurityMeasure instance directly.
        """
        so = row.get("security_objective")
        ml = row.get("maturity_level_obj")

        position = row.get("position")

        if so and ml and position is not None:
            try:
                instance = SecurityMeasure.objects.get(
                    security_objective=so,
                    maturity_level=ml,
                    position=position,
                )
                return instance, False  # False = not new
            except SecurityMeasure.DoesNotExist:
                pass

        instance = SecurityMeasure()
        return instance, True

    def import_obj(self, row, instance_loader, **kwargs):
        kwargs["resource"] = self
        return super().import_obj(row, instance_loader, **kwargs)

    def dehydrate_maturity_level_color(self, obj):
        if hasattr(self, "_current_import_row") and self._current_import_row["maturity_level_color"] is not None:
            return self._current_import_row["maturity_level_color"]
        if hasattr(self, "_current_import_row") and self._current_import_row["maturity_level_color"] is None:
            return ""
        if obj.maturity_level and obj.maturity_level.pk:
            return obj.maturity_level.color
        return self._current_import_row["maturity_level_color"]

    def dehydrate_maturity_level_level(self, obj):
        if hasattr(self, "_current_import_row"):
            return self._current_import_row["maturity_level_level"]
        if obj.maturity_level and obj.maturity_level.pk:
            return obj.maturity_level.level
        return self._current_import_row["maturity_level_level"]

    def dehydrate_standard(self, obj):
        if hasattr(self, "_current_import_row"):
            return self._current_import_row["standard"]
        return SecurityObjectivesInStandard.objects.filter(security_objective=obj.security_objective).first().standard

    # def skip_row(self, instance, original, row, import_validation_errors=None):
    #     # Object already in used we don't change
    #     if instance and instance.pk and self.request:
    #         return not can_change_or_delete_obj(self.request, instance)

    #     return super().skip_row(
    #         instance,
    #         original,
    #         row,
    #         import_validation_errors=import_validation_errors,
    #     )

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

    def before_import_row(self, row, **kwargs):
        self._current_import_row = row
        creator = self._get_creator(kwargs)
        lang = self.lang

        standard = None
        if row["standard"] and creator:
            standard = Standard.objects.filter(
                translations__label=row["standard"],
                regulator=creator,
            ).first()
        if standard:
            if row["security_objective"] and creator:
                so = SecurityObjective.objects.filter(
                    unique_code=row["security_objective"],
                    standard=standard,
                    creator=creator,
                ).first()
                row["security_objective"] = so
            if row["maturity_level"] and row["maturity_level_level"] is not None and creator:
                ml = MaturityLevel.objects.filter(
                    standard=standard,
                    level=row["maturity_level_level"],
                ).first()
                if not ml:
                    ml = MaturityLevel.objects.create(
                        standard=standard,
                        creator=creator,
                        level=row["maturity_level_level"],
                    )
                ml.set_current_language(lang)
                ml.label = row["maturity_level"]
                # add the color of domain if present of the import
                if row["maturity_level_color"]:
                    match = re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", row["maturity_level_color"])
                    if match:
                        ml.color = row["maturity_level_color"]
                ml.save()
                row["maturity_level_obj"] = ml
            if row["evidence"] is None:
                row["evidence"] = ""
        return super().before_import_row(row, **kwargs)

    # erase the temporary variable
    def after_import_row(self, row, row_result, **kwargs):
        if hasattr(self, "_current_import_row"):
            del self._current_import_row

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
        import_id_fields = ("security_objective", "maturity_level", "position")


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
    CeleryImportExportMixin,
    FunctionalityMixin,
    PermissionMixin,
    CustomTranslatableAdmin,
    ImportMixin,
    # ImportExportModelAdmin,
    # ExportActionModelAdmin,
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

    def has_import_permission(self, request):
        return request.user.has_perm("securityobjectives.add_securitymeasure")

    def has_export_permission(self, request):
        return request.user.has_perm("securityobjectives.view_securitymeasure")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("creator", "security_objective")
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:
            return fields + ["creator"]
        return fields

    translated_fields = ["description"]

    def get_resource_kwargs(self, request, *args, **kwargs):
        # This passes the current request object to the Resource's __init__
        return {"user_id": request.user.pk}

    def get_import_resource_kwargs(self, request, **kwargs):
        kwargs = super().get_import_resource_kwargs(request, **kwargs)
        kwargs["user_id"] = request.user.pk
        kwargs["lang"] = get_language() or PARLER_DEFAULT_LANGUAGE_CODE
        return kwargs

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
    CustomTranslatableAdmin,
    ImportMixin,
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
