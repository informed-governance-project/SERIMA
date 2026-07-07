from django.utils import timezone


def build_incident_payload(incident, subject: str, content_html: str) -> dict:
    sector_regulation = incident.sector_regulation
    return {
        "event": "incident_notification",
        "sent_at": timezone.now().isoformat(),
        "incident": {
            "id": incident.pk,
            "incident_id": incident.incident_id,
            "company_name": incident.company_name,
            "incident_notification_date": incident.incident_notification_date.isoformat(),
            "regulation": str(sector_regulation.regulation) if sector_regulation else "",
            "affected_sectors": [str(sector) for sector in incident.affected_sectors.all()],
        },
        "subject": subject,
        "content_html": content_html,
    }
