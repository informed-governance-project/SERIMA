import logging
from urllib.parse import quote, urlparse

import requests
from django import forms
from django.conf import settings
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
from .registry import register

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10


class RTConfigForm(forms.Form):
    url = forms.URLField(
        label=_("URL"),
        help_text="e.g., https://rt.example.com",
        validators=[URLValidator(), validate_external_https_url],
        assume_scheme="https",
    )
    queue = forms.CharField(label=_("Queue"), max_length=255)


@register
class RTConnector(BaseConnector):
    type_id = "rt"
    label = _("RT (Request Tracker)")
    config_form = RTConfigForm
    requires_secret = True
    secret_label = _("Token")

    def _base_url(self):
        return self.connector.config["url"].rstrip("/")

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"token {self.connector.secret}",
        }

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        base_url = self._base_url()
        try:
            validate_external_https_url(base_url)
        except ValidationError:
            raise PermanentDeliveryError(f"Blocked unsafe RT URL: {base_url}")

        if ctx.previous_external_ref:
            url = f"{base_url}/REST/2.0/ticket/{ctx.previous_external_ref}/correspond"
            payload = {
                "Content": ctx.content_html,
                "ContentType": "text/html",
            }
        else:
            url = f"{base_url}/REST/2.0/ticket"
            payload = {
                "Requestor": settings.EMAIL_SENDER,
                "Queue": self.connector.config["queue"],
                "Subject": ctx.subject,
                "Content": ctx.content_html,
                "ContentType": "text/html",
            }

        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise TransientDeliveryError(f"Error connecting to RT API: {e}")

        if response.ok:
            external_ref = ctx.previous_external_ref
            if not ctx.previous_external_ref and response.status_code == 201:
                external_ref = str(response.json().get("id", ""))
            return DeliveryResult(success=True, external_ref=external_ref)

        error = f"RT API error {response.status_code}: {response.text[:500]}"
        if response.status_code >= 500:
            raise TransientDeliveryError(error)
        raise PermanentDeliveryError(error)

    def test_connection(self) -> tuple[bool, str]:
        config = self.connector.config
        if not config.get("url") or not config.get("queue") or not self.connector.secret:
            return False, str(_("RT configuration is incomplete"))

        parsed = urlparse(config["url"])
        encoded_queue = quote(config["queue"], safe="")
        url = f"{parsed.scheme}://{parsed.netloc}/REST/2.0/queue/{encoded_queue}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            logger.error("Error connecting to RT API: %s", e)
            return False, str(_("Error connecting to RT API"))

        if response.status_code == 200:
            return True, str(_("Connection successful"))
        if response.status_code == 401:
            return False, str(_("RT token unauthorized (401)"))
        if response.status_code == 404:
            return False, str(_("RT queue not found (404)"))
        return False, f"Unexpected RT response ({response.status_code})"
