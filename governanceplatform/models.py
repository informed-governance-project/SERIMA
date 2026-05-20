import importlib
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.contrib.sessions.base_session import AbstractBaseSession
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models import Deferrable, Q
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from parler.models import TranslatableModel, TranslatedFields
from phonenumber_field.modelfields import PhoneNumberField

import governanceplatform
from incidents.models import Incident

from .globals import ACTION_FLAG_CHOICES, get_functionality_choices
from .managers import CustomUserManager
from .settings import RT_SECRET_KEY
from .validators import validate_rt_url


class ApplicationConfig(models.Model):
    key = models.CharField(max_length=128, unique=True)
    value = models.CharField(max_length=255)

    def change_uuid_value(self):
        self.value = uuid.uuid4().hex[:8]
        self.save()


# sector
class Sector(TranslatableModel):
    translations = TranslatedFields(name=models.CharField(_("Name"), max_length=100))
    parent = models.ForeignKey(
        "self",
        null=True,
        on_delete=models.CASCADE,
        blank=True,
        default=None,
        verbose_name=_("Parent Sector"),
        related_name="children",
    )
    acronym = models.CharField(verbose_name=_("Acronym"), max_length=4)

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

    def get_safe_translation(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""

    def __str__(self):
        name = self.safe_translation_getter("name", any_language=True)
        if name and self.parent:
            parent_name = self.parent.safe_translation_getter("name", any_language=True)
            return parent_name + " → " + name
        if name and self.parent is None:
            return name
        return ""

    class Meta:
        verbose_name = _("Sector")
        verbose_name_plural = _("Sectors")


# esssential services
class Service(TranslatableModel):
    translations = TranslatedFields(name=models.CharField(_("Name"), max_length=100))
    sector = models.ForeignKey(Sector, verbose_name=_("Sector"), on_delete=models.CASCADE)
    acronym = models.CharField(verbose_name=_("Acronym"), max_length=4)

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation if name_translation else ""

    class Meta:
        verbose_name = _("Service")
        verbose_name_plural = _("Services")


class Functionality(TranslatableModel):
    translations = TranslatedFields(name=models.CharField(verbose_name=_("Name"), max_length=100))

    type = models.CharField(
        verbose_name=_("Type"),
        max_length=100,
        choices=get_functionality_choices,
        null=False,
        unique=True,
    )

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["type"],
                name="Unique_Type",
                deferrable=Deferrable.DEFERRED,
            ),
        ]
        verbose_name = _("Functionality")
        verbose_name_plural = _("Functionalities")


# operator has type (critical, essential, etc.) who give access to functionalities
class OperatorType(TranslatableModel):
    translations = TranslatedFields(type=models.CharField(verbose_name=_("Type"), max_length=100))
    functionalities = models.ManyToManyField(
        Functionality,
        verbose_name=_("Functionalities"),
    )

    def __str__(self):
        type_translation = self.safe_translation_getter("type", any_language=True)
        return type_translation or ""


# operator are companies
class Company(models.Model):
    identifier = models.CharField(
        max_length=10,
        verbose_name=_("Acronym"),
        unique=True,
    )  # requirement from business concat(name_country_regulator)
    name = models.CharField(max_length=64, verbose_name=_("Name"), unique=True)
    country = models.CharField(
        max_length=200,
        verbose_name=_("Country"),
        null=True,
        choices=list(CountryField().choices),
    )
    address = models.CharField(
        max_length=255,
        verbose_name=_("Address"),
        blank=True,
        default=None,
        null=True,
    )
    email = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default=None,
        verbose_name=_("Email address"),
    )
    phone_number = PhoneNumberField(
        verbose_name=_("Phone number"),
        max_length=30,
        blank=True,
        default=None,
        null=True,
    )
    types = models.ManyToManyField(
        OperatorType,
        verbose_name=_("Types"),
    )
    entity_categories = models.ManyToManyField(
        "governanceplatform.EntityCategory",
        verbose_name=_("Entity categories"),
        blank=True,
    )
    sectors = models.ManyToManyField(
        Sector,
        verbose_name=_("sectors"),
        blank=True,
    )

    def __str__(self):
        return self.name

    def security_objective_exists(self, year=None, sector=None):
        if not (year and sector):
            return False

        return self.standardanswer_set.filter(year_of_submission=year, sectors__in=[sector.id], status="PASS").exists()

    def risk_analysis_exists(self, year=None, sector=None):
        if not (year and sector):
            return False

        return self.companyreporting_set.filter(year=year, sector=sector, servicestat__isnull=False).exists()

    class Meta:
        verbose_name = _("Operator")
        verbose_name_plural = _("Operators")


