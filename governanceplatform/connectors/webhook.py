import hashlib
import hmac
import json
import time

import requests
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from governanceplatform.validators import validate_external_https_url

from .base import (
    BaseConnector,
    DeliveryResult,
    NotificationContext,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from .payload import build_incident_payload
from .registry import register

REQUEST_TIMEOUT = 10


class WebhookConfigForm(forms.Form):
    url = forms.URLField(
        label=_("URL"),
        validators=[URLValidator(), validate_external_https_url],
        assume_scheme="https",
    )


@register
class WebhookConnector(BaseConnector):
    type_id = "webhook"
    label = _("Webhook (HTTPS API)")
    config_form = WebhookConfigForm
    requires_secret = True
    secret_label = _("HMAC secret")

    def _post_signed(self, payload: dict):
        url = self.connector.config["url"]
        try:
            validate_external_https_url(url)
        except ValidationError:
            raise PermanentDeliveryError(f"Blocked unsafe webhook URL: {url}")

        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.connector.secret.encode(),
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Serima-Timestamp": timestamp,
            "X-Serima-Signature": f"sha256={signature}",
        }

        try:
            return requests.post(url, data=body, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise TransientDeliveryError(f"Error connecting to webhook: {e}")

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        payload = build_incident_payload(ctx.incident, ctx.subject, ctx.content_html)
        response = self._post_signed(payload)

        if response.ok:
            return DeliveryResult(success=True)

        error = f"Webhook error {response.status_code}: {response.text[:500]}"
        if response.status_code >= 500:
            raise TransientDeliveryError(error)
        raise PermanentDeliveryError(error)

    def test_connection(self) -> tuple[bool, str]:
        if not self.connector.config.get("url") or not self.connector.secret:
            return False, str(_("Webhook configuration is incomplete"))

        try:
            response = self._post_signed({"event": "ping"})
        except (TransientDeliveryError, PermanentDeliveryError) as e:
            return False, str(e)

        if response.ok:
            return True, str(_("Connection successful"))
        return False, f"Webhook error {response.status_code}"
