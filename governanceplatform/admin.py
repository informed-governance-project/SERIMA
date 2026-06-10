from copy import deepcopy

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Exists, Max, Model, OuterRef, Q, Value
from django.db.models.fields import TextField
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path
from django.utils import translation
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django_otp import devices_for_user, user_has_device
from django_otp.decorators import otp_required
from django_otp.plugins.otp_totp.models import TOTPDevice
from parler.admin import TranslatableAdmin, TranslatableTabularInline

from governanceplatform.settings import PARLER_DEFAULT_LANGUAGE_CODE
from incidents.decorators import check_user_is_correct
from incidents.email import send_html_email

from .forms import CustomObserverAdminForm, CustomTranslatableAdminForm
from .formset import CompanyUserInlineFormset
from .helpers import (
    generate_display_methods,
    get_active_company_from_session,
    is_observer_user,
    is_user_operator,
    is_user_regulator,
    render_to_string_multi_languages,
    set_creator,
    user_in_group,
)
from .mixins import ShowReminderForTranslationsMixin
from .models import (  # OperatorType,; Service,
    ApplicationConfig,
    Company,
    CompanyUser,
    EntityCategory,
    Functionality,
    Observer,
    ObserverRegulation,
    ObserverUser,
    Regulation,
    Regulator,
    RegulatorUser,
    ScriptLogEntry,
    Sector,
    User,
)
from .permissions import set_platform_admin_permissions
from .settings import SITE_NAME


# get the id of a group by name
def get_group_id(name=""):
    try:
        group_id = Group.objects.get(name=name).id
    except ObjectDoesNotExist:
        group_id = None

    return group_id


class CustomAdminSite(admin.AdminSite):
    site_header = SITE_NAME + " " + _("Settings")
    site_title = SITE_NAME

    def admin_view(self, view, cacheable=False):
        decorated_view = otp_required(view)
        decorated_view = check_user_is_correct(decorated_view)
        return super().admin_view(decorated_view, cacheable)

    def get_app_list(self, request, app_label=None):
        """
        Override this method to organize models under custom sections.
        """
        app_list = super().get_app_list(request, app_label)

        user = request.user
        has_permission = user.has_perm("governanceplatform.view_scriptlogentry")

        # change the place of scriptlogentry to have it under the administration
        for app in app_list:
            if app["app_label"] == "admin" and has_permission:
                app["models"].append(
                    {
                        "name": capfirst(ScriptLogEntry._meta.verbose_name_plural),  # Human-readable name
                        "object_name": ScriptLogEntry._meta.object_name,
                        "admin_url": "/admin/governanceplatform/scriptlogentry/",
                        "view_only": True,
                        "perms": {
                            "add": False,
                            "change": False,
                            "view": True,
                            "delete": False,
                        },
                    }
                )
            if app["app_label"] == "governanceplatform":
                app["models"] = [model for model in app["models"] if model["object_name"] != ScriptLogEntry._meta.object_name]
        return app_list


admin_site = CustomAdminSite()


