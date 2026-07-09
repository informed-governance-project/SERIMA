import hashlib
import hmac
import json
import logging
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

logger = logging.getLogger(__name__)

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
        url = self.connector.config.get("url", "")
        try:
            validate_external_https_url(url)
        except ValidationError:
            raise PermanentDeliveryError(str(_("The webhook URL is not allowed")))

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
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
            logger.error("Error connecting to webhook: %s", e)
            raise TransientDeliveryError(str(_("Error connecting to the webhook endpoint")))

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        payload = build_incident_payload(ctx.incident)
        response = self._post_signed(payload)

        if response.ok:
            return DeliveryResult(success=True)

        logger.error("Webhook error %s: %s", response.status_code, response.text)
        if response.status_code >= 500:
            raise TransientDeliveryError(str(_("Webhook server error (%s)")) % response.status_code)
        raise PermanentDeliveryError(str(_("The webhook endpoint returned an error (%s)")) % response.status_code)

    def test_connection(self) -> tuple[bool, str]:
        if not self.connector.config.get("url") or not self.connector.secret:
            return False, str(_("Webhook configuration is incomplete"))

        try:
            response = self._post_signed({"event": "ping"})
        except (TransientDeliveryError, PermanentDeliveryError) as e:
            return False, str(e)

        if response.ok:
            return True, str(_("Connection successful"))
        logger.error("Webhook error %s: %s", response.status_code, response.text)
        return False, str(_("The webhook endpoint returned an error (%s)")) % response.status_code
