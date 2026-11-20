from datetime import timedelta

import pytest
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

from governanceplatform.models import ApplicationConfig, User
from incidents.email import INCIDENT_EMAIL_PLACEHOLDERS, EmailContext, render_notification, replace_email_variables
from incidents.helpers import CROSS_BORDER_POSITIVE_ANSWER_KEY, CROSS_BORDER_QUESTION_REFERENCE_KEY
from incidents.models import Answer, Email, IncidentWorkflow, PredefinedAnswer, QuestionOptions, ReportTimeline, Workflow


@pytest.fixture
def incident(populate_incident_db):
    return populate_incident_db["incidents"][0]


@pytest.fixture
def add_report(db):
    def _add_report(incident, workflow_id=1, detection_date=None, starting_date=None, with_timeline=True):
        timeline = None
        if with_timeline:
            timeline = ReportTimeline.objects.create(
                incident_detection_date=detection_date,
                incident_starting_date=starting_date,
            )
        return IncidentWorkflow.objects.create(
            incident=incident,
            workflow=Workflow.objects.get(id=workflow_id),
            report_timeline=timeline,
        )

    return _add_report


@pytest.mark.django_db
def test_incident_id_placeholder_is_replaced(incident):
    assert replace_email_variables("Incident #INCIDENT_ID# is open", EmailContext(incident)) == f"Incident {incident.incident_id} is open"


@pytest.mark.django_db
def test_placeholder_is_replaced_at_every_occurrence(incident):
    content = "#INCIDENT_ID# / #INCIDENT_ID#"
    assert replace_email_variables(content, EmailContext(incident)) == f"{incident.incident_id} / {incident.incident_id}"


@pytest.mark.django_db
def test_public_url_placeholder_uses_settings(incident, settings):
    settings.PUBLIC_URL = "https://serima.example.lu"
    assert replace_email_variables("Go to #PUBLIC_URL#", EmailContext(incident)) == "Go to https://serima.example.lu"


@pytest.mark.django_db
def test_unknown_placeholder_is_left_untouched(incident):
    assert replace_email_variables("Hello #NOT_A_PLACEHOLDER#", EmailContext(incident)) == "Hello #NOT_A_PLACEHOLDER#"


@pytest.mark.django_db
def test_notification_date_renders_as_iso_date(incident):
    expected = incident.incident_notification_date.strftime("%Y-%m-%d")
    assert replace_email_variables("#INCIDENT_NOTIFICATION_DATE#", EmailContext(incident)) == expected


@pytest.mark.django_db
def test_detection_date_falls_back_to_the_incident_when_no_report_exists(incident):
    expected = incident.incident_detection_date.strftime("%Y-%m-%d")
    assert replace_email_variables("#INCIDENT_DETECTION_DATE#", EmailContext(incident)) == expected


@pytest.mark.django_db
def test_detection_date_comes_from_the_latest_report(incident, add_report):
    reported_date = timezone.now() - timedelta(days=3)
    add_report(incident, detection_date=reported_date)
    assert replace_email_variables("#INCIDENT_DETECTION_DATE#", EmailContext(incident)) == reported_date.strftime("%Y-%m-%d")


