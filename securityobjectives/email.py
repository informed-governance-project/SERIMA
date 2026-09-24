from datetime import date

from django.conf import settings
from django.db.models import Q
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from governanceplatform.email import send_html_email
from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import CompanyUser, RegulatorUser
from securityobjectives.globals import SO_EMAIL_VARIABLES


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
                sectors__in=standard_answer.sectors.all(),
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
        subject = _("[{site}] New security objectives export").format(site=settings.SITE_NAME)

    send_html_email(subject, html_content, sorted(recipient_list))


# replace the variables in globals.py by the right value
def replace_email_variables(content, standard_answer):
    modify_content = content
    for _i, (variable, key) in enumerate(SO_EMAIL_VARIABLES):
        if variable == "#SO_REFERENCE#":
            group_id = standard_answer.group.group_id
            if not group_id:
                var_txt = ""
            else:
                var_txt = group_id
        else:
            var_txt = getattr(standard_answer, key) if getattr(standard_answer, key) is not None else ""
            if isinstance(var_txt, date):
                var_txt = getattr(standard_answer, key).strftime("%Y-%m-%d")
        modify_content = modify_content.replace(variable, var_txt)
    return modify_content
