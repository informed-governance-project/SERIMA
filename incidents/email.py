import logging
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import Observer, RegulatorUser
from incidents.globals import INCIDENT_EMAIL_VARIABLES

logger = logging.getLogger(__name__)


def is_valid_email(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


# replace the variables in globals.py by the right value
def replace_email_variables(content, incident):
    # find the incidents which don't have final notification.
    modify_content = content
    modify_content = modify_content.replace("#PUBLIC_URL#", settings.PUBLIC_URL)
    for _i, (variable, key) in enumerate(INCIDENT_EMAIL_VARIABLES):
        if variable == "#INCIDENT_FINAL_NOTIFICATION_URL#":
            incident_id = getattr(incident, key)
            final_notification_url = settings.PUBLIC_URL + reverse("final-notification", args=[incident_id])
            var_txt = f'<a href="{final_notification_url}">{final_notification_url}</a>'
        elif variable == "#INCIDENT_DETECTION_DATE#":
            last_report = incident.get_latest_incident_workflow()
            if not last_report:
                var_txt = incident.incident_detection_date.strftime("%Y-%m-%d") if incident.incident_detection_date is not None else ""
            else:
                var_txt = (
                    last_report.report_timeline.incident_detection_date.strftime("%Y-%m-%d")
                    if last_report.report_timeline.incident_detection_date is not None
                    else ""
                )
        elif variable == "#INCIDENT_STARTING_DATE#":
            last_report = incident.get_latest_incident_workflow()
            if not last_report:
                var_txt = ""
            else:
                var_txt = (
                    last_report.report_timeline.incident_starting_date.strftime("%Y-%m-%d")
                    if last_report.report_timeline.incident_starting_date is not None
                    else ""
                )
        elif variable == "#DEADLINE#":
            deadline = incident.get_deadline()
            if not deadline:
                var_txt = ""
            else:
                deadline = timezone.localtime(deadline)
                var_txt = deadline.strftime("%Y-%m-%d %H:%M %Z")
        else:
            var_txt = getattr(incident, key) if getattr(incident, key) is not None else ""
            if isinstance(var_txt, date):
                var_txt = getattr(incident, key).strftime("%Y-%m-%d")
        modify_content = modify_content.replace(variable, var_txt)
    return modify_content


def send_html_email(subject, content, recipient_list, attachments=None):
    valid_recipient_list = [email for email in recipient_list if is_valid_email(email)]
    if not valid_recipient_list:
        logger.warning(
            "Email not sent: no valid recipients",
            extra={"original_recipients": recipient_list},
        )
        return False

    email = EmailMessage(
        subject,
        content,
        settings.EMAIL_SENDER,
        bcc=valid_recipient_list,
    )
    email.content_subtype = "html"
    for attachment in attachments or []:
        email.attach(*attachment)

    try:
        sent_count = email.send()

        if sent_count == 0:
            logger.error(
                "Email send returned 0 (no email sent)",
                extra={
                    "subject": subject,
                    "recipients": valid_recipient_list,
                },
            )
            return False

        return True

    except Exception:
        logger.exception(
            "Email sending failed",
            extra={
                "subject": subject,
                "recipients": valid_recipient_list,
                "sender": settings.EMAIL_SENDER,
            },
        )
        return False


def get_emails_from_qs(queryset):
    return [obj.user.email for obj in queryset]


def get_recipient_list(incident):
    # Contact user's email
    recipient_list = []
    if incident.contact_user is not None:
        recipient_list.append(incident.contact_user.email)
    company = incident.company
    sector_regulation = incident.sector_regulation
    regulator = sector_regulation.regulator

    if company:
        # Company's email
        recipient_list.append(company.email)

        company_admins_qs = company.companyuser_set.filter(is_company_administrator=True).select_related("user")
    else:
        company_admins_qs = []

    # Company administrators' emails
    recipient_list.extend(get_emails_from_qs(company_admins_qs))

    # Regulator's email
    recipient_list.append(regulator.email_for_notification)

    # Regulator administrators' emails
    regulator_admins_qs = regulator.regulatoruser_set.filter(is_regulator_administrator=True).select_related("user")
    recipient_list.extend(get_emails_from_qs(regulator_admins_qs))

    # Sector managers' emails
    regulator_users_sectored = RegulatorUser.objects.filter(
        regulator=regulator,
        sectors__in=incident.affected_sectors.all(),
    ).distinct("user")
    recipient_list.extend(get_emails_from_qs(regulator_users_sectored))

    return recipient_list


def render_notification(email, incident):
    subject = replace_email_variables(
        email.safe_translation_getter("subject", language_code=settings.LANGUAGE_CODE),
        incident,
    )
    html_content = render_to_string_multi_languages(
        "incidents/email.html",
        {
            "content": None,
            "url_site": settings.PUBLIC_URL,
            "company_name": incident.company_name,
            "incident_contact_title": incident.contact_title,
            "incident_contact_firstname": incident.contact_firstname,
            "incident_contact_lastname": incident.contact_lastname,
            "technical_contact_title": incident.technical_title,
            "technical_contact_firstname": incident.technical_firstname,
            "technical_contact_lastname": incident.technical_lastname,
        },
        replace_email_variables,
        content=email,
        object=incident,
    )
    return subject, html_content


def dispatch_observer_notifications(email, incident):
    """Create deliveries for the observers' active connectors; return the plain-email
    recipients owed by their notification modes (default e-mail behavior)."""
    from .models import ConnectorDelivery
    from .scripts.connector_delivery import run as deliver_connector_notification

    default_recipients = []
    for observer in Observer.objects.prefetch_related("connectors"):
        if not observer.can_access_incident(incident):
            continue

        active_connectors = [connector for connector in observer.connectors.all() if connector.is_active]
        for connector in active_connectors:
            delivery = ConnectorDelivery.objects.create(incident=incident, connector=connector, email=email)
            transaction.on_commit(lambda pk=delivery.pk: deliver_connector_notification.delay(pk))

        # default e-mail: fallback when no connector is active, always in
        # "default_and_connectors" mode, never in "connectors_only" mode
        owes_email = observer.notification_mode == Observer.NotificationMode.DEFAULT_AND_CONNECTORS or (
            not active_connectors and observer.notification_mode == Observer.NotificationMode.DEFAULT
        )
        if owes_email:
            if observer.email_for_notification:
                default_recipients.append(observer.email_for_notification)
            else:
                logger.warning("Observer %s owes an e-mail notification but has no notification address", observer.pk)
            default_recipients.extend(get_emails_from_qs(observer.observeruser_set.all().select_related("user")))

    return default_recipients


def send_email(email, incident, send_to_observers=False):
    subject, html_content = render_notification(email, incident)
    recipient_list = get_recipient_list(incident)

    if send_to_observers:
        recipient_list.extend(dispatch_observer_notifications(email, incident))

    # Remove duplicates
    recipient_list = list(dict.fromkeys(recipient_list))

    send_html_email(subject, html_content, recipient_list)
