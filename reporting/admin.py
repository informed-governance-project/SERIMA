from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin

from governanceplatform.admin import CustomTranslatableAdmin, admin_site
from governanceplatform.mixins import FunctionalityMixin, TranslationUpdateMixin
from governanceplatform.models import Regulation, Sector
from governanceplatform.widgets import TranslatedNameM2MWidget

from .forms import TemplateAdminForm
from .models import Color, Configuration, ObservationRecommendation, Template


class ObservationRecommendationResource(TranslationUpdateMixin, resources.ModelResource):
    id = fields.Field(
        column_name="id",
        attribute="id",
    )
    code = fields.Field(
        column_name="code",
        attribute="code",
    )
    description = fields.Field(
        column_name="description",
        attribute="description",
    )

    sectors = fields.Field(
        column_name="sectors",
        attribute="sectors",
        widget=TranslatedNameM2MWidget(Sector, field="name", separator="|"),
    )

    class Meta:
        model = ObservationRecommendation
        fields = (
            "id",
            "code",
            "description",
            "sectors",
        )
        export_order = fields


@admin.register(ObservationRecommendation, site=admin_site)
class ObservationRecommendationAdmin(FunctionalityMixin, CustomTranslatableAdmin, ImportExportModelAdmin):
    resource_class = ObservationRecommendationResource
    list_display = ["code", "description", "get_sector_name"]
    search_fields = ["code", "description"]
    filter_horizontal = ("sectors",)
    fields = (
        "code",
        "description",
        "sectors",
    )

    # Hidden temporally
    def has_module_permission(self, request):
        return False

    @admin.display(description=_("Sectors"))
    def get_sector_name(self, obj):
        return [sector for sector in obj.sectors.all()]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ColorInline(admin.TabularInline):
    model = Color
    extra = 0
    fields = ("position", "color")


class TemplateInline(admin.TabularInline):
    model = Template
    form = TemplateAdminForm
    extra = 0
    fields = ("language", "template_file", "download_link")
    readonly_fields = ("download_link",)

    @admin.display(description=_("Current file"))
    def download_link(self, obj):
        if obj.pk and obj.template_file:
            url = reverse("reporting_template_download", args=[obj.pk])
            return format_html(
                '<a class="viewlink" href="{}" download>{}</a>',
                url,
                _("Download"),
            )
        return "—"


@admin.register(Configuration, site=admin_site)
class ConfigurationAdmin(FunctionalityMixin, admin.ModelAdmin):
    inlines = [TemplateInline, ColorInline]
    list_display = ("display_regulation", "standard", "regulator")
    fields = ["standard"]

    @admin.display(description=_("Regulation"))
    def display_regulation(self, obj):
        if obj.pk and obj.standard:
            return str(obj.standard.regulation)
        return "-"

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:
            return fields + ["regulator"]
        return fields

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("regulator",)
        return ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "regulation":
            regulator = request.user.regulators.first()
            kwargs["queryset"] = Regulation.objects.filter(regulators=regulator).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        user = request.user
        obj.regulator = user.regulators.first()
        super().save_model(request, obj, form, change)