# Regulator
class Regulator(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(max_length=64, verbose_name=_("Name")),
        full_name=models.TextField(blank=True, default="", null=True, verbose_name=_("Full name")),
        description=models.TextField(blank=True, default="", null=True, verbose_name=_("Description")),
    )
    country = models.CharField(
        max_length=200,
        null=True,
        choices=list(CountryField().choices),
        verbose_name=_("Country"),
    )
    address = models.CharField(max_length=255, verbose_name=_("Address"))
    email_for_notification = models.EmailField(
        verbose_name=_("E-mail address for incident notification"),
        default=None,
        blank=True,
        null=True,
    )
    functionalities = models.ManyToManyField(
        Functionality,
        verbose_name=_("Functionalities"),
        blank=True,
    )

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""

    class Meta:
        verbose_name = _("Regulator")
        verbose_name_plural = _("Regulators")


# Observer
class Observer(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(default="", max_length=64, verbose_name=_("Name")),
        full_name=models.TextField(blank=True, default="", null=True, verbose_name=_("Full name")),
        description=models.TextField(blank=True, default="", null=True, verbose_name=_("Description")),
    )
    country = models.CharField(
        max_length=200,
        null=True,
        choices=list(CountryField().choices),
        verbose_name=_("Country"),
    )
    address = models.CharField(max_length=255, verbose_name=_("Address"))
    email_for_notification = models.EmailField(
        verbose_name=_("E-mail address for incident notification"),
        default=None,
        blank=True,
        null=True,
    )
    is_receiving_all_incident = models.BooleanField(default=False, verbose_name=_("Receives all incident notifications"))
    functionalities = models.ManyToManyField(
        Functionality,
        verbose_name=_("Functionalities"),
        blank=True,
    )

    rt_url = models.URLField(
        blank=True,
        null=True,
        help_text="e.g., https://rt.exemple.com",
        verbose_name=_("URL"),
        validators=[
            URLValidator(),
            validate_rt_url,
        ],
    )
    _rt_token = models.CharField(
        db_column="rt_token",
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Token"),
    )

    @property
    def rt_token(self):
        if self._rt_token is None or self._rt_token == "" or self._rt_token.strip() == "":
            return ""
        try:
            cipher_suite = Fernet(RT_SECRET_KEY)
            val = cipher_suite.decrypt(str.encode(self._rt_token))
            return val.decode()
        except Exception:
            return ""

    @rt_token.setter
    def rt_token(self, val):
        if not val:
            self._rt_token = None
            return

        cipher_suite = Fernet(RT_SECRET_KEY)

        enc_val = cipher_suite.encrypt(str.encode(val))
        self._rt_token = enc_val.decode()

    rt_queue = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Queue"))

    def get_incidents(self):
        base_qs = Incident.objects.exclude(sector_regulation__isnull=True)

        if self.is_receiving_all_incident:
            return base_qs

        observer_regulations = self.observerregulation_set.all()
        if not observer_regulations:
            return Incident.objects.none()

        final_q = Q()

        for observer_regulation in observer_regulations:
            regulation = observer_regulation.regulation
            sectors = observer_regulation.sectors.all()
            filter_conditions = observer_regulation.incident_rule
            conditions = filter_conditions.get("conditions", [])

            regulation_q = Q(sector_regulation__regulation=regulation)
            sectors_q = Q(affected_sectors__in=sectors)

            if conditions:
                for condition in conditions:
                    condition_q = Q()

                    for code in condition.get("include", []):
                        condition_q &= Q(company__entity_categories__code=code)

                    for code in condition.get("exclude", []):
                        condition_q &= ~Q(company__entity_categories__code=code)

                    final_q |= regulation_q & sectors_q & condition_q
            else:
                final_q |= regulation_q & sectors_q

        return base_qs.filter(final_q).distinct()

    def can_access_incident(self, incident):
        if incident in self.get_incidents():
            return True
        return False

    def __str__(self):
        name_translation = self.safe_translation_getter("name", any_language=True)
        return name_translation or ""

    class Meta:
        verbose_name = _("Observer")
        verbose_name_plural = _("Observers")


