import logging

import requests
from celery import shared_task
from django.db import transaction

from governanceplatform.connectors import (
    NotificationContext,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from incidents.email import EmailContext, render_notification
from incidents.globals import CONNECTOR_LOG_ROLE, TRANSMIT_ACTION
from incidents.models import ConnectorDelivery, LogReportRead

logger = logging.getLogger(__name__)

RETRY_BASE_DELAY = 60
RETRY_MAX_DELAY = 600


# Event-driven task: enqueued by dispatch_observer_notifications, no beat schedule
@shared_task(name="deliver_connector_notification", bind=True, max_retries=5)
def run(self, delivery_id):
    delivery = ConnectorDelivery.objects.select_related("connector__observer", "incident", "email").filter(pk=delivery_id).first()
    if delivery is None or delivery.status == ConnectorDelivery.Status.SENT:
        return

    delivery.attempts += 1
    subject, html_content = render_notification(delivery.email, EmailContext(delivery.incident))
    previous_delivery = (
        ConnectorDelivery.objects.filter(
            incident=delivery.incident,
            connector=delivery.connector,
            status=ConnectorDelivery.Status.SENT,
        )
        .exclude(external_ref="")
        .order_by("-created_at")
        .first()
    )
    ctx = NotificationContext(
        incident=delivery.incident,
        subject=subject,
        content_html=html_content,
        previous_external_ref=previous_delivery.external_ref if previous_delivery else "",
    )

    impl = delivery.connector.get_impl()
    try:
        result = impl.send(ctx)
    except PermanentDeliveryError as e:
        logger.error("Connector delivery %s failed permanently: %s", delivery.pk, e)
        delivery.status = ConnectorDelivery.Status.FAILED
        delivery.last_error = str(e)
        delivery.save()
        return
    except (TransientDeliveryError, requests.RequestException) as e:
        logger.warning("Connector delivery %s failed (attempt %s): %s", delivery.pk, delivery.attempts, e)
        delivery.last_error = str(e)
        if self.request.retries >= self.max_retries:
            delivery.status = ConnectorDelivery.Status.FAILED
            delivery.save()
            return
        delivery.save()
        raise self.retry(exc=e, countdown=min(RETRY_BASE_DELAY * 2**self.request.retries, RETRY_MAX_DELAY))

    delivery.status = ConnectorDelivery.Status.SENT
    delivery.external_ref = result.external_ref or delivery.external_ref
    delivery.last_error = ""
    with transaction.atomic():
        delivery.save()
        if impl.transmits_incident_payload:
            log_transmission(delivery)


def log_transmission(delivery: ConnectorDelivery) -> None:
    # One entry per report the payload carries, as the API logs a read of the incident.
    # bulk_create skips LogReportRead.save(), which needs a user and would bump incident_last_update.
    connector = delivery.connector
    LogReportRead.objects.bulk_create(
        LogReportRead(
            user=None,
            user_full_name=connector.name,
            role=CONNECTOR_LOG_ROLE,
            entity_name=connector.observer.name,
            incident=delivery.incident,
            incident_report=report,
            action=TRANSMIT_ACTION,
        )
        for report in delivery.incident.get_latest_incident_workflows()
    )
