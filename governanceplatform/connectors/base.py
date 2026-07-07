from dataclasses import dataclass
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _


@dataclass
class NotificationContext:
    incident: Any
    subject: str
    content_html: str
    # external reference of a previous successful delivery for the same
    # (incident, connector) pair — lets connectors update instead of create
    previous_external_ref: str = ""


@dataclass
class DeliveryResult:
    success: bool
    external_ref: str = ""
    message: str = ""


class TransientDeliveryError(Exception):
    """Delivery failed for a reason worth retrying (network error, 5xx)."""


class PermanentDeliveryError(Exception):
    """Delivery failed for a reason a retry cannot fix (bad config, 4xx)."""


class BaseConnector:
    type_id: str
    label: str
    config_form: type[forms.Form]
    requires_secret: bool = False
    secret_label = _("Secret")

    def __init__(self, connector):
        self.connector = connector

    def validate_config(self, config: dict) -> dict:
        form = self.config_form(data=config)
        if not form.is_valid():
            raise forms.ValidationError([f"{name}: {'; '.join(errors)}" for name, errors in form.errors.items()])
        return form.cleaned_data

    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        raise NotImplementedError
