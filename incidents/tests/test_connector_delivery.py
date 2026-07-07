import json

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
    ObserverConnector.objects.create(observer=observer, connector_type="email", name="Email", config={}, is_active=False)

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
    ObserverConnector.objects.create(observer=excluded_observer, connector_type="email", name="Email", config={})

    dispatch_observer_notifications(email_template, incident)

    deliveries = ConnectorDelivery.objects.all()
    assert deliveries.count() == 1
    delivery = deliveries.get()
    assert delivery.connector == rt_connector
    assert delivery.status == ConnectorDelivery.Status.PENDING
    assert delivery.email == email_template


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
def test_email_delivery_with_incident_json_attachment(populate_incident_db, email_template, incident):
    observer = populate_incident_db["observers"][0]
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="email",
        name="Email",
        config={
            "send_to_observer_email": True,
            "send_to_observer_users": False,
            "additional_recipients": [],
            "attach_incident_json": True,
            "gpg_public_key": "",
        },
    )
    delivery = ConnectorDelivery.objects.create(incident=incident, connector=connector, email=email_template)

    deliver.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == ConnectorDelivery.Status.SENT
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.bcc == [observer.email_for_notification]
    filename, content, mimetype = message.attachments[0]
    assert filename == f"incident_{incident.pk}.json"
    assert mimetype == "application/json"
    payload = json.loads(content)
    assert payload["incident"]["incident_id"] == incident.incident_id
