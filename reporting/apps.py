from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReportingConfig(AppConfig):
    name = "reporting"
    verbose_name = _("Reporting")

    def ready(self):
        from . import signals  # noqa: F401
