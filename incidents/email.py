import logging
from datetime import date

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from governanceplatform.email import send_html_email
from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import Observer, RegulatorUser
from governanceplatform.rt import add_rt_correspondence, check_rt_config, create_rt_ticket
from incidents.globals import INCIDENT_EMAIL_VARIABLES

from .access_control import observer_can_access_incident
from .models import RTTicket

logger = logging.getLogger(__name__)


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


def send_email(email, incident, send_to_observers=False):
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
    recipient_list = get_recipient_list(incident)

    if send_to_observers:
        observer_emails = []
        observers = Observer.objects.all()
        for observer in observers:
            if observer_can_access_incident(observer, incident):
                if check_rt_config(observer):
                    create_or_update_rt_ticket(observer, subject, html_content, incident)
                else:
                    # Observer's mail
                    observer_emails.append(observer.email_for_notification)
                    # Observer users' email
                    observer_user_qs = observer.observeruser_set.all().select_related("user")
                    observer_emails.extend(get_emails_from_qs(observer_user_qs))

        recipient_list.extend(observer_emails)

    # Remove duplicates
    recipient_list = list(dict.fromkeys(recipient_list))

    send_html_email(subject, html_content, recipient_list)


def create_or_update_rt_ticket(recipient, subject, content, incident):
    """Open an RT ticket for this incident, or reply on the one already opened for it."""
    ticket = RTTicket.objects.filter(incident=incident, observer=recipient).first()

    if ticket is not None:
        add_rt_correspondence(recipient, ticket.ticket_id, content)
        return

    ticket_id = create_rt_ticket(recipient, subject, content)
    if ticket_id is not None:
        RTTicket.objects.create(incident=incident, observer=recipient, ticket_id=ticket_id)
