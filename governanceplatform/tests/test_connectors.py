import email as email_lib
import hashlib
import hmac
import json

import gnupg
import pytest
import responses
from django import forms
from django.core import mail
from django.test import override_settings

from governanceplatform.connectors import (
    NotificationContext,
    PermanentDeliveryError,
    connector_type_choices,
    get_connector_class,
)
from governanceplatform.connectors.email import (
    EmailListField,
    encrypt_pgp_mime,
    get_public_key_info,
)
from governanceplatform.models import ObserverConnector


@pytest.fixture(scope="session")
def gpg_keypair(tmp_path_factory):
    home = tmp_path_factory.mktemp("gnupg")
    gpg = gnupg.GPG(gnupghome=str(home))
    key_input = gpg.gen_key_input(
        key_type="EDDSA",
        key_curve="ed25519",
        subkey_type="ECDH",
        subkey_curve="cv25519",
        name_email="cert1@cert1.lu",
        no_protection=True,
    )
    key = gpg.gen_key(key_input)
    assert key.fingerprint, "test GPG key generation failed"
    return gpg, gpg.export_keys(key.fingerprint)


def test_registry_contains_builtin_connectors():
    assert {type_id for type_id, _label in connector_type_choices()} == {"rt", "email", "webhook"}
    for type_id in ("rt", "email", "webhook"):
        assert get_connector_class(type_id).type_id == type_id


@pytest.mark.django_db
def test_connector_secret_is_encrypted_at_rest(populate_db):
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(observer=observer, connector_type="rt", name="RT", config={})
    connector.secret = "s3cret-token"
    connector.save()

    connector.refresh_from_db()
    assert connector._secret != "s3cret-token"
    assert connector.secret == "s3cret-token"

    connector.secret = None
    assert connector._secret is None
    assert connector.secret == ""


@override_settings(DEBUG=False)
def test_rt_config_form_rejects_http_url():
    form = get_connector_class("rt").config_form(data={"url": "http://rt.example.com", "queue": "incidents"})
    assert not form.is_valid()
    assert "url" in form.errors


@override_settings(DEBUG=False)
def test_rt_config_form_rejects_internal_address():
    form = get_connector_class("rt").config_form(data={"url": "https://127.0.0.1", "queue": "incidents"})
    assert not form.is_valid()
    assert "url" in form.errors


def test_email_list_field_parses_and_validates():
    field = EmailListField(required=False)
    assert field.clean("a@example.com, b@example.com") == ["a@example.com", "b@example.com"]
    assert field.clean(["a@example.com"]) == ["a@example.com"]
    assert field.clean("") == []
    with pytest.raises(forms.ValidationError):
        field.clean("not-an-email")


def test_gpg_public_key_validation(gpg_keypair):
    _gpg, public_key = gpg_keypair
    fingerprint, expires = get_public_key_info(public_key)
    assert len(fingerprint) == 40
    assert expires is None

    with pytest.raises(forms.ValidationError):
        get_public_key_info("not an armored key")


def test_pgp_mime_encryption_roundtrip(gpg_keypair):
    gpg, public_key = gpg_keypair
    attachments = [("incident_1.json", json.dumps({"incident": 1}), "application/json")]
    armored = encrypt_pgp_mime(public_key, "<p>Confidential</p>", attachments)
    assert armored.startswith("-----BEGIN PGP MESSAGE-----")

    decrypted = gpg.decrypt(armored)
    assert decrypted.ok
    inner = email_lib.message_from_bytes(decrypted.data)
    parts = {part.get_content_type(): part for part in inner.walk()}
    assert "<p>Confidential</p>" in parts["text/html"].get_payload(decode=True).decode()
    assert json.loads(parts["application/json"].get_payload(decode=True)) == {"incident": 1}


@pytest.mark.django_db
def test_email_connector_sends_encrypted_never_plaintext(populate_db, gpg_keypair):
    gpg, public_key = gpg_keypair
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={
            "send_to_observer_email": True,
            "send_to_observer_users": False,
            "additional_recipients": [],
            "attach_incident_json": False,
            "gpg_public_key": public_key,
        },
    )

    ctx = NotificationContext(incident=None, subject="Incident", content_html="<p>Secret content</p>")
    result = connector.get_impl().send(ctx)

    assert result.success
    assert len(mail.outbox) == 1
    message = mail.outbox[0].message()
    assert message.get_content_type() == "multipart/encrypted"
    assert message.get_param("protocol") == "application/pgp-encrypted"
    assert "Secret content" not in message.as_string()

    encrypted_part = next(part for part in message.walk() if part.get_content_type() == "application/octet-stream")
    decrypted = gpg.decrypt(encrypted_part.get_payload(decode=True))
    assert decrypted.ok
    inner = email_lib.message_from_bytes(decrypted.data)
    assert inner.get_content_type() == "text/html"
    assert "Secret content" in inner.get_payload(decode=True).decode()


