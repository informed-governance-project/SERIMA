from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SelfRegistrationConfig(AppConfig):
    name = "selfregistration"
    verbose_name = _("Self-registration")
