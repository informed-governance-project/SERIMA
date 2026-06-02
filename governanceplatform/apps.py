from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class GovernancePlatformConfig(AppConfig):
    name = "governanceplatform"
    verbose_name = _("Governance")

    def ready(self):
        import logging

        from . import signals  # noqa: F401

        # Increasing weasyprint.process log level before weasyprint init
        logging.getLogger("weasyprint.progress").setLevel(logging.ERROR)
