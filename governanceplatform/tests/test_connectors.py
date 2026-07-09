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
    PermanentDeliveryError,
    connector_type_choices,
    get_connector_class,
)
from governanceplatform.connectors.gpg_json import get_public_key_info
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
    assert {type_id for type_id, _label in connector_type_choices()} == {"rt", "webhook", "gpg_json"}
    for type_id in ("rt", "webhook", "gpg_json"):
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


def test_gpg_public_key_validation(gpg_keypair):
    _gpg, public_key = gpg_keypair
    fingerprint, expires = get_public_key_info(public_key)
    assert len(fingerprint) == 40
    assert expires is None

    with pytest.raises(forms.ValidationError):
        get_public_key_info("not an armored key")


def test_gpg_json_config_form_requires_valid_key(gpg_keypair):
    _gpg, public_key = gpg_keypair
    config_form = get_connector_class("gpg_json").config_form

    assert not config_form(data={}).is_valid()
    assert not config_form(data={"gpg_public_key": "garbage"}).is_valid()
    assert config_form(data={"gpg_public_key": public_key}).is_valid()


@pytest.mark.django_db
def test_gpg_json_test_connection_sends_encrypted_payload_to_observer_only(populate_db, gpg_keypair):
    gpg, public_key = gpg_keypair
    observer = populate_db["observers"][0]
    assert observer.observeruser_set.exists(), "fixture must provide observer users to prove they are excluded"
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="gpg_json",
        name="GPG JSON",
        config={"gpg_public_key": public_key},
    )

    ok, message = connector.get_impl().test_connection()

    assert ok
    assert observer.email_for_notification in message
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    # recipient isolation: only the observer's notification address, never its users
    assert sent.bcc == [observer.email_for_notification]
    user_emails = [ou.user.email for ou in observer.observeruser_set.all()]
    raw_message = sent.message().as_string()
    for user_email in user_emails:
        assert user_email not in raw_message

    filename, armored, mimetype = sent.attachments[0]
    assert filename == "test.json.gpg"
    assert mimetype == "application/pgp-encrypted"
    assert armored.startswith("-----BEGIN PGP MESSAGE-----")
    decrypted = gpg.decrypt(armored)
    assert decrypted.ok
    assert json.loads(decrypted.data) == {"event": "ping"}


@pytest.mark.django_db
def test_gpg_json_neutral_envelope(populate_db, gpg_keypair):
    _gpg, public_key = gpg_keypair
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="gpg_json",
        name="GPG JSON",
        config={"gpg_public_key": public_key},
    )

    ok, _message = connector.get_impl().test_connection()

    assert ok
    sent = mail.outbox[0]
    assert "ping" not in sent.subject
    assert "ping" not in sent.body


@pytest.mark.django_db
def test_gpg_json_fail_closed_on_invalid_key(populate_db):
    observer = populate_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="gpg_json",
        name="GPG JSON",
        config={"gpg_public_key": "garbage, not a key"},
    )

    ok, _message = connector.get_impl().test_connection()

    assert not ok
    assert mail.outbox == []


@pytest.mark.django_db
def test_gpg_json_fails_without_observer_email(populate_db, gpg_keypair):
    _gpg, public_key = gpg_keypair
    observer = populate_db["observers"][0]
    observer.email_for_notification = None
    observer.save()
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="gpg_json",
        name="GPG JSON",
        config={"gpg_public_key": public_key},
    )

    ok, _message = connector.get_impl().test_connection()
    assert not ok

    with pytest.raises(PermanentDeliveryError):
        connector.get_impl()._recipient()
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
