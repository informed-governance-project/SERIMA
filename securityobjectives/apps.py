from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecurityobjectivesConfig(AppConfig):
    name = "securityobjectives"
    verbose_name = _("Security objectives")

    def ready(self):
        from . import signals  # noqa: F401
