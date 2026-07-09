import json
import tempfile
import time
from contextlib import contextmanager

import gnupg
from django import forms
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


def encrypt_bytes(armored_key: str, data: bytes) -> str:
    """Encrypt data to the given public key; return the ASCII-armored ciphertext."""
    with _ephemeral_gpg(armored_key) as (gpg, import_result):
        fingerprints = {fp for fp in import_result.fingerprints if fp}
        if len(fingerprints) != 1:
            raise PermanentDeliveryError(str(_("Invalid GPG public key")))
        encrypted = gpg.encrypt(data, fingerprints.pop(), always_trust=True, armor=True)
        if not encrypted.ok:
            raise PermanentDeliveryError(str(_("GPG encryption failed: %s")) % encrypted.status)
        return str(encrypted)


class GPGJsonConfigForm(forms.Form):
    gpg_public_key = forms.CharField(
        label=_("GPG public key"),
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("ASCII-armored public key used to encrypt the incident JSON payload."),
    )

    def clean_gpg_public_key(self):
        armored_key = self.cleaned_data["gpg_public_key"].strip()
        get_public_key_info(armored_key)
        return armored_key


@register
class GPGJsonConnector(BaseConnector):
    type_id = "gpg_json"
    label = _("GPG-encrypted JSON (e-mail)")
    config_form = GPGJsonConfigForm

    def _recipient(self) -> str:
        # the encrypted payload goes to the observer's notification address only —
        # never observer users, never additional recipients
        from incidents.email import is_valid_email

        recipient = self.connector.observer.email_for_notification
        if not recipient or not is_valid_email(recipient):
            raise PermanentDeliveryError(str(_("The observer has no valid notification e-mail address")))
        return recipient

    def _send_encrypted(self, filename: str, payload: dict, subject: str, content: str, recipient: str) -> None:
        from incidents.email import send_html_email

        data = json.dumps(payload, indent=2, ensure_ascii=False).encode()
        # fail-closed: any encryption error aborts the delivery, plaintext is never sent
        armored = encrypt_bytes(self.connector.config.get("gpg_public_key", ""), data)

        # neutral envelope: no incident data outside the ciphertext
        sent = send_html_email(subject, content, [recipient], attachments=[(filename, armored, "application/pgp-encrypted")])
        if not sent:
            raise TransientDeliveryError(str(_("Email sending failed")))

    def send(self, ctx: NotificationContext) -> DeliveryResult:
        recipient = self._recipient()
        payload = build_incident_payload(ctx.incident)
        subject = ctx.subject
        content = ctx.content_html
        self._send_encrypted(f"incident_{ctx.incident.pk}.json.gpg", payload, subject, content, recipient)
        return DeliveryResult(success=True)

    def test_connection(self) -> tuple[bool, str]:
        try:
            recipient = self._recipient()
        except PermanentDeliveryError as e:
            return False, str(e)

        try:
            fingerprint, expires = get_public_key_info(self.connector.config.get("gpg_public_key", ""))
        except forms.ValidationError as e:
            return False, "; ".join(e.messages)

        try:
            self._send_encrypted("test.json.gpg", {"event": "ping"}, recipient)
        except (TransientDeliveryError, PermanentDeliveryError) as e:
            return False, str(e)

        message = str(_("Encrypted test payload sent to %s")) % recipient
        message += f" — GPG key {fingerprint}"
        if expires:
            message += time.strftime(" (expires %Y-%m-%d)", time.gmtime(expires))
        return True, message
