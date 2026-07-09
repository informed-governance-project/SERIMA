import json

import gnupg
import pytest
import requests
import responses
from django.core import mail
from django.utils.translation import activate

from governanceplatform.models import Observer, ObserverConnector
from incidents.email import dispatch_observer_notifications
from incidents.models import ConnectorDelivery
from incidents.scripts.connector_delivery import run as deliver

RT_URL = "https://rt.example.com"


@pytest.fixture
def resolvable_hosts(monkeypatch):
    monkeypatch.setattr("governanceplatform.validators.socket.gethostbyname", lambda hostname: "93.184.216.34")


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


@pytest.fixture
def rt_connector(populate_incident_db):
    observer = populate_incident_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="rt",
        name="RT",
        config={"url": RT_URL, "queue": "incidents"},
    )
    connector.secret = "rt-token"
    connector.save()
    return connector


@pytest.fixture
def email_template(populate_incident_db):
    return populate_incident_db["incidents_email"][0]


@pytest.fixture
def incident(populate_incident_db):
    return populate_incident_db["incidents"][0]


@pytest.mark.django_db
def test_dispatch_creates_deliveries_for_entitled_active_connectors_only(rt_connector, email_template, incident):
    observer = rt_connector.observer
    ObserverConnector.objects.create(observer=observer, connector_type="webhook", name="Hook", config={}, is_active=False)

    activate("en")
    # explicit pk: the fixture data inserts observers with fixed ids without advancing the sequence
    excluded_observer = Observer.objects.create(
        id=999,
        country="LU",
        address="456 rue de Luxembourg",
        email_for_notification="cert2@cert2.lu",
        is_receiving_all_incident=False,
        name="CERT2",
    )
    ObserverConnector.objects.create(observer=excluded_observer, connector_type="webhook", name="Hook", config={})

    default_recipients = dispatch_observer_notifications(email_template, incident)

    deliveries = ConnectorDelivery.objects.all()
    assert deliveries.count() == 1
    delivery = deliveries.get()
    assert delivery.connector == rt_connector
    assert delivery.status == ConnectorDelivery.Status.PENDING
    assert delivery.email == email_template
    # entitled observer has an active connector and mode "default" -> no plain e-mail;
    # the excluded observer never contributes anything
    assert default_recipients == []


@pytest.mark.django_db
def test_default_mode_falls_back_to_email_without_active_connectors(populate_incident_db, email_template, incident):
    observer = populate_incident_db["observers"][0]
    ObserverConnector.objects.create(observer=observer, connector_type="webhook", name="Hook", config={}, is_active=False)

    default_recipients = dispatch_observer_notifications(email_template, incident)

    assert ConnectorDelivery.objects.count() == 0
    assert observer.email_for_notification in default_recipients
    for observer_user in observer.observeruser_set.all():
        assert observer_user.user.email in default_recipients


@pytest.mark.django_db
def test_default_and_connectors_mode_sends_email_and_connectors(rt_connector, email_template, incident):
    observer = rt_connector.observer
    observer.notification_mode = Observer.NotificationMode.DEFAULT_AND_CONNECTORS
    observer.save()

    default_recipients = dispatch_observer_notifications(email_template, incident)

    assert ConnectorDelivery.objects.count() == 1
    assert observer.email_for_notification in default_recipients


@pytest.mark.django_db
def test_connectors_only_mode_never_sends_email(rt_connector, email_template, incident):
    observer = rt_connector.observer
    observer.notification_mode = Observer.NotificationMode.CONNECTORS_ONLY
    observer.save()

    default_recipients = dispatch_observer_notifications(email_template, incident)

    assert ConnectorDelivery.objects.count() == 1
    assert default_recipients == []


@pytest.mark.django_db
def test_connectors_only_mode_has_no_fallback_without_active_connectors(populate_incident_db, email_template, incident):
    observer = populate_incident_db["observers"][0]
    observer.notification_mode = Observer.NotificationMode.CONNECTORS_ONLY
    observer.save()

    default_recipients = dispatch_observer_notifications(email_template, incident)

    assert ConnectorDelivery.objects.count() == 0
    assert default_recipients == []


@pytest.mark.django_db
def test_default_mode_without_email_address_contributes_nothing(populate_incident_db, email_template, incident):
    observer = populate_incident_db["observers"][0]
    observer.email_for_notification = None
    observer.save()
    observer.observeruser_set.all().delete()

    default_recipients = dispatch_observer_notifications(email_template, incident)

    assert default_recipients == []
    assert ConnectorDelivery.objects.count() == 0


