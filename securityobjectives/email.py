from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q
from django.utils import translation
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from governanceplatform.email import (
    COMMENT_ADDED_NOTICE,
    PUBLIC_URL_PLACEHOLDER,
    EmailPlaceholder,
    replace_placeholders,
    send_html_email,
)
from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import CompanyUser, RegulatorUser
from securityobjectives.globals import OPERATOR_STATUS, STANDARD_ANSWER_REVIEW_STATUS

if TYPE_CHECKING:
    from django.utils.functional import Promise

    from .models import StandardAnswer


def send_email(email, standard_answer):
    if email is not None:
        subject = replace_email_variables(
            email.safe_translation_getter("subject", language_code=settings.LANGUAGE_CODE),
            standard_answer,
        )
        html_content = render_to_string_multi_languages(
            "emails/notification.html",
            {
                "content": None,
            },
            replace_email_variables,
            content=email,
            object=standard_answer,
        )
        recipient_list = []
        company_users_emails = []
        # get company user emails
        if standard_answer.submitter_company is not None:
            company_users = CompanyUser.objects.filter(company=standard_answer.submitter_company).distinct("user")
            for c in company_users:
                company_users_emails.append(c.user.email)
        recipient_list.extend(company_users_emails)

        # get also regulator email and emails of responsible people for the designated sectors
        # + administrator issue #580
        regulator_email = standard_answer.standard.regulator.email_for_notification
        if regulator_email is not None:
            recipient_list.append(regulator_email)

        regulator_users_sectored = RegulatorUser.objects.filter(
            Q(
                regulator=standard_answer.standard.regulator,
                sectors__in=standard_answer.get_sectors(),
            )
            | Q(
                is_regulator_administrator=True,
                regulator=standard_answer.standard.regulator,
            )
        ).distinct("user")
        regulator_users_sectored_emails = []
        for u in regulator_users_sectored:
            regulator_users_sectored_emails.append(u.user.email)

        recipient_list.extend(regulator_users_sectored_emails)

        send_html_email(subject, html_content, recipient_list)


def send_export_notification(regulator, regulation, sector_ids):
    """Warn the regulator's contacts that a declaration export was produced.

    The mail carries no exported data on purpose: a recipient who needs to know what left
    the platform reads the log entry the export wrote.
    """
    recipient_list = set()

    if regulator.email_for_notification:
        recipient_list.add(regulator.email_for_notification)

    regulator_users = RegulatorUser.objects.filter(
        Q(regulator=regulator, sectors__in=sector_ids) | Q(regulator=regulator, is_regulator_administrator=True)
    ).distinct()
    recipient_list.update(regulator_users.values_list("user__email", flat=True))

    html_content = render_to_string_multi_languages(
        "emails/security_objective_mass_export.html",
        {
            "regulation": str(regulation),
            "site_name": settings.SITE_NAME,
        },
    )

    with translation.override(settings.LANGUAGE_CODE):
        subject = f"[{settings.SITE_NAME}] {_('New security objectives export')}"

    send_html_email(subject, html_content, sorted(recipient_list))


def _resolve_status(standard_answer: StandardAnswer) -> str | Promise:
    # The status the operator sees: PASS and FAIL stay "Under review" until the review is sent.
    return dict(STANDARD_ANSWER_REVIEW_STATUS)[OPERATOR_STATUS[standard_answer.status]]


def _resolve_review_comment_added(standard_answer: StandardAnswer) -> str | Promise:
    # The operator reads the review comment only once the review is sent, so the email does not announce it before.
    return COMMENT_ADDED_NOTICE if standard_answer.is_review_sent and standard_answer.review_comment else ""


# The placeholders usable in the security objective email templates of the admin interface.
# Adding a new one is a single entry here: the admin help dialog and the substitution both read from this list.

SO_EMAIL_PLACEHOLDERS = [
    PUBLIC_URL_PLACEHOLDER,
    EmailPlaceholder("#SO_REFERENCE#", _("Reference of the declaration"), lambda standard_answer: standard_answer.group.group_id),
    EmailPlaceholder("#SO_STATUS#", _("Status of the declaration"), _resolve_status),
    EmailPlaceholder(
        "#SO_REVIEW_COMMENT_ADDED#",
        # Same lazy string the resolver returns, so what the admin advertises cannot drift from what is sent.
        format_lazy('"{}" — {}', COMMENT_ADDED_NOTICE, _("empty until the review is sent with a comment")),
        _resolve_review_comment_added,
    ),
]


def replace_email_variables(content: str, standard_answer: StandardAnswer) -> str:
    return replace_placeholders(content, SO_EMAIL_PLACEHOLDERS, standard_answer)
