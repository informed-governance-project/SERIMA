from datetime import timedelta

import pytest
from django.utils import timezone
from django.utils.translation import override

from governanceplatform.models import User
from incidents.email import INCIDENT_EMAIL_PLACEHOLDERS, EmailContext, replace_email_variables
from incidents.models import Email, IncidentWorkflow, ReportTimeline, Workflow


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


# --- the placeholder help dialog on the change form -------------------------------------------


@pytest.fixture
def email_change_form(otp_client, populate_incident_db):
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
    assert "admin/incidents/email/change_form.html" in rendered
    assert "admin/parler/language_tabs.html" in rendered
