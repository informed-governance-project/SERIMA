import logging
import secrets
import string

from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.template import loader
from django.utils.translation import get_language_info
from django.utils.translation import gettext_lazy as _
from parler.forms import TranslatableModelForm

from .connectors.registry import connector_type_choices
from .email import Base64EmailMultiAlternatives
from .models import Observer, ObserverConnector

User = get_user_model()
logger = logging.getLogger("django.contrib.auth")


class CustomUserChangeForm(UserChangeForm):
    password = None

    first_name = forms.CharField(
        label=_("First name"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label=_("Last name"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    phone_number = forms.CharField(
        label=_("Phone number"),
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "tel"}),
    )
    email = forms.CharField(
        label=_("Email address"),
        disabled=True,
        required=True,
        widget=forms.EmailInput(attrs={"readonly": "readonly"}),
    )

    role = forms.CharField(
        label=_("Role"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "role")
        widgets = {
            "email": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        group_names = [group.name for group in self.instance.groups.all()]

        if not group_names:
            del self.fields["role"]
        else:
            role = ", ".join(group_names)
            self.fields["role"].initial = role

    def clean(self):
        cleaned_data = super().clean()

        # Validate readonly fields
        self.validate_readonly_fields(cleaned_data)

        # Validate groups
        self.validate_groups(cleaned_data)

        return cleaned_data

    def validate_readonly_fields(self, cleaned_data):
        readonly_fields = ["email"]
        for field_name in readonly_fields:
            old_value = getattr(self.instance, field_name)
            new_value = cleaned_data.get(field_name)

            if new_value and new_value != old_value:
                raise forms.ValidationError(f"{field_name.capitalize()} cannot be modified.")

    def validate_groups(self, cleaned_data):
        actual_group_names = {group.name for group in self.instance.groups.all()}
        form_group_names = set(cleaned_data.get("role", "").split(", "))
        if form_group_names != actual_group_names:
            raise forms.ValidationError("Groups cannot be modified.")


class SelectCompany(forms.Form):
    select_company = forms.ModelChoiceField(queryset=None, required=True, label="Company")

    def __init__(self, *args, **kwargs):
        companies = kwargs.pop("companies")
        super().__init__(*args, **kwargs)

        self.fields["select_company"].queryset = companies.order_by("name")


class CustomPasswordResetForm(PasswordResetForm):
    captcha = CaptchaField()
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    honeypot_name = ""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        require_captcha = kwargs.pop("require_captcha", True)
        super().__init__(*args, **kwargs)

        # The captcha proves a human triggered the request. When the reset email
        # is dispatched internally (e.g. right after registration) that has
        # already been verified, so skip it — the captcha is single-use and
        # cannot be re-validated here anyway.
        if not require_captcha:
            del self.fields["captcha"]

        if self.request:
            # get the name of the field
            name = self.request.session.get("honeypot_field_name")

            # if there is no name create a new one
            if not name:
                name = f"field_{secrets.token_hex(4)}"
                self.request.session["honeypot_field_name"] = name

            self.honeypot_name = name

            self.fields[name] = forms.CharField(
                required=False,
                widget=forms.TextInput(),
            )

    def clean(self):
        cleaned_data = super().clean()

        value = cleaned_data.get(self.honeypot_name)

        if value:
            raise forms.ValidationError("Invalid submission.")

        return cleaned_data

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        """
        Send a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = Base64EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        try:
            email_message.send()
        except Exception:
            logger.exception("Failed to send password reset email to %s", context["user"].pk)


class RegistrationForm(forms.ModelForm):
    captcha = CaptchaField()
    accept_terms = forms.BooleanField(
        label=_("I acknowledge and agree to the"),
        error_messages={"required": _("Accepting the Terms of Use is required for registration.")},
    )
    email = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "email"}))
    first_name = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "given-name", "title": _("First name")}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "family-name", "title": _("Last name")}))
    field_order = (
        "email",
        "last_name",
        "first_name",
        "accept_terms",
        "captcha",
    )
    honeypot_name = ""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if self.request:
            # get the name of the field
            name = self.request.session.get("honeypot_field_name")

            # if there is no name create a new one
            if not name:
                name = f"field_{secrets.token_hex(4)}"
                self.request.session["honeypot_field_name"] = name

            self.honeypot_name = name

            self.fields[name] = forms.CharField(
                required=False,
                widget=forms.TextInput(),
            )

    @staticmethod
    def generate_temporary_password(length=24):
        chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(chars) for _ in range(length))

    def save(self, commit=True):
        user = super().save(commit=False)
        temp_password = self.generate_temporary_password()
        user.set_password(temp_password)
        user.email_verified = False
        if commit:
            user.save()
        return user

    def clean(self):
        cleaned_data = super().clean()

        value = cleaned_data.get(self.honeypot_name)

        if value:
            raise forms.ValidationError("Invalid submission.")

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get("email").lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("There is an issue, please verify your e-mail"))
        return email

    class Meta:
        model = User
        fields = (
            "email",
            "last_name",
            "first_name",
            "accept_terms",
        )


class CustomTranslatableAdminForm(TranslatableModelForm):
    FALLBACK_LANGUAGE = settings.PARLER_DEFAULT_LANGUAGE_CODE

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and self.FALLBACK_LANGUAGE not in self.data:
            if not self.instance.has_translation(self.FALLBACK_LANGUAGE):
                self.add_default_translation_error()
        elif self.FALLBACK_LANGUAGE not in self.data:
            self.add_default_translation_error()

        self.check_translation_duplication_entry()

        return cleaned_data

    def add_default_translation_error(self):
        language_info = get_language_info(self.FALLBACK_LANGUAGE)
        fallback_language_name = language_info["name_translated"]
        error_message = _("Default language translation (%(fallback_language_name)s) is missing. Please add it before saving.")
        self.add_error(
            None,
            ValidationError(error_message, params={"fallback_language_name": fallback_language_name}),
        )

    def check_translation_duplication_entry(self):
        forms_to_check = ["QuestionCategoryForm"]
        if self.__class__.__name__ not in forms_to_check:
            return

        model = self._meta.model._parler_meta.root_model
        current_language = self.instance.get_current_language()
        duplicate_translations = model.objects.filter(**self.cleaned_data, language_code=current_language)

        if duplicate_translations.exists():
            error_message = _("This %(model)s already exists.") % {"model": self.instance._meta.verbose_name.lower()}
            self.add_error(
                None,
                ValidationError(error_message),
            )


class TermsAcceptanceForm(forms.Form):
    accept = forms.BooleanField(label=_("I acknowledge and agree to the"))


class ContactForm(forms.Form):
    firstname = forms.CharField(max_length=150, required=True)
    lastname = forms.CharField(max_length=150, required=True)
    phone = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(max_length=254, required=True, disabled=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    terms_accepted = forms.BooleanField(
        label=_("I agree that my personal data may be used for communication purposes."),
        required=True,
        error_messages={"required": "You must accept the use of your personal data."},
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["firstname"].initial = user.first_name
            self.fields["lastname"].initial = user.last_name
            self.fields["email"].initial = user.email
            self.fields["email"].disabled = True
            self.fields["phone"].initial = user.phone_number


class ObserverAdminForm(CustomTranslatableAdminForm):
    allowed_connector_types = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Available connectors"),
        help_text=_("Connector types this observer is allowed to use."),
    )

    class Meta:
        model = Observer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_connector_types"].choices = connector_type_choices()


class ObserverConnectorAdminForm(forms.ModelForm):
    class Meta:
        model = ObserverConnector
        fields = ["observer", "connector_type", "name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance if self.instance and self.instance.pk else None
        if not instance:
            return

        for field_name in self.fields:
            if field_name.startswith("config__"):
                config_key = field_name.removeprefix("config__")
                self.initial[field_name] = instance.config.get(config_key, self.fields[field_name].initial)

        if "secret" in self.fields and instance.secret:
            self.fields["secret"].widget = forms.TextInput(attrs={"type": "password", "class": "vTextField"})
            self.fields["secret"].help_text = _(
                "A secret is already set. To remove it, clear the field and save. To update it, enter a new one."
            )
            self.initial["secret"] = "*" * len(instance.secret)

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk:
            self.instance.config = {
                name.removeprefix("config__"): value for name, value in cleaned_data.items() if name.startswith("config__")
            }
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "secret" in self.fields:
            val = self.cleaned_data.get("secret")
            if val:
                if set(val) != {"*"}:
                    obj.secret = val  # use the encrypting setter
            else:
                obj.secret = None
        if commit:
            obj.save()
        return obj