@pytest.mark.django_db
def test_starting_date_is_empty_when_no_report_exists(incident):
    assert replace_email_variables("[#INCIDENT_STARTING_DATE#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_starting_date_comes_from_the_latest_report(incident, add_report):
    started_at = timezone.now() - timedelta(days=5)
    add_report(incident, starting_date=started_at)
    assert replace_email_variables("#INCIDENT_STARTING_DATE#", EmailContext(incident)) == started_at.strftime("%Y-%m-%d")


@pytest.mark.django_db
def test_dates_fall_back_when_the_latest_report_has_no_timeline(incident, add_report):
    add_report(incident, with_timeline=False)
    detection_date = incident.incident_detection_date.strftime("%Y-%m-%d")
    assert (
        replace_email_variables("[#INCIDENT_DETECTION_DATE#][#INCIDENT_STARTING_DATE#]", EmailContext(incident)) == f"[{detection_date}][]"
    )


@pytest.mark.django_db
def test_incident_status_renders_its_label(incident):
    incident.incident_status = "CLOSE"
    incident.save()
    assert replace_email_variables("#INCIDENT_STATUS#", EmailContext(incident)) == "Closed"


@pytest.mark.django_db
def test_incident_status_is_translated_into_the_email_language(incident):
    with override("fr"):
        if str(_("Ongoing")) == "Ongoing":
            pytest.skip("French catalogue is not compiled; run manage.py compilemessages")
        assert replace_email_variables("#INCIDENT_STATUS#", EmailContext(incident)) == "En cours"


@pytest.mark.django_db
def test_review_status_is_empty_when_no_report_exists(incident):
    assert replace_email_variables("[#REPORT_REVIEW_STATUS#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_review_status_comes_from_the_latest_report(incident, add_report):
    report = add_report(incident)
    report.review_status = "PASS"
    report.save()
    assert replace_email_variables("#REPORT_REVIEW_STATUS#", EmailContext(incident)) == "Passed"


@pytest.mark.django_db
def test_report_name_is_empty_when_no_report_exists(incident):
    assert replace_email_variables("[#REPORT_NAME#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_report_name_comes_from_the_latest_report(incident, add_report):
    add_report(incident, workflow_id=1)
    assert replace_email_variables("#REPORT_NAME#", EmailContext(incident)) == str(Workflow.objects.get(id=1))


@pytest.mark.django_db
def test_comment_added_is_empty_without_a_review_comment(incident, add_report):
    add_report(incident, workflow_id=1)
    assert replace_email_variables("[#REPORT_COMMENT_ADDED#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_comment_added_announces_a_comment_left_by_the_regulator(incident, add_report):
    report = add_report(incident, workflow_id=1)
    report.comment = "Please clarify the impact figures."
    report.save()

    rendered = replace_email_variables("#REPORT_COMMENT_ADDED#", EmailContext(incident, incident_workflow=report))

    assert rendered == "New comment added"


@pytest.mark.django_db
def test_comment_added_is_empty_when_no_report_was_submitted(incident):
    assert replace_email_variables("[#REPORT_COMMENT_ADDED#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_comment_added_reads_the_submission_of_the_report_in_context(incident, add_report):
    """A reminder names a report; the comment must come from that report's submission, not another one."""
    commented = add_report(incident, workflow_id=1)
    commented.comment = "Needs more detail."
    commented.save()
    add_report(incident, workflow_id=2)

    rendered = replace_email_variables("#REPORT_COMMENT_ADDED#", EmailContext(incident, workflow=commented.workflow))

    assert rendered == "New comment added"


# --- the report the email is about ------------------------------------------------------------


@pytest.mark.django_db
def test_the_report_in_context_wins_over_the_latest_one(incident, add_report):
    """A reminder chases a report that is not the latest, and often has no submission at all."""
    add_report(incident, workflow_id=1)
    chased = Workflow.objects.get(id=2)

    rendered = replace_email_variables("#REPORT_NAME#", EmailContext(incident, workflow=chased))

    assert rendered == str(chased)


@pytest.mark.django_db
def test_the_status_of_an_unsubmitted_report_in_context_is_derived(incident, add_report):
    add_report(incident, workflow_id=1)
    unsubmitted = Workflow.objects.get(id=2)

    rendered = replace_email_variables("#REPORT_REVIEW_STATUS#", EmailContext(incident, workflow=unsubmitted))

    assert rendered == "Unsubmitted"


@pytest.mark.django_db
def test_an_overdue_report_in_context_renders_as_overdue(populate_incident_db, create_incident):
    """workflow_update_status sends its email for a report whose deadline has passed and which was never filed."""
    sector_regulation = next(sr for sr in populate_incident_db["incidents_workflows"] if sr.id == 2)
    user = next(u for u in populate_incident_db["users"] if u.email == "opadmin@com1.lu")
    overdue_incident = create_incident(
        user=user,
        workflow=sector_regulation,
        incident_id="XXXX-SSS-SSS-0003-2005",
        # the report is due 16 hours after detection
        incident_detection_date=timezone.now() - timedelta(hours=48),
    )
    late_report = Workflow.objects.get(id=3)

    rendered = replace_email_variables("#REPORT_REVIEW_STATUS#", EmailContext(overdue_incident, workflow=late_report))

    assert rendered == "Submission overdue"


# --- the submission the email is about --------------------------------------------------------


@pytest.mark.django_db
def test_a_submission_in_context_supplies_its_own_status_without_deriving_it(incident, add_report):
    """A status the regulator just set is read off the submission, not recomputed from the deadline."""
    submission = add_report(incident, workflow_id=1)
    submission.review_status = "PASS"
    submission.save()

    rendered = replace_email_variables(
        "#REPORT_NAME# #REPORT_REVIEW_STATUS#",
        EmailContext(incident, incident_workflow=submission),
    )

    assert rendered == f"{submission.workflow} Passed"


@pytest.mark.django_db
def test_a_submission_in_context_wins_over_a_later_one(incident, add_report):
    earlier = add_report(incident, workflow_id=1)
    earlier.review_status = "FAIL"
    earlier.save()
    add_report(incident, workflow_id=2)

    rendered = replace_email_variables("#REPORT_REVIEW_STATUS#", EmailContext(incident, incident_workflow=earlier))

    assert rendered == "Revision required"


@pytest.mark.django_db
def test_the_submission_in_context_names_its_own_report(incident, add_report):
    """A reminder concerns a specific submission, which is not necessarily the latest one."""
    earlier = add_report(incident, workflow_id=1)
    add_report(incident, workflow_id=2)

    rendered = replace_email_variables("#REPORT_NAME#", EmailContext(incident, incident_workflow=earlier))

    assert rendered == str(earlier.workflow)


@pytest.mark.django_db
def test_deadline_is_empty_when_the_workflow_defines_none(incident):
    assert replace_email_variables("[#DEADLINE#]", EmailContext(incident)) == "[]"


@pytest.mark.django_db
def test_deadline_renders_a_localised_datetime(populate_incident_db, create_incident):
    sector_regulation = next(sr for sr in populate_incident_db["incidents_workflows"] if sr.id == 2)
    user = next(u for u in populate_incident_db["users"] if u.email == "opadmin@com1.lu")
    detection_date = timezone.now()
    incident = create_incident(
        user=user,
        workflow=sector_regulation,
        incident_id="XXXX-SSS-SSS-0002-2005",
        incident_detection_date=detection_date,
    )
    expected = timezone.localtime(detection_date + timedelta(hours=16)).strftime("%Y-%m-%d %H:%M %Z")
    assert replace_email_variables("#DEADLINE#", EmailContext(incident)) == expected


# --- the subject of a notification --------------------------------------------------------------


def email_template(subject, content="<p>A report was submitted.</p>"):
    # Reuse a fixture email: the fixtures insert emails with explicit primary keys without advancing the
    # sequence, so creating one collides on the id.
    email = Email.objects.first()
    email.set_current_language("en")
    email.subject = subject
    email.content = content
    email.save()
    return email


@pytest.mark.django_db
def test_the_subject_is_rendered_in_the_instance_language_not_the_ambient_one(incident, add_report, settings):
    """An operator submitting in English on a French instance must not get an English notice in a French subject."""
    settings.LANGUAGE_CODE = "fr"
    with override("fr"):
        if str(_("New comment added")) == "New comment added":
            pytest.skip("French catalogue is not compiled; run manage.py compilemessages")
    report = add_report(incident, workflow_id=1)
    report.comment = "Please clarify the impact figures."
    report.save()

    with override("en"):
        subject, _body = render_notification(email_template("#REPORT_COMMENT_ADDED# Report"), EmailContext(incident))

    assert subject == "Ajout d'un nouveau commentaire Report"


@pytest.mark.django_db
def test_a_placeholder_rendering_empty_leaves_no_spacing_in_the_subject(incident, add_report):
    add_report(incident, workflow_id=1)

    subject, _body = render_notification(email_template("#REPORT_COMMENT_ADDED# Report  for #INCIDENT_ID#"), EmailContext(incident))

    assert subject == f"Report for {incident.incident_id}"


# --- #CROSS_BORDER# ------------------------------------------------------------------------------

CROSS_BORDER_QUESTION_REFERENCE = "1"
CROSS_BORDER_MARKER = "[Cross-border]"


def designate_cross_border_question(positive_answer=None):
    ApplicationConfig.objects.create(key=CROSS_BORDER_QUESTION_REFERENCE_KEY, value=CROSS_BORDER_QUESTION_REFERENCE)
    if positive_answer is not None:
        ApplicationConfig.objects.create(key=CROSS_BORDER_POSITIVE_ANSWER_KEY, value=positive_answer)


def answer_cross_border(incident, predefined_answer_label, submitted_at=None):
    """Submit a report answering the cross-border question."""
    submitted_at = submitted_at or timezone.now()
    question_options = QuestionOptions.objects.filter(question__reference=CROSS_BORDER_QUESTION_REFERENCE).first()
    incident_workflow = IncidentWorkflow.objects.create(
        incident=incident,
        workflow=Workflow.objects.first(),
        timestamp=submitted_at,
        report_timeline=ReportTimeline.objects.create(incident_detection_date=submitted_at),
    )
    answer = Answer.objects.create(incident_workflow=incident_workflow, question_options=question_options, timestamp=submitted_at)
    answer.predefined_answers.set(
        PredefinedAnswer.objects.filter(question=question_options.question, translations__predefined_answer=predefined_answer_label)
    )
    return incident_workflow


def cross_border(incident):
    return replace_email_variables("#CROSS_BORDER#", EmailContext(incident))


@pytest.mark.django_db
def test_cross_border_renders_nothing_until_a_question_is_designated(incident):
    answer_cross_border(incident, "Yes")
    assert cross_border(incident) == ""


@pytest.mark.django_db
def test_cross_border_marks_an_incident_reported_as_cross_border(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "Yes")
    assert cross_border(incident) == CROSS_BORDER_MARKER


@pytest.mark.django_db
def test_cross_border_renders_nothing_for_an_incident_reported_otherwise(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "No")
    assert cross_border(incident) == ""


@pytest.mark.django_db
def test_cross_border_renders_nothing_before_any_report(incident):
    designate_cross_border_question()
    assert cross_border(incident) == ""


@pytest.mark.django_db
def test_cross_border_follows_the_latest_report_both_ways(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "Yes", timezone.now() - timedelta(days=2))
    assert cross_border(incident) == CROSS_BORDER_MARKER

    answer_cross_border(incident, "No", timezone.now() - timedelta(days=1))
    assert cross_border(incident) == ""

    answer_cross_border(incident, "Yes", timezone.now())
    assert cross_border(incident) == CROSS_BORDER_MARKER


@pytest.mark.django_db
def test_cross_border_reads_the_positive_answer_from_the_configuration(incident):
    designate_cross_border_question(positive_answer="No")
    answer_cross_border(incident, "No")
    assert cross_border(incident) == CROSS_BORDER_MARKER


@pytest.mark.django_db
def test_cross_border_marks_the_subject_and_the_body(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "Yes")

    subject, body = render_notification(
        email_template("#CROSS_BORDER# Report for #INCIDENT_ID#", "<p>#CROSS_BORDER# A report was submitted.</p>"),
        EmailContext(incident),
    )

    assert subject == f"{CROSS_BORDER_MARKER} Report for {incident.incident_id}"
    assert CROSS_BORDER_MARKER in body


@pytest.mark.django_db
def test_an_empty_cross_border_marker_leaves_no_spacing_in_the_subject(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "No")

    subject, _body = render_notification(email_template("#CROSS_BORDER# Report  for #INCIDENT_ID#"), EmailContext(incident))

    assert subject == f"Report for {incident.incident_id}"


@pytest.mark.django_db
def test_a_template_without_the_placeholder_is_left_as_written(incident):
    designate_cross_border_question()
    answer_cross_border(incident, "Yes")

    subject, body = render_notification(email_template("Report for #INCIDENT_ID#"), EmailContext(incident))

    assert subject == f"Report for {incident.incident_id}"
    assert CROSS_BORDER_MARKER not in body


@pytest.mark.django_db
def test_the_cross_border_marker_follows_the_instance_language(incident, settings):
    """An operator submitting in English on a French instance must not get an English marker in a French subject."""
    settings.LANGUAGE_CODE = "fr"
    with override("fr"):
        if str(_("Cross-border")) == "Cross-border":
            pytest.skip("French catalogue is not compiled; run manage.py compilemessages")
    designate_cross_border_question()
    answer_cross_border(incident, "Yes")

    with override("en"):
        subject, _body = render_notification(email_template("#CROSS_BORDER# Report"), EmailContext(incident))

    assert subject == "[Transfrontalier] Report"


@pytest.mark.django_db
def test_the_body_marks_each_language_section_in_its_own_language(incident):
    with override("fr"):
        if str(_("Cross-border")) == "Cross-border":
            pytest.skip("French catalogue is not compiled; run manage.py compilemessages")
    designate_cross_border_question()
    answer_cross_border(incident, "Yes")

    _subject, body = render_notification(email_template("Report", "<p>#CROSS_BORDER#</p>"), EmailContext(incident))

    for marker in ("[Cross-border]", "[Transfrontalier]", "[Grenzüberschreitend]", "[Grensoverschrijdend]"):
        assert marker in body


# --- the placeholder help dialog on the change form -------------------------------------------


@pytest.fixture
def email_change_form(otp_client, populate_incident_db):
    try:
        get_template("admin/includes/email_placeholders_help.html")
    except TemplateDoesNotExist:
        pytest.skip("theme does not provide the placeholder dialog")
    email = Email.objects.first()
    client = otp_client(User.objects.get(email="regadmin@reg1.lu"))
    return client.get(f"/admin/incidents/email/{email.pk}/change/")


@pytest.mark.django_db
def test_the_change_form_offers_a_button_opening_the_placeholder_dialog(email_change_form):
    content = email_change_form.content.decode()
    assert "data-placeholders-help-open" in content
    assert '<dialog id="email-placeholders-help"' in content


@pytest.mark.django_db
def test_the_dialog_lists_every_registered_placeholder(email_change_form):
    content = email_change_form.content.decode()
    for placeholder in INCIDENT_EMAIL_PLACEHOLDERS:
        assert placeholder.token in content


@pytest.mark.django_db
def test_the_change_form_keeps_the_parler_language_tabs(email_change_form):
    rendered = [template.name for template in email_change_form.templates if template.name]
    assert "admin/parler/language_tabs.html" in rendered