@pytest.mark.django_db
def test_email_connector_gpg_fail_closed(populate_db):
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={"send_to_observer_email": True, "gpg_public_key": "garbage, not a key"},
    )

    ctx = NotificationContext(incident=None, subject="Incident", content_html="<p>Secret content</p>")
    with pytest.raises(PermanentDeliveryError):
        connector.get_impl().send(ctx)

    assert mail.outbox == []


@pytest.mark.django_db
def test_email_test_connection_sends_test_mail(populate_db):
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={"send_to_observer_email": True, "send_to_observer_users": False, "additional_recipients": []},
    )

    ok, message = connector.get_impl().test_connection()

    assert ok
    assert observer.email_for_notification in message
    assert len(mail.outbox) == 1
    assert mail.outbox[0].bcc == [observer.email_for_notification]
    assert "test message" in mail.outbox[0].body


@pytest.mark.django_db
def test_email_test_connection_encrypts_when_gpg_configured(populate_db, gpg_keypair):
    _gpg, public_key = gpg_keypair
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={"send_to_observer_email": True, "gpg_public_key": public_key},
    )

    ok, message = connector.get_impl().test_connection()

    assert ok
    assert len(mail.outbox) == 1
    assert mail.outbox[0].message().get_content_type() == "multipart/encrypted"


@pytest.mark.django_db
def test_email_test_connection_fails_without_recipients(populate_db):
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={"send_to_observer_email": False, "send_to_observer_users": False, "additional_recipients": []},
    )

    ok, _message = connector.get_impl().test_connection()

    assert not ok
    assert mail.outbox == []


@pytest.mark.django_db
@responses.activate
def test_rt_test_connection_creates_test_ticket(populate_db, monkeypatch):
    monkeypatch.setattr("governanceplatform.validators.socket.gethostbyname", lambda hostname: "93.184.216.34")
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="rt",
        name="RT",
        config={"url": "https://rt.example.com", "queue": "incidents"},
    )
    connector.secret = "rt-token"
    connector.save()
    responses.add(responses.POST, "https://rt.example.com/REST/2.0/ticket", json={"id": 7}, status=201)

    ok, message = connector.get_impl().test_connection()

    assert ok
    assert "7" in message
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "https://rt.example.com/REST/2.0/ticket"


@pytest.mark.django_db
@responses.activate
def test_rt_surfaces_api_message_on_403(populate_db, monkeypatch):
    monkeypatch.setattr("governanceplatform.validators.socket.gethostbyname", lambda hostname: "93.184.216.34")
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="rt",
        name="RT",
        config={"url": "https://rt.example.com", "queue": "incident"},
    )
    connector.secret = "rt-token"
    connector.save()
    responses.add(
        responses.POST,
        "https://rt.example.com/REST/2.0/ticket",
        json={"message": "No permission to create tickets in the queue 'incident'"},
        status=403,
    )

    ok, message = connector.get_impl().test_connection()

    assert not ok
    assert "403" in message
    assert "No permission to create tickets in the queue 'incident'" in message


@pytest.mark.django_db
@responses.activate
def test_webhook_hmac_signature(populate_db, monkeypatch):
    monkeypatch.setattr("governanceplatform.validators.socket.gethostbyname", lambda hostname: "93.184.216.34")
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="webhook",
        name="Hook",
        config={"url": "https://hooks.example.com/serima"},
    )
    connector.secret = "hmac-secret"
    connector.save()
    responses.add(responses.POST, "https://hooks.example.com/serima", json={}, status=200)

    ok, _message = connector.get_impl().test_connection()

    assert ok
    request = responses.calls[0].request
    timestamp = request.headers["X-Serima-Timestamp"]
    expected = hmac.new(b"hmac-secret", f"{timestamp}.".encode() + request.body, hashlib.sha256).hexdigest()
    assert request.headers["X-Serima-Signature"] == f"sha256={expected}"
    assert json.loads(request.body) == {"event": "ping"}
