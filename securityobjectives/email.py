from datetime import date

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q

from governanceplatform.helpers import render_to_string_multi_languages
from governanceplatform.models import CompanyUser, RegulatorUser
from securityobjectives.globals import SO_EMAIL_VARIABLES


def send_html_email(subject, content, recipient_list):
    email = EmailMessage(subject, content, settings.EMAIL_SENDER, bcc=recipient_list)
    email.content_subtype = "html"
    email.send(fail_silently=True)


def send_email(email, standard_answer):
    if email is not None:
        subject = replace_email_variables(
            email.safe_translation_getter("subject", language_code=settings.LANGUAGE_CODE),
            standard_answer,
        )
        html_content = render_to_string_multi_languages(
            "security_objectives/email.html",
            {
                "content": None,
                "url_site": settings.PUBLIC_URL,
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