# define an abstract class which make  the difference between operator and regulator
class User(AbstractUser, PermissionsMixin):
    username = None
    email = models.EmailField(
        verbose_name=_("Email address"),
        unique=True,
        error_messages={
            "unique": _("An account with this email address already exists."),
        },
    )
    phone_number = PhoneNumberField(
        max_length=30,
        blank=True,
        default=None,
        null=True,
        verbose_name=_("Phone number"),
    )
    companies = models.ManyToManyField(
        Company,
        through="CompanyUser",
        verbose_name=_("Operators"),
    )
    regulators = models.ManyToManyField(
        Regulator,
        through="RegulatorUser",
        verbose_name=_("Regulators"),
    )
    observers = models.ManyToManyField(
        Observer,
        through="ObserverUser",
        verbose_name=_("Observers"),
    )

    is_staff = models.BooleanField(
        verbose_name=_("Administrator"),
        default=False,
        help_text=_("Determines if the user can log in via the administration interface."),
    )

    email_verified = models.BooleanField(
        verbose_name=_("Email verified"),
        default=False,
        help_text=_("Indicates whether the user has verified their email address."),
    )

    accepted_terms = models.BooleanField(default=False)
    accepted_terms_date = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    @admin.display(
        description=_("Companies"),
        ordering="companies__name",
    )
    def get_companies(self):
        return ", ".join([company.name for company in self.companies.all().distinct()])

    @admin.display(
        description=_("Regulator"),
        ordering="regulators__translations__name",
    )
    def get_regulators(self):
        return ", ".join([regulator.safe_translation_getter("name", any_language=True) for regulator in self.regulators.all()])

    @admin.display(
        description=_("Observer"),
        ordering="observers__translations__name",
    )
    def get_observers(self):
        return ", ".join([observer.safe_translation_getter("name", any_language=True) for observer in self.observers.all()])

    @admin.display(
        description=_("Roles"),
        ordering="groups__name",
    )
    def get_permissions_groups(self):
        return ", ".join([group.name for group in self.groups.all()])

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def get_sectors(self):
        sectors = Sector.objects.none()
        if governanceplatform.helpers.user_in_group(self, "RegulatorUser"):
            ru = RegulatorUser.objects.filter(user=self).first()
            sectors = ru.sectors
        elif governanceplatform.helpers.user_in_group(self, "RegulatorAdmin"):
            sectors = Sector.objects.all()
        return sectors

    def get_module_permissions(self):
        user_entity = None
        if governanceplatform.helpers.is_user_regulator(self):
            regulator_user = self.regulatoruser_set.first()
            if regulator_user:
                user_entity = regulator_user.regulator
        elif governanceplatform.helpers.is_observer_user(self):
            observer_user = self.observeruser_set.first()
            if observer_user:
                user_entity = observer_user.observer
        if user_entity:
            return list(user_entity.functionalities.values_list("type", flat=True))
        return []

    class Meta:
        verbose_name_plural = _("Users")
        verbose_name = _("User")
        permissions = (
            ("import_user", "Can import user"),
            ("export_user", "Can export user"),
        )


# Password User History
class PasswordUserHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hashed_password = models.CharField(max_length=128)
    timestamp = models.DateTimeField(auto_now_add=True)


class CompanyUser(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Operator"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )
    is_company_administrator = models.BooleanField(default=False, verbose_name=_("Is administrator"))

    approved = models.BooleanField(default=False, verbose_name=_("Approved"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="unique_CompanyUser"),
        ]
        verbose_name = _("Company User")
        verbose_name_plural = _("Company Users")

    def __str__(self):
        return ""

    def clean(self):
        is_incident_user = self.user.groups.filter(name="IncidentUser").exists()
        # manage the case of the creation of the company pk is none
        if self.company.pk is not None:
            has_admin = self.company.companyuser_set.filter(is_company_administrator=True).exists()
        else:
            has_admin = False

        if is_incident_user and self.is_company_administrator and not self.approved:
            raise ValidationError(_("Incident users can only become administrator after being approved."))

        if not has_admin and not self.is_company_administrator:
            raise ValidationError(_("The first user of an operator must be an administrator."))


# link between the admin regulator users and the regulators.
class RegulatorUser(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )
    regulator = models.ForeignKey(
        Regulator,
        on_delete=models.CASCADE,
        verbose_name=_("Regulator"),
    )
    is_regulator_administrator = models.BooleanField(default=False, verbose_name=_("Is administrator"))
    can_export_incidents = models.BooleanField(default=False, verbose_name=_("Can export incidents"))
    sectors = models.ManyToManyField(Sector, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "regulator"], name="unique_RegulatorUser"),
        ]
        verbose_name = _("Regulator user")
        verbose_name_plural = _("Regulator users")

    def __str__(self):
        return ""