class CustomTranslatableAdmin(ShowReminderForTranslationsMixin, TranslatableAdmin):
    form = CustomTranslatableAdminForm

    translated_fields: list[str] = []

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        lang = request.LANGUAGE_CODE
        queryset = queryset.active_translations(lang).distinct()
        return queryset.distinct(), use_distinct

    """
    Automaticaly annotate field in translated_fields
    Give sortable column via `_field`
    Manage fallback if translation is not here
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        lang = getattr(request, "LANGUAGE_CODE", "en")
        default_lang = PARLER_DEFAULT_LANGUAGE_CODE

        annotations = {}

        for f in self.translated_fields:
            # Annotate value with the request lang and default one
            annotations[f"_{f}_lang"] = Max(f"translations__{f}", filter=Q(translations__language_code=lang))
            annotations[f"_{f}_default"] = Max(f"translations__{f}", filter=Q(translations__language_code=default_lang))

        qs = qs.annotate(**annotations)

        # Apply Coalesce for fallback (_field = _field_lang or _field_default or "")
        final_annotations = {}
        for f in self.translated_fields:
            final_annotations[f"_{f}"] = Coalesce(
                f"_{f}_lang",
                f"_{f}_default",
                Value(""),
                output_field=TextField(),
            )

        return qs.annotate(**final_annotations)


class CustomTranslatableTabularInline(TranslatableTabularInline):
    form = CustomTranslatableAdminForm


# Creation of a dummymodel to add the item in the django list
class SettingsDummy(Model):
    class Meta:
        managed = False
        verbose_name = _("Django Settings")
        verbose_name_plural = _("Django Settings")


@admin.register(SettingsDummy, site=admin_site)
class SettingsAdmin(admin.ModelAdmin):
    change_list_template = "admin/settings_list.html"

    def changelist_view(self, request, extra_context=None):
        settings_dict = {
            key: getattr(settings, key) for key in dir(settings) if key.isupper() and key not in settings.ADMIN_UNVISIBLE_VARIABLES
        }

        extra_context = extra_context or {}
        extra_context["settings"] = settings_dict

        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        return SettingsDummy.objects.none()


@admin.register(Site, site=admin_site)
class SiteAdmin(admin.ModelAdmin):
    pass


@admin.register(Sector, site=admin_site)
class SectorAdmin(CustomTranslatableAdmin):
    list_display = ["acronym", "name_display", "parent"]
    list_display_links = ["acronym", "name_display"]
    search_fields = ["translations__name", "acronym", "parent__translations__name"]
    fields = ("name", "parent", "acronym")
    ordering = ["id", "parent"]
    translated_fields = ["name"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            # Regulator Admin
            current_id = None
            if request.resolver_match.kwargs.get("object_id"):
                current_id = request.resolver_match.kwargs["object_id"]
            kwargs["queryset"] = Sector.objects.filter(parent=None).exclude(pk=current_id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)

        if obj.pk and obj.parent_id and obj.pk == obj.parent_id:
            messages.error(request, "A sector cannot have itself as a parent")
            return

        super().save_model(request, obj, form, change)


for name, method in generate_display_methods(["name"]).items():
    setattr(SectorAdmin, name, method)


@admin.register(EntityCategory, site=admin_site)
class EntityCategoryAdmin(CustomTranslatableAdmin):
    list_display = ["code", "label_display"]
    search_fields = ["translations__label", "code"]
    order_list = ["code"]
    fields = (
        "label",
        "code",
    )
    translated_fields = ["label"]


for name, method in generate_display_methods(["label"]).items():
    setattr(EntityCategoryAdmin, name, method)


class CompanyUserInline(admin.TabularInline):
    model = CompanyUser
    verbose_name = _("Contact for company")
    verbose_name_plural = _("Contacts for company")
    extra = 0
    formset = CompanyUserInlineFormset  # define formset for the clean function

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        platformAdminGroupId = get_group_id("PlatformAdmin")
        observerAdminGroupId = get_group_id("ObserverAdmin")
        observerUserGroupId = get_group_id("ObserverUser")
        regulatorAdminGroupId = get_group_id("RegulatorAdmin")
        regulatorUserGroupId = get_group_id("RegulatorUser")
        if db_field.name == "user":
            user = request.user
            # Regulator User and admin
            if user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin"):
                kwargs["queryset"] = (
                    User.objects.exclude(
                        groups__in=[
                            platformAdminGroupId,
                            observerAdminGroupId,
                            observerUserGroupId,
                            regulatorAdminGroupId,
                            regulatorUserGroupId,
                        ]
                    )
                    .filter(regulators=None, observers=None)
                    .order_by("email")
                )

            if user_in_group(user, "OperatorAdmin"):
                company_in_use = get_active_company_from_session(request)
                kwargs["queryset"] = (
                    User.objects.exclude(
                        groups__in=[
                            platformAdminGroupId,
                            observerAdminGroupId,
                            observerUserGroupId,
                            regulatorAdminGroupId,
                            regulatorUserGroupId,
                        ]
                    )
                    .filter(companies__in=[company_in_use])
                    .exclude(id=user.id)
                    .distinct()
                    .order_by("email")
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        has_admin = False
        if obj:
            has_admin = obj.companyuser_set.filter(is_company_administrator=True).exists()

        if not user_in_group(user, "OperatorAdmin") and has_admin:
            readonly_fields += ("approved",)

        return readonly_fields

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        if "user" in form.base_fields and user_in_group(request.user, "OperatorAdmin"):
            widget = form.base_fields["user"].widget
            widget.can_add_related = False

        # inject user into formset
        class UserFormset(formset):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs["user"] = request.user
                super().__init__(*args, **inner_kwargs)

        return UserFormset

    # Revoke the permissions of the logged user
    def has_add_permission(self, request, obj=None):
        if obj == request.user:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        user = request.user

        if obj and user_in_group(user, "RegulatorAdmin") and is_user_operator(obj):
            return False

        if obj == user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        user = request.user

        if obj and user_in_group(user, "RegulatorAdmin") and is_user_operator(obj):
            return False

        if obj == user:
            return False

        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        # Operator Admin
        if user_in_group(user, "OperatorAdmin"):
            company_in_use = get_active_company_from_session(request)
            return (
                queryset.filter(
                    company=company_in_use,
                )
                .exclude(user=user)
                .distinct()
            )
        return queryset


class CompanyUserMultipleInline(CompanyUserInline):
    max_num = None


@admin.register(Company, site=admin_site)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        "identifier",
        "name",
        "address",
        "country",
        "email",
        "phone_number",
    ]
    filter_horizontal = ["entity_categories", "sectors"]
    search_fields = [
        "name",
        "address",
        "country",
        "email",
        "phone_number",
        "identifier",
    ]
    inlines = (CompanyUserMultipleInline,)
    fieldsets = [
        (
            _("Contact information"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "name",
                    ("address", "country"),
                    ("email", "phone_number"),
                ],
            },
        ),
        (
            _("Configuration information"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "identifier",
                ],
            },
        ),
        (
            _("Entity categories"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "entity_categories",
                ],
            },
        ),
        (
            _("Sectors"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    "sectors",
                ],
            },
        ),
    ]

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        user = request.user
        # Exclude CompanyUserMultipleInline for RegulatorAdmin
        # because if we go for user creation it asks company and that's not good
        if user_in_group(user, "RegulatorAdmin"):
            inline_instances = []

        return inline_instances

    def get_readonly_fields(self, request, obj=None):
        # Platform Admin, Regulator Admin and Regulator User
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        # Operator Admin
        if user_in_group(user, "OperatorAdmin"):
            readonly_fields += ("identifier", "sectors")
        if not (user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin")):
            readonly_fields += ("entity_categories",)

        return readonly_fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        # Operator Admin
        if user_in_group(user, "OperatorAdmin"):
            company_in_use = get_active_company_from_session(request)
            is_company_administrator = company_in_use.companyuser_set.filter(user=user, is_company_administrator=True).exists()
            if is_company_administrator:
                queryset = queryset.filter(id=company_in_use.id)
            else:
                queryset = queryset.none()

        return queryset

    # we don't delete company with users
    def delete_queryset(self, request, queryset):
        annotated = queryset.annotate(_user_count=Count("user"))
        if annotated.filter(_user_count__gt=0).exists():
            messages.add_message(
                request,
                messages.WARNING,
                "Some companies haven't been deleted because they contain users",
            )
        annotated.filter(_user_count=0).delete()

    def delete_model(self, request, obj):
        if obj.user_set.count() > 0:
            messages.set_level(request, messages.WARNING)
            messages.add_message(
                request,
                messages.WARNING,
                "The company has user attached and can't be deleted",
            )
        else:
            obj.delete()

    def save_formset(self, request, form, formset, change):
        def send_suggestion_email(context, email_list):
            html_message = render_to_string_multi_languages("emails/suggestion_link_user_account.html", context)
            with translation.override(settings.LANGUAGE_CODE):
                subject = _("Suggestion to Link a User Account with Your Company")

            send_html_email(subject, html_message, email_list)

        company = formset.instance
        admins_qs = company.companyuser_set.filter(is_company_administrator=True).select_related("user")

        # Collect email tasks to send after the atomic block
        pending_emails = []

        with transaction.atomic():
            instances = formset.save(commit=False)

            for instance in instances:
                if user_in_group(instance.user, "IncidentUser") and user_in_group(request.user, "RegulatorUser"):
                    instance.approved = False
                    user = instance.user
                    if user and company and not user.companyuser_set.exclude(pk=instance.pk).exists() and admins_qs:
                        base_context = {
                            "operator_admin_name": None,
                            "new_user_name": user.get_full_name(),
                            "new_user_email": user.email,
                            "regulator": request.user.regulators.first().full_name,
                        }

                        if company.email:
                            pending_emails.append(
                                (
                                    dict(base_context, operator_admin_name=None),
                                    [company.email],
                                )
                            )

                        for operator_admin in admins_qs:
                            admin_user = operator_admin.user
                            admin_email = admin_user.email
                            pending_emails.append(
                                (
                                    dict(
                                        base_context,
                                        operator_admin_name=admin_user.get_full_name(),
                                    ),
                                    [admin_email],
                                )
                            )

                    if not admins_qs:
                        instance.approved = True

                if not user_in_group(instance.user, "IncidentUser"):
                    instance.approved = True

                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            formset.save_m2m()

        # Send emails outside the atomic block
        for context, email_list in pending_emails:
            send_suggestion_email(context, email_list)

    def has_export_permission(self, request):
        return self.has_view_permission(request)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)


class userRegulatorInline(admin.TabularInline):
    model = RegulatorUser
    extra = 0
    min_num = 1
    max_num = 1

    filter_horizontal = [
        "sectors",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            return qs.filter(is_regulator_administrator=True)
        return qs

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "regulator":
            user = request.user
            # Platform Admin
            if user_in_group(user, "PlatformAdmin"):
                kwargs["queryset"] = Regulator.objects.all()
            # Regulator Admin
            if user_in_group(user, "RegulatorAdmin"):
                kwargs["queryset"] = user.regulators.all()

        if db_field.name == "user":
            RegulatorAdminGroupId = get_group_id(name="RegulatorAdmin")
            RegulatorUserGroupId = get_group_id(name="RegulatorUser")
            user = request.user
            # Platform Admin
            current_id = None
            if request.resolver_match.kwargs.get("object_id"):
                current_id = request.resolver_match.kwargs["object_id"]
            if user_in_group(user, "PlatformAdmin"):
                kwargs["queryset"] = User.objects.filter(
                    Q(groups=None)
                    | Q(
                        groups__in=[RegulatorAdminGroupId],
                        regulators=None,
                    )
                    | Q(
                        groups__in=[RegulatorAdminGroupId],
                        regulators=current_id,
                    )
                )
            # Regulator Admin
            if user_in_group(user, "RegulatorAdmin"):
                kwargs["queryset"] = User.objects.filter(
                    Q(
                        groups__in=[RegulatorAdminGroupId, RegulatorUserGroupId],
                        regulators=None,
                    )
                    | Q(
                        groups__in=[RegulatorAdminGroupId, RegulatorUserGroupId],
                        regulators=user.regulators.first(),
                    )
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Revoke the permissions of the logged user
    def has_add_permission(self, request, obj=None):
        if obj == request.user:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj == request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj == request.user:
            return False
        return super().has_delete_permission(request, obj)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if user_in_group(request.user, "PlatformAdmin"):
            if "is_regulator_administrator" in formset.form.base_fields:
                formset.form.base_fields["is_regulator_administrator"].widget = forms.HiddenInput()
                formset.form.base_fields["is_regulator_administrator"].initial = True
            if "sectors" in formset.form.base_fields:
                formset.form.base_fields.pop("sectors", None)

        if not user_in_group(request.user, "PlatformAdmin"):
            if "can_export_incidents" in formset.form.base_fields:
                formset.form.base_fields["can_export_incidents"].widget = forms.HiddenInput()

        formset.empty_permitted = False
        return formset

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        # only the platform admin can change the can_export_incidents
        if not user_in_group(user, "PlatformAdmin"):
            readonly_fields += ("can_export_incidents",)

        return readonly_fields


class userRegulatorMultipleInline(userRegulatorInline):
    max_num = None


# reset the 2FA we delete the TOTP devices
@admin.action(description=_("Reset 2FA"))
def reset_2FA(modeladmin, request, queryset):
    request_user = request.user
    for user in queryset:
        # conditions for regulatoradmin issue #550
        if user_in_group(request_user, "RegulatorAdmin") and not (
            user_in_group(user, "RegulatorAdmin") or user_in_group(user, "RegulatorUser")
        ):
            continue
        # conditions for RegulatorUser issue #577
        if user_in_group(request_user, "RegulatorUser") and (user_in_group(user, "RegulatorAdmin") or user_in_group(user, "RegulatorUser")):
            continue
        devices = devices_for_user(user)
        for device in devices:
            device.delete()


class UserRegulatorsListFilter(SimpleListFilter):
    title = _("Regulators")
    parameter_name = "regulators"

    def lookups(self, request, model_admin):
        regulators = Regulator.objects.none()
        user = request.user
        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            regulators = Regulator.objects.all()
        return [(regulator.id, regulator) for regulator in regulators]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(regulators=value)
        return queryset


class ObserverUsersListFilter(SimpleListFilter):
    title = _("Observer")
    parameter_name = "observers"

    def lookups(self, request, model_admin):
        observers = Observer.objects.none()
        user = request.user
        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            observers = Observer.objects.all()
        return [(observer.id, observer) for observer in observers]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(observers=value)
        return queryset


class UserCompaniesListFilter(SimpleListFilter):
    title = _("Operators")
    parameter_name = "companies"

    def lookups(self, request, model_admin):
        companies = Company.objects.all()
        user = request.user
        # Platform Admin
        if not is_user_regulator(user):
            companies = Company.objects.none()

        return [(company.id, company.name) for company in companies]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(companies=value).distinct()
        return queryset


class UserPermissionsGroupListFilter(SimpleListFilter):
    title = _("Roles")
    parameter_name = "roles"

    def lookups(self, request, model_admin):
        groups = Group.objects.all()
        user = request.user

        if user_in_group(user, "RegulatorAdmin"):
            groups = groups.exclude(
                name__in=[
                    "PlatformAdmin",
                    "ObserverAdmin",
                    "ObserverUser",
                ]
            )

        if user_in_group(user, "PlatformAdmin"):
            groups = groups.exclude(
                name__in=[
                    "OperatorAdmin",
                    "OperatorUser",
                    "IncidentUser",
                    "ObserverUser",
                    "RegulatorUser",
                ]
            )

        if user_in_group(user, "ObserverAdmin"):
            groups = groups.exclude(
                name__in=[
                    "PlatformAdmin",
                    "RegulatorAdmin",
                    "RegulatorUser",
                    "OperatorAdmin",
                    "OperatorUser",
                    "IncidentUser",
                ]
            )

        if user_in_group(user, "RegulatorUser"):
            groups = groups.exclude(
                name__in=[
                    "PlatformAdmin",
                    "RegulatorAdmin",
                    "ObserverAdmin",
                    "ObserverUser",
                ]
            )

        if user_in_group(user, "OperatorAdmin"):
            groups = groups.filter(name__in=["OperatorAdmin", "OperatorUser"])
        return [(group.id, group.name) for group in groups]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(groups=self.value())
        # little hack to have the default view when a regulator admin logged in req41
        if self.value() is None and not request.GET and user_in_group(request.user, "RegulatorAdmin"):
            return queryset.filter(Q(regulators=request.user.regulators.first()) | Q(groups__in=[get_group_id("RegulatorUser")])).distinct()
        return queryset


@admin.register(User, site=admin_site)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        "is_active",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "get_regulators",
        "get_companies",
        "get_observers",
        "get_permissions_groups",
        "get_2FA_activation",
        "email_verified",
        "date_joined",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "companies__name",
        "regulators__translations__name",
        "observers__translations__name",
        "groups__name",
    ]
    list_filter = [
        UserRegulatorsListFilter,
        ObserverUsersListFilter,
        UserCompaniesListFilter,
        UserPermissionsGroupListFilter,
    ]
    list_display_links = ("email", "first_name", "last_name")
    standard_fieldsets = [
        (
            _("Contact information"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    ("first_name", "last_name"),
                    ("email", "phone_number"),
                ],
            },
        ),
    ]
    # add is_active for RegulatorAdmin
    admin_fieldsets = [
        (
            _("Contact information"),
            {
                "classes": ["extrapretty"],
                "fields": [
                    ("first_name", "last_name"),
                    ("email", "phone_number"),
                    ("is_active"),
                ],
            },
        ),
    ]
    actions = [reset_2FA]
    change_list_template = "admin/reset_accepted_terms.html"

    # manage the administrator field for operatorAdmin
    def get_form(self, request, obj=None, change=False, **kwargs):

        if not obj and user_in_group(request.user, "OperatorAdmin"):

            class DynamicForm(forms.ModelForm):
                is_administrator = forms.BooleanField(required=False, label=_("Create this user as an administrator"))

                class Meta:
                    model = self.model
                    fields = "__all__"

            kwargs["form"] = DynamicForm

        return super().get_form(request, obj, change, **kwargs)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "reset-accepted-terms/",
                self.admin_site.admin_view(self.reset_accepted_terms),
                name="reset_accepted_terms",
            ),
            path(
                "reset-cookie-acceptation/",
                self.admin_site.admin_view(self.reset_cookie_acceptation),
                name="reset_cookie_acceptation",
            ),
        ]
        return custom_urls + urls

    def reset_cookie_acceptation(self, request):
        if not user_in_group(request.user, "PlatformAdmin"):
            raise Http404()

        cfg = ApplicationConfig.objects.get(key="cookiebanner")
        if cfg:
            cfg.change_uuid_value()
        messages.success(request, _("Cookies acceptation has been reseted"))
        return redirect("..")

    def reset_accepted_terms(self, request):
        if not user_in_group(request.user, "PlatformAdmin"):
            raise Http404()

        User.objects.update(accepted_terms=False)
        messages.success(request, _("Terms acceptation has been reset"))
        return redirect("..")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if user_in_group(request.user, "PlatformAdmin"):
            extra_context["reset_url"] = "reset-accepted-terms/"
            extra_context["reset_url_cookies"] = "reset-cookie-acceptation/"
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description="2FA", boolean=True, ordering="has_2fa")
    def get_2FA_activation(self, obj):
        return bool(user_has_device(obj))

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = (
            "get_permissions_groups",
            "date_joined",
            "get_2FA_activation",
            "email_verified",
        )

        if obj is None:
            return readonly_fields

        if user_in_group(obj, "PlatformAdmin"):
            return readonly_fields
        if is_user_regulator(obj):
            return ("get_regulators",) + readonly_fields
        if is_observer_user(obj):
            return ("get_observers",) + readonly_fields

        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        if not obj:
            fieldsets = deepcopy(self.standard_fieldsets)
            if user_in_group(request.user, "OperatorAdmin"):
                fields = list(fieldsets[0][1]["fields"])
                if "is_administrator" not in fields:
                    fields.append("is_administrator")
                fieldsets[0][1]["fields"] = fields
            return fieldsets

        user = request.user
        use_admin_fieldsets = False

        # RegulatorAdmin
        if is_user_regulator(user):
            if not user_in_group(obj, "PlatformAdmin") and obj.pk != user.pk:
                use_admin_fieldsets = True

        # PlatformAdmin
        if user_in_group(user, "PlatformAdmin"):
            if (user_in_group(obj, "RegulatorAdmin") or user_in_group(obj, "PlatformAdmin")) and obj.pk != user.pk:
                use_admin_fieldsets = True

        fieldsets = self.admin_fieldsets if use_admin_fieldsets else self.standard_fieldsets
        readonly_fields = self.get_readonly_fields(request, obj)

        existing_fields = {field for _, opts in fieldsets for field in opts.get("fields", [])}

        extra_fields = [f for f in readonly_fields if f not in existing_fields]

        if extra_fields:
            fieldsets = list(fieldsets) + [
                (
                    _("Additional information"),
                    {"fields": tuple(extra_fields)},
                )
            ]

        return fieldsets

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        user = request.user

        # Exclude all inlines for the logged-in user
        if obj and obj == user:
            return []

        # PlatformAdmin inlines
        if user_in_group(user, "PlatformAdmin"):
            inline_instances = []

        # RegulatorAdmin inlines
        if user_in_group(user, "RegulatorAdmin"):
            if obj and is_user_regulator(obj):
                inline_instances = [userRegulatorInline(self.model, self.admin_site)]
            if obj and is_user_operator(obj):
                inline_instances = []

        # RegulatorUser inlines
        if user_in_group(user, "RegulatorUser"):
            if obj and user_in_group(obj, "OperatorAdmin"):
                inline_instances = []

        # OperatorAdmin inlines
        if user_in_group(user, "OperatorAdmin"):
            inline_instances = []

        return inline_instances

    def get_list_display(self, request):
        list_display = super().get_list_display(request)

        if user_in_group(request.user, "PlatformAdmin"):
            fields_to_exclude = ["get_companies"]
            list_display = [field for field in list_display if field not in fields_to_exclude]

        if user_in_group(request.user, "ObserverAdmin"):
            fields_to_exclude = [
                "get_companies",
                "get_regulators",
                "is_active",
            ]
            list_display = [field for field in list_display if field not in fields_to_exclude]

        if user_in_group(request.user, "RegulatorUser"):
            fields_to_exclude = [
                "get_regulators",
                "get_observers",
            ]
            list_display = [field for field in list_display if field not in fields_to_exclude]
        if user_in_group(request.user, "RegulatorAdmin"):
            fields_to_exclude = ["get_observers"]
            list_display = [field for field in list_display if field not in fields_to_exclude]
        if user_in_group(request.user, "OperatorAdmin"):
            fields_to_exclude = [
                "get_companies",
                "get_regulators",
                "get_observers",
                "is_active",
            ]
            list_display = [field for field in list_display if field not in fields_to_exclude]

        return list_display

    def get_queryset(self, request):
        # stock the request
        self._request = request
        queryset = super().get_queryset(request).annotate(has_2fa=Exists(TOTPDevice.objects.filter(user=OuterRef("pk"), confirmed=True)))
        user = request.user

        PlatformAdminGroupId = get_group_id(name="PlatformAdmin")
        RegulatorAdminGroupId = get_group_id(name="RegulatorAdmin")
        observerAdminGroupId = get_group_id(name="ObserverAdmin")
        observerUserGroupId = get_group_id(name="ObserverUser")

        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            return queryset.filter(
                Q(groups=None)
                | Q(
                    groups__in=[
                        PlatformAdminGroupId,
                        RegulatorAdminGroupId,
                        observerAdminGroupId,
                    ]
                )
            )
        # Regulator Admin
        if user_in_group(user, "RegulatorAdmin"):
            return queryset.exclude(
                groups__in=[
                    PlatformAdminGroupId,
                    observerUserGroupId,
                    observerAdminGroupId,
                ]
            ).filter(Q(regulators=user.regulators.first()) | Q(regulators=None))
        # Regulator User
        if user_in_group(user, "RegulatorUser"):
            return queryset.exclude(
                Q(groups=None)
                | Q(
                    groups__in=[
                        PlatformAdminGroupId,
                        RegulatorAdminGroupId,
                        observerUserGroupId,
                        observerAdminGroupId,
                    ]
                ),
            ).filter(Q(regulators=user.regulators.first()) | Q(regulators=None))
        # Observer Admin
        if user_in_group(user, "ObserverAdmin"):
            return queryset.filter(Q(observers=user.observers.first()))
        # Operator Admin
        if user_in_group(user, "OperatorAdmin"):
            company_in_use = get_active_company_from_session(request)
            return queryset.filter(
                companies__in=[company_in_use],
            ).distinct()
        return queryset

    def has_change_permission(self, request, obj=None):
        user = request.user
        if obj and user_in_group(user, "RegulatorUser") and (obj == user or is_user_operator(obj) or user_in_group(obj, "IncidentUser")):
            return True
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj:
            if (
                user_in_group(obj, "RegulatorUser")
                or user_in_group(obj, "RegulatorAdmin")
                or user_in_group(obj, "PlatformAdmin")
                or user_in_group(obj, "OperatorAdmin")
            ) and obj.logentry_set.all().count() > 0:
                return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        user = request.user
        super().save_model(request, obj, form, change)
        if not change:
            # in ObserverAdmin we can only add user for our Observer entity and default is ObserverUser
            if user_in_group(user, "ObserverAdmin"):
                group, _ = Group.objects.get_or_create(name="ObserverUser")
                obj.observers.add(user.observers.first())
                obj.groups.add(group)

            # in RegulatorAdmin we can only add user for regulator and default is RegulatorUser
            if user_in_group(user, "RegulatorAdmin"):
                group, _ = Group.objects.get_or_create(name="RegulatorUser")
                obj.groups.add(group)

            # in RegulatorUser or OperatorAdmin we can only add user for operators and default is OperatorUser
            # operators have to be created under companies
            if user_in_group(user, "RegulatorUser"):
                group, _ = Group.objects.get_or_create(name="OperatorUser")
                obj.groups.add(group)

            if user_in_group(user, "OperatorAdmin"):
                is_admin = form.cleaned_data.get("is_administrator")
                company_in_use = get_active_company_from_session(request)
                if company_in_use:
                    obj.companies.add(company_in_use, through_defaults={"approved": True, "is_company_administrator": is_admin})
                group, _ = Group.objects.get_or_create(name="OperatorUser")
                obj.groups.add(group)

            # in PlatformAdmin we add by default platformadmin
            # if we are not in a popup we create a platformAdmin
            if user_in_group(user, "PlatformAdmin") and "to_field=id&_popup" not in request.get_full_path():
                group, _ = Group.objects.get_or_create(name="PlatformAdmin")
                obj.groups.add(group)
                set_platform_admin_permissions(obj)

    # override delete to don't delete RegulatorAdmin RegulatorUser and PlatformAdmin (put them inactive)
    def delete_model(self, request, obj):
        if user_in_group(obj, "PlatformAdmin") or is_user_regulator(obj):
            obj.is_active = False
            obj.save()
        else:
            obj.delete()

    def has_export_permission(self, request):
        return self.has_view_permission(request)


@admin.register(Functionality, site=admin_site)
class FunctionalityAdmin(CustomTranslatableAdmin):
    list_display = ["type", "name_display"]
    search_fields = ["translations__name"]
    order_list = ["type"]
    translated_fields = ["name"]


for name, method in generate_display_methods(["name"]).items():
    setattr(FunctionalityAdmin, name, method)


@admin.register(Regulator, site=admin_site)
class RegulatorAdmin(CustomTranslatableAdmin):
    list_display = ["name_display", "full_name_display", "description_display"]
    search_fields = [
        "translations__name",
        "translations__full_name",
        "translations__description",
    ]
    fields = (
        "name",
        "full_name",
        "description",
        "country",
        "address",
        "email_for_notification",
        "functionalities",
    )

    filter_horizontal = [
        "functionalities",
    ]
    translated_fields = ["name", "full_name", "description"]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        # only the platform admin can change the functionalities
        if not user_in_group(user, "PlatformAdmin"):
            readonly_fields += ("functionalities",)

        return readonly_fields

    inlines = (userRegulatorMultipleInline,)

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user_in_group(user, "RegulatorAdmin") and obj != user.regulators.first():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user_in_group(user, "RegulatorAdmin") and obj != user.regulators.first():
            return False
        return super().has_delete_permission(request, obj)


for name, method in generate_display_methods(["name", "full_name", "description"]).items():
    setattr(RegulatorAdmin, name, method)


class ObserverRegulationInline(admin.TabularInline):
    model = ObserverRegulation
    verbose_name = _("Observer regulation")
    filter_horizontal = ("sectors",)
    verbose_name_plural = _("Observer regulations")
    extra = 0
    min_num = 0

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "sectors":
            # exclude parent with children from the list
            kwargs["queryset"] = Sector.objects.annotate(child_count=Count("children")).exclude(parent=None, child_count__gt=0)

        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ObserverUserInline(admin.TabularInline):
    model = ObserverUser
    verbose_name = _("Observer user")
    verbose_name_plural = _("Observer users")
    extra = 0
    min_num = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # Platform Admin
        if user_in_group(user, "PlatformAdmin"):
            return qs.filter(is_observer_administrator=True)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            ObserverAdminGroupID = get_group_id(name="ObserverAdmin")
            ObserverUserGroupID = get_group_id(name="ObserverUser")
            user = request.user
            current_id = None
            if "object_id" in request.resolver_match.kwargs:
                current_id = request.resolver_match.kwargs["object_id"]
            if user_in_group(user, "PlatformAdmin"):
                kwargs["queryset"] = User.objects.filter(
                    Q(groups=None)
                    | Q(
                        groups__in=[ObserverAdminGroupID],
                        observers=None,
                    )
                    | Q(
                        groups__in=[ObserverAdminGroupID],
                        observers=current_id,
                    )
                )
            # Observer Admin
            if user_in_group(user, "ObserverAdmin"):
                kwargs["queryset"] = User.objects.filter(
                    Q(
                        groups__in=[ObserverAdminGroupID],
                        observers=None,
                    )
                    | Q(
                        groups__in=[ObserverAdminGroupID, ObserverUserGroupID],
                        observers=user.observers.first(),
                    )
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if user_in_group(request.user, "PlatformAdmin") and "is_observer_administrator" in formset.form.base_fields:
            formset.form.base_fields["is_observer_administrator"].widget = forms.HiddenInput()
            formset.form.base_fields["is_observer_administrator"].initial = True

        if not user_in_group(request.user, "PlatformAdmin"):
            if "can_export_incidents" in formset.form.base_fields:
                formset.form.base_fields["can_export_incidents"].widget = forms.HiddenInput()

        formset.empty_permitted = False
        return formset

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        # only the platform admin can change the can_export_incidents
        if not user_in_group(user, "PlatformAdmin"):
            readonly_fields += ("can_export_incidents",)

        return readonly_fields


@admin.register(Observer, site=admin_site)
class ObserverAdmin(CustomTranslatableAdmin):
    form = CustomObserverAdminForm
    list_display = [
        "name_display",
        "full_name_display",
        "is_receiving_all_incident",
        "description_display",
    ]
    search_fields = [
        "translations__name",
        "translations__full_name",
        "translations__description",
    ]
    filter_horizontal = [
        "functionalities",
    ]
    translated_fields = ["name", "description", "full_name"]

    inlines = (
        ObserverUserInline,
        ObserverRegulationInline,
    )

    def get_fieldsets(self, request, obj=None):
        base_fieldsets = [
            (
                None,
                {
                    "fields": [
                        "name",
                        "full_name",
                        "description",
                        "country",
                        "address",
                        "email_for_notification",
                        "is_receiving_all_incident",
                        "functionalities",
                    ],
                },
            ),
        ]

        if is_observer_user(request.user):
            base_fieldsets.append(
                (
                    "RT Configuration",
                    {
                        "classes": ["collapse"],
                        "fields": ["rt_url", "rt_token", "rt_queue"],
                    },
                )
            )

        return base_fieldsets

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user_in_group(user, "ObserverAdmin") and obj != user.observers.first():
            return False
        return super().has_change_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        user = request.user
        # Observer Admin
        if user_in_group(user, "ObserverAdmin"):
            return queryset.filter(
                user=user,
            )

        return queryset

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        user = request.user
        # only the platform admin can change the is_receive_all_incident
        if not user_in_group(user, "PlatformAdmin"):
            readonly_fields += ("is_receiving_all_incident", "functionalities")

        return readonly_fields


for name, method in generate_display_methods(["name", "full_name", "description"]).items():
    setattr(ObserverAdmin, name, method)


@admin.register(Regulation, site=admin_site)
class RegulationAdmin(CustomTranslatableAdmin):
    list_display = ["label_display", "get_regulators"]
    search_fields = ["translations__label", "regulators__translations__name"]
    fields = (
        "label",
        "regulators",
    )
    filter_horizontal = [
        "regulators",
    ]
    translated_fields = ["label"]


for name, method in generate_display_methods(["label"]).items():
    setattr(RegulationAdmin, name, method)


@admin.register(ScriptLogEntry, site=admin_site)
class ScriptLogEntryAdmin(admin.ModelAdmin):
    list_display = ["action_time", "action", "object_repr", "additional_info"]
    readonly_fields = [
        "action_time",
        "action",
        "object_id",
        "object_repr",
        "additional_info",
    ]
    search_fields = ["object_repr"]