@pytest.mark.django_db
@responses.activate
def test_rt_delivery_creates_ticket(rt_connector, email_template, incident, resolvable_hosts):
    responses.add(responses.POST, f"{RT_URL}/REST/2.0/ticket", json={"id": 42}, status=201)
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=rt_connector, email=email_template)

    deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == ConnectorDelivery.Status.SENT
    assert delivery.external_ref == "42"
    assert delivery.attempts == 1
    assert delivery.last_error == ""


@pytest.mark.django_db
@responses.activate
def test_rt_delivery_corresponds_on_existing_ticket(rt_connector, email_template, incident, resolvable_hosts):
    ConnectorDelivery.objects.create(
        incident=incident,
        connector=rt_connector,
        email=email_template,
        status=ConnectorDelivery.Status.SENT,
        external_ref="42",
    )
    responses.add(responses.POST, f"{RT_URL}/REST/2.0/ticket/42/correspond", json={}, status=200)
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=rt_connector, email=email_template)

    deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == ConnectorDelivery.Status.SENT
    assert delivery.external_ref == "42"
    assert len(responses.calls) == 1


@pytest.mark.django_db
@responses.activate
def test_rt_transient_error_is_retried_until_failure(rt_connector, email_template, incident, resolvable_hosts):
    responses.add(responses.POST, f"{RT_URL}/REST/2.0/ticket", body=requests.exceptions.ConnectionError("unreachable"))
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=rt_connector, email=email_template)

    # eager mode executes the retries inline, so this exercises the full retry chain
    deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == ConnectorDelivery.Status.FAILED
    assert delivery.attempts == 1 + deliver.max_retries
    assert delivery.last_error != ""


@pytest.mark.django_db
@responses.activate
def test_rt_permanent_error_fails_without_retry(rt_connector, email_template, incident, resolvable_hosts):
    responses.add(responses.POST, f"{RT_URL}/REST/2.0/ticket", body="unauthorized", status=401)
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=rt_connector, email=email_template)

    result = deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert result.status == "SUCCESS"
    assert delivery.status == ConnectorDelivery.Status.FAILED
    assert "401" in delivery.last_error
    assert "rt-token" not in delivery.last_error


@pytest.mark.django_db
@responses.activate
def test_sent_delivery_is_not_resent(rt_connector, email_template, incident):
    delivery = ConnectorDelivery.objects.create(
        incident=incident,
        connector=rt_connector,
        email=email_template,
        status=ConnectorDelivery.Status.SENT,
        external_ref="42",
    )

    deliver.apply(args=[delivery.pk])

    assert len(responses.calls) == 0
    delivery.refresh_from_db()
    assert delivery.attempts == 0


@pytest.mark.django_db
def test_gpg_json_delivery_sends_encrypted_incident_payload(populate_incident_db, email_template, incident, gpg_keypair):
    gpg, public_key = gpg_keypair
    observer = populate_incident_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="gpg_json",
        name="GPG JSON",
        config={"gpg_public_key": public_key},
    )
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=connector, email=email_template)

    deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == ConnectorDelivery.Status.SENT
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.bcc == [observer.email_for_notification]
    filename, armored, mimetype = message.attachments[0]
    assert filename == f"incident_{incident.pk}.json.gpg"
    assert mimetype == "application/pgp-encrypted"
    decrypted = gpg.decrypt(armored)
    assert decrypted.ok
    payload = json.loads(decrypted.data)
    assert payload["incident"]["incident_id"] == incident.incident_id


@pytest.mark.django_db
def test_incident_payload_mirrors_pdf_sections(populate_incident_db, incident):
    from governanceplatform.connectors.payload import build_incident_payload

    payload = build_incident_payload(incident)

    # must be JSON-serializable end to end
    json.dumps(payload)

    inc = payload["incident"]
    assert inc["incident_id"] == incident.incident_id
    for section in ("status", "complaint_reference", "regulator", "sectors", "timeline", "contacts", "reports"):
        assert section in inc
    assert set(inc["contacts"]) == {"incident", "technical"}
    assert set(inc["contacts"]["incident"]) == {"first_name", "last_name", "title", "email", "telephone"}
    assert set(inc["timeline"]) == {"timezone", "notification_date", "detection_date", "starting_date", "resolution_date"}
