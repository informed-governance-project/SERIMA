import logging

import requests
from celery import shared_task

from governanceplatform.connectors import (
    NotificationContext,
    PermanentDeliveryError,
    TransientDeliveryError,
)
from incidents.email import render_notification
from incidents.models import ConnectorDelivery

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
    subject, html_content = render_notification(delivery.email, delivery.incident)
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

    try:
        result = delivery.connector.get_impl().send(ctx)
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
    delivery.save()