# link between the admin observer users and the observer entity.
class ObserverUser(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )
    observer = models.ForeignKey(
        Observer,
        on_delete=models.CASCADE,
        verbose_name=_("Observer"),
    )
    is_observer_administrator = models.BooleanField(default=False, verbose_name=_("Is administrator"))
    can_export_incidents = models.BooleanField(default=False, verbose_name=_("Can export incidents"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "observer"], name="unique_ObserverUser"),
        ]
        verbose_name = _("Observer user")
        verbose_name_plural = _("Observer users")

    def __str__(self):
        return ""


# Different regulation like NIS etc.
class Regulation(TranslatableModel):
    translations = TranslatedFields(
        label=models.CharField(
            max_length=255,
            verbose_name=_("Label"),
        )
    )
    regulators = models.ManyToManyField(
        Regulator,
        default=None,
        blank=True,
        verbose_name=_("Regulators"),
    )

    @admin.display(description=_("Regulators"))
    def get_regulators(self):
        return [regulator.safe_translation_getter("name", any_language=True) for regulator in self.regulators.all()]

    def __str__(self):
        label_translation = self.safe_translation_getter("label", any_language=True)
        return label_translation or ""

    class Meta:
        verbose_name_plural = _("Regulations")
        verbose_name = _("Regulation")


# To categorize the operator, used for the observers to see or not the incident
class EntityCategory(TranslatableModel):
    translations = TranslatedFields(
        label=models.CharField(
            max_length=255,
            verbose_name=_("Label"),
        )
    )
    code = models.CharField(
        max_length=255,
        verbose_name=_("Code"),
    )

    def __str__(self):
        label_translation = self.safe_translation_getter("label", any_language=True)
        return label_translation or ""

    def get_safe_translation(self):
        return str(self)

    class Meta:
        verbose_name_plural = _("Entity categories")
        verbose_name = _("Entity category")


# link between the observers and the regulation
class ObserverRegulation(models.Model):
    regulation = models.ForeignKey(
        Regulation,
        on_delete=models.CASCADE,
        verbose_name=_("Legal basis"),
    )

    sectors = models.ManyToManyField(Sector, blank=True, verbose_name=_("Sectors"))
    observer = models.ForeignKey(
        Observer,
        on_delete=models.CASCADE,
        verbose_name=_("Observer"),
    )
    incident_rule = models.JSONField(
        verbose_name=_("Incident rules"),
        null=True,
        blank=True,
        default=dict,
    )

    def save(self, *args, **kwargs):
        if self.incident_rule is None or self.incident_rule == "":
            self.incident_rule = {}
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["regulation", "observer"], name="unique_Observerregulation"),
        ]
        verbose_name = _("Observer regulation")
        verbose_name_plural = _("Observer regulations")

    def __str__(self):
        return ""


# class to record the script logs
class ScriptLogEntry(models.Model):
    action_time = models.DateTimeField(auto_now=True, verbose_name=_("Timestamp"))
    action_flag = models.PositiveSmallIntegerField(verbose_name=_("Activity"))
    object_id = models.TextField(null=True, blank=True, verbose_name=_("Object id"))
    object_repr = models.CharField(max_length=200, verbose_name=_("Object representation"))
    additional_info = models.TextField(null=True, blank=True, verbose_name=_("Additional information"))

    class Meta:
        verbose_name = _("Script execution logs")
        verbose_name_plural = _("Script execution logs")

    def __str__(self):
        return f"{self.action()} - {self.object_repr}"

    # Define a method to return human-readable action names
    def action(self):
        return ACTION_FLAG_CHOICES.get(self.action_flag, "Unknown")


class UserSession(AbstractBaseSession):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    @classmethod
    def get_session_store_class(cls):
        return importlib.import_module("governanceplatform.sessions").SessionStore

    class Meta:
        verbose_name = _("User session")
        verbose_name_plural = _("User sessions")
