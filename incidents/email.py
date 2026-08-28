import logging
from dataclasses import KW_ONLY, dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from django.utils.functional import Promise

from governanceplatform.email import send_html_email
from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import Observer, RegulatorUser
from governanceplatform.rt import add_rt_correspondence, check_rt_config, create_rt_ticket

from .access_control import observer_can_access_incident
from .globals import WORKFLOW_REVIEW_STATUS
from .helpers import is_deadline_exceeded
from .models import Email, Incident, IncidentWorkflow, ReportTimeline, RTTicket, Workflow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailContext:
    """What an email is about.

    Pass ``incident_workflow`` when the email concerns a submission, so its review status is read from it
    rather than derived. Reminders and deadline notices chase a report with no submission at all: they pass
    ``workflow`` instead, and the status is derived from the deadline.
    """

    incident: Incident
    _: KW_ONLY
    workflow: Workflow | None = None
    incident_workflow: IncidentWorkflow | None = None


@dataclass(frozen=True)
class EmailPlaceholder:
    """A token a regulator can type in an email template, and how to resolve it against an incident."""

    token: str
    description: str | Promise
    resolve: Callable[[EmailContext], Any]

    def render(self, context: EmailContext) -> str:
        value = self.resolve(context)
        return "" if value is None else str(value)


def _format_date(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value is not None else ""


def _latest_report_timeline(context: EmailContext) -> ReportTimeline | None:
    latest_report = context.incident.get_latest_incident_workflow()
    return latest_report.report_timeline if latest_report is not None else None


def _resolve_detection_date(context: EmailContext) -> str:
    timeline = _latest_report_timeline(context)
    if timeline is None:
        return _format_date(context.incident.incident_detection_date)
    return _format_date(timeline.incident_detection_date)


def _resolve_starting_date(context: EmailContext) -> str:
    timeline = _latest_report_timeline(context)
    if timeline is None:
        return ""
    return _format_date(timeline.incident_starting_date)


def _report_in_context(context: EmailContext) -> Workflow | None:
    """The report the email is about, falling back to the latest submitted one for incident-wide emails."""
    if context.incident_workflow is not None:
        return context.incident_workflow.workflow
    if context.workflow is not None:
        return context.workflow
    latest_report = context.incident.get_latest_incident_workflow()
    return latest_report.workflow if latest_report is not None else None


def _resolve_report_name(context: EmailContext) -> str:
    workflow = _report_in_context(context)
    return str(workflow) if workflow is not None else ""


def _resolve_review_status(context: EmailContext) -> str | Promise:
    if context.incident_workflow is not None:
        return context.incident_workflow.get_review_status_display()
    workflow = _report_in_context(context)
    if workflow is None:
        return ""
    # Mirrors the incident list: the status of the latest submission, or the one derived from the deadline
    # when nothing has been submitted for that report yet.
    return dict(WORKFLOW_REVIEW_STATUS).get(is_deadline_exceeded(workflow, context.incident), "")


def _submission_in_context(context: EmailContext) -> IncidentWorkflow | None:
    """The submission the email is about. A reminder names a report instead, which may have none yet."""
    if context.incident_workflow is not None:
        return context.incident_workflow
    if context.workflow is not None:
        return context.incident.get_latest_incident_workflow_by_workflow(context.workflow)
    return context.incident.get_latest_incident_workflow()


def _resolve_comment_added(context: EmailContext) -> str | Promise:
    # Plain truthiness, as the comment icon the operator sees on its incident list uses.
    submission = _submission_in_context(context)
    return _("New comment added") if submission is not None and submission.comment else ""


def _resolve_deadline(context: EmailContext) -> str:
    deadline = context.incident.get_deadline()
    if deadline is None:
        return ""
    return timezone.localtime(deadline).strftime("%Y-%m-%d %H:%M %Z")


# The placeholders usable in the email templates of the admin interface.
# Adding a new one is a single entry here: the admin help text and the substitution both read from this list.

INCIDENT_EMAIL_PLACEHOLDERS = [
    EmailPlaceholder("#PUBLIC_URL#", _("Address of the platform"), lambda context: settings.PUBLIC_URL),
    EmailPlaceholder("#INCIDENT_ID#", _("Incident reference"), lambda context: context.incident.incident_id),
    EmailPlaceholder(
        "#INCIDENT_NOTIFICATION_DATE#",
        _("Date the incident was notified"),
        lambda context: _format_date(context.incident.incident_notification_date),
    ),
    EmailPlaceholder("#INCIDENT_DETECTION_DATE#", _("Date the incident was detected"), _resolve_detection_date),
    EmailPlaceholder("#INCIDENT_STARTING_DATE#", _("Date the incident started"), _resolve_starting_date),
    EmailPlaceholder("#INCIDENT_STATUS#", _("Status of the incident"), lambda context: context.incident.get_incident_status_display()),
    EmailPlaceholder("#REPORT_NAME#", _("Name of the report"), _resolve_report_name),
    EmailPlaceholder("#REPORT_REVIEW_STATUS#", _("Status of that report"), _resolve_review_status),
    EmailPlaceholder("#REPORT_COMMENT_ADDED#", _("Notice that the regulator left a review comment"), _resolve_comment_added),
    EmailPlaceholder("#DEADLINE#", _("Deadline of the next report"), _resolve_deadline),
]


def replace_email_variables(content: str, context: EmailContext) -> str:
    for placeholder in INCIDENT_EMAIL_PLACEHOLDERS:
        if placeholder.token in content:
            content = content.replace(placeholder.token, placeholder.render(context))
    return content


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


def send_email(
    email_template: Email,
    incident: Incident,
    *,
    workflow: Workflow | None = None,
    incident_workflow: IncidentWorkflow | None = None,
    send_to_observers: bool = False,
) -> None:
    context = EmailContext(incident, workflow=workflow, incident_workflow=incident_workflow)
    subject = replace_email_variables(
        email_template.safe_translation_getter("subject", language_code=settings.LANGUAGE_CODE),
        context,
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
        content=email_template,
        object=context,
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
