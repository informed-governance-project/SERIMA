import datetime

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from django.utils.translation import activate

from incidents.email import send_email
from incidents.models import Email
from incidents.tests.test_cross_border import (
    answer_cross_border,
    designate_cross_border_question,
)

MARKER = "[Cross-border]"
ANSWER_YES = "Yes"
ANSWER_NO = "No"


def prepare_email(subject="Report submitted for #INCIDENT_ID#", content="A report was submitted."):
    """Reuse a fixture email.

    The fixtures insert emails with explicit primary keys without advancing the
    sequence, so creating one here collides on the id.
    """
    email = Email.objects.first()
    email.set_current_language("en")
    email.subject = subject
    email.content = content
    email.save()
    return email


def send(incident, subject="#CROSS_BORDER# Report submitted for #INCIDENT_ID#", content="A report was submitted."):
    mail.outbox = []
    send_email(prepare_email(subject, content), incident, send_to_observers=True)
    return mail.outbox[0]


@pytest.mark.django_db
def test_placeholder_renders_nothing_without_a_designated_question(populate_incident_db):
    """An instance that has configured nothing sees no marker."""
    activate("en")
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now())

    assert MARKER not in send(incident).subject


@pytest.mark.django_db
def test_placeholder_is_left_alone_in_an_untouched_template(populate_incident_db):
    """A regulator who does not ask for the marker sees the subject unchanged.

    This is the difference with marking every message automatically: the
    platform adds nothing to a template that does not carry the placeholder.
    """
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now())

    message = send(incident, subject="Report submitted for #INCIDENT_ID#")

    assert MARKER not in message.subject
    assert message.subject.startswith("Report submitted for ")


@pytest.mark.django_db
def test_cross_border_incident_is_marked_in_the_subject(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now())

    assert send(incident).subject.startswith(MARKER)


@pytest.mark.django_db
def test_cross_border_incident_is_marked_in_the_body(populate_incident_db):
    """The same placeholder works in the content, not only in the subject."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now())

    message = send(incident, content="A report was submitted. #CROSS_BORDER#")

    assert MARKER in message.body


@pytest.mark.django_db
def test_other_incidents_render_an_empty_marker(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_NO, timezone.now())

    assert MARKER not in send(incident).subject


@pytest.mark.django_db
def test_incident_without_any_report_renders_an_empty_marker(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]

    assert MARKER not in send(incident).subject


@pytest.mark.django_db
def test_latest_report_decides(populate_incident_db):
    """A final report correcting the answer to "no" removes the marker."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now() - datetime.timedelta(days=2))
    assert send(incident).subject.startswith(MARKER)

    answer_cross_border(incident, ANSWER_NO, timezone.now())
    assert MARKER not in send(incident).subject


@pytest.mark.django_db
def test_late_switch_to_cross_border_is_picked_up(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_NO, timezone.now() - datetime.timedelta(days=2))
    assert MARKER not in send(incident).subject

    answer_cross_border(incident, ANSWER_YES, timezone.now())
    assert send(incident).subject.startswith(MARKER)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="fr")
def test_subject_marker_follows_the_instance_language(populate_incident_db):
    """The subject is taken in the instance language; the marker follows it.

    The language active when the send is triggered is deliberately a different
    one, which is what happens when an operator submits a report in English on
    a French instance.
    """
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_YES, timezone.now())

    assert send(incident).subject.startswith("[Transfrontalier]")


@pytest.mark.django_db
def test_empty_marker_leaves_no_spacing_artefact(populate_incident_db):
    """An empty placeholder must not leave the space its template wrote around it."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, ANSWER_NO, timezone.now())

    subject = send(incident).subject

    assert subject == subject.strip()
    assert "  " not in subject


@pytest.mark.django_db
def test_recipients_are_unchanged(populate_incident_db):
    """The marker is text; it must not move anybody in or out."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]

    before = send(incident).bcc

    answer_cross_border(incident, ANSWER_YES, timezone.now())
    after = send(incident).bcc

    assert before == after
