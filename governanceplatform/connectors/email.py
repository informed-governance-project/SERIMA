import json
import re
import tempfile
import time
from contextlib import contextmanager
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import gnupg
from django import forms
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _

from .base import (
    BaseConnector,
    DeliveryResult,
    NotificationContext,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from .payload import build_incident_payload
from .registry import register


class EmailListField(forms.CharField):
    def prepare_value(self, value):
        if isinstance(value, list):
            return ", ".join(value)
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return []
        if isinstance(value, list):
            items = value
        else:
            items = [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]
        for item in items:
            validate_email(item)
        return items


@contextmanager
def _ephemeral_gpg(armored_key: str):
    # throwaway GNUPGHOME so no keyring state persists on workers
    with tempfile.TemporaryDirectory() as home:
        gpg = gnupg.GPG(gnupghome=home)
        import_result = gpg.import_keys(armored_key)
        yield gpg, import_result


def get_public_key_info(armored_key: str) -> tuple[str, int | None]:
    """Validate an ASCII-armored public key; return (fingerprint, expires unix ts or None)."""
    with _ephemeral_gpg(armored_key) as (gpg, import_result):
        fingerprints = {fp for fp in import_result.fingerprints if fp}
        if len(fingerprints) != 1:
            raise forms.ValidationError(_("Provide exactly one valid ASCII-armored GPG public key"))
        key = gpg.list_keys()[0]
        expires = int(key["expires"]) if key.get("expires") else None
        if expires and expires <= time.time():
            raise forms.ValidationError(_("The GPG public key is expired"))
        return key["fingerprint"], expires


def encrypt_pgp_mime(armored_key: str, content_html: str, attachments: list[tuple[str, str | bytes, str]]) -> str:
    """Encrypt an HTML body plus attachments into a single ASCII-armored PGP message (RFC 3156 inner part)."""
    inner = MIMEText(content_html, "html", "utf-8")
    if attachments:
        mixed = MIMEMultipart("mixed")
        mixed.attach(inner)
        for filename, content, mimetype in attachments:
            subtype = mimetype.partition("/")[2] or "octet-stream"
            part = MIMEApplication(content.encode() if isinstance(content, str) else content, _subtype=subtype)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            mixed.attach(part)
        inner = mixed

    with _ephemeral_gpg(armored_key) as (gpg, import_result):
        fingerprints = {fp for fp in import_result.fingerprints if fp}
        if len(fingerprints) != 1:
            raise PermanentDeliveryError("Invalid GPG public key")
        encrypted = gpg.encrypt(inner.as_bytes(), fingerprints.pop(), always_trust=True, armor=True)
        if not encrypted.ok:
            raise PermanentDeliveryError(f"GPG encryption failed: {encrypted.status}")
        return str(encrypted)


class EmailConfigForm(forms.Form):
    send_to_observer_email = forms.BooleanField(label=_("Send to the observer notification e-mail address"), required=False, initial=True)
    send_to_observer_users = forms.BooleanField(label=_("Send to the observer users"), required=False, initial=True)
    additional_recipients = EmailListField(
        label=_("Additional recipients"),
        required=False,
        help_text=_("Comma-separated e-mail addresses"),
    )
    attach_incident_json = forms.BooleanField(label=_("Attach the incident data as a JSON file"), required=False, initial=False)
    gpg_public_key = forms.CharField(
        label=_("GPG public key"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("ASCII-armored public key. When set, notifications are sent GPG-encrypted (PGP/MIME) — never in plaintext."),
    )

    def clean_gpg_public_key(self):
        armored_key = self.cleaned_data.get("gpg_public_key", "").strip()
        if armored_key:
            get_public_key_info(armored_key)
        return armored_key


@register
class EmailConnector(BaseConnector):
    type_id = "email"
    label = _("Email")
    config_form = EmailConfigForm

    def _resolve_recipients(self) -> list[str]:
        from incidents.email import get_emails_from_qs, is_valid_email

        config = self.connector.config
        observer = self.connector.observer
        recipients = []
        if config.get("send_to_observer_email") and observer.email_for_notification:
            recipients.append(observer.email_for_notification)
        if config.get("send_to_observer_users"):
            recipients.extend(get_emails_from_qs(observer.observeruser_set.all().select_related("user")))
        recipients.extend(config.get("additional_recipients") or [])
        return list(dict.fromkeys(recipient for recipient in recipients if recipient and is_valid_email(recipient)))

    def _deliver(self, subject, content_html, recipients, attachments):
        from incidents.email import send_html_email, send_pgp_mime_email

        armored_key = self.connector.config.get("gpg_public_key")
        if armored_key:
            # fail-closed: any encryption error aborts the delivery, plaintext is never sent
            armored_message = encrypt_pgp_mime(armored_key, content_html, attachments)
            sent = send_pgp_mime_email(subject, armored_message, recipients)
        else:
            sent = send_html_email(subject, content_html, recipients, attachments=attachments or None)

        if not sent:
            raise TransientDeliveryError("Email sending failed")

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        recipients = self._resolve_recipients()
        if not recipients:
            raise PermanentDeliveryError("No valid recipients configured")

        attachments = []
        if self.connector.config.get("attach_incident_json"):
            payload = build_incident_payload(ctx.incident, ctx.subject, ctx.content_html)
            attachments.append((f"incident_{ctx.incident.pk}.json", json.dumps(payload, indent=2), "application/json"))

        self._deliver(ctx.subject, ctx.content_html, recipients, attachments)
        return DeliveryResult(success=True)

    def test_connection(self) -> tuple[bool, str]:
        recipients = self._resolve_recipients()
        if not recipients:
            return False, str(_("No valid recipients configured"))

        fingerprint = expires = None
        armored_key = self.connector.config.get("gpg_public_key")
        if armored_key:
            try:
                fingerprint, expires = get_public_key_info(armored_key)
            except forms.ValidationError as e:
                return False, "; ".join(e.messages)

        subject = str(_("[TEST] SERIMA notification connector"))
        content_html = str(_("<p>This is a test message confirming your SERIMA notification connector is configured correctly.</p>"))
        try:
            self._deliver(subject, content_html, recipients, attachments=[])
        except (TransientDeliveryError, PermanentDeliveryError) as e:
            return False, str(e)

        message = str(_("Test e-mail sent to: %s")) % ", ".join(recipients)
        if fingerprint:
            message += f" — GPG key {fingerprint}"
            if expires:
                message += time.strftime(" (expires %Y-%m-%d)", time.gmtime(expires))
        return True, message
