from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IncidentsConfig(AppConfig):
    name = "incidents"
    verbose_name = _("Incident notification")

    def ready(self):
        from . import signals  # noqa: F401
