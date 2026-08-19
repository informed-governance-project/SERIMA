import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import activate

from governanceplatform.models import ApplicationConfig
from incidents.filters import ObserverIncidentFilter
from incidents.helpers import (
    CROSS_BORDER_POSITIVE_ANSWER_KEY,
    CROSS_BORDER_QUESTION_REFERENCE_KEY,
    annotate_cross_border_impact,
)
from incidents.models import (
    Answer,
    Incident,
    IncidentWorkflow,
    PredefinedAnswer,
    QuestionOptions,
    ReportTimeline,
    Workflow,
)

CROSS_BORDER_QUESTION_REFERENCE = "1"


def designate_cross_border_question(positive_answer=None):
    ApplicationConfig.objects.create(
        key=CROSS_BORDER_QUESTION_REFERENCE_KEY,
        value=CROSS_BORDER_QUESTION_REFERENCE,
    )
    if positive_answer is not None:
        ApplicationConfig.objects.create(
            key=CROSS_BORDER_POSITIVE_ANSWER_KEY,
            value=positive_answer,
        )


def answer_cross_border(incident, predefined_answer_label, submitted_at):
    """Submit a report answering the cross-border question."""
    question_options = QuestionOptions.objects.filter(question__reference=CROSS_BORDER_QUESTION_REFERENCE).first()
    incident_workflow = IncidentWorkflow.objects.create(
        incident=incident,
        workflow=Workflow.objects.first(),
        timestamp=submitted_at,
        # save_answers() always creates one, and replace_email_variables()
        # dereferences it, so a report without a timeline is not a realistic
        # fixture.
        report_timeline=ReportTimeline.objects.create(incident_detection_date=submitted_at),
    )
    answer = Answer.objects.create(
        incident_workflow=incident_workflow,
        question_options=question_options,
        timestamp=submitted_at,
    )
    answer.predefined_answers.set(
        PredefinedAnswer.objects.filter(
            question=question_options.question,
            translations__predefined_answer=predefined_answer_label,
        )
    )
    return incident_workflow


def is_flagged(incident):
    return annotate_cross_border_impact(Incident.objects.filter(pk=incident.pk)).first().is_cross_border_impact


@pytest.mark.django_db
def test_no_designated_question_flags_nothing(populate_incident_db):
    """Without an application config, every incident reads as not cross-border."""
    activate("en")
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "Yes", timezone.now())

    assert is_flagged(incident) is False


@pytest.mark.django_db
def test_positive_answer_is_flagged(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "Yes", timezone.now())

    assert is_flagged(incident) is True


@pytest.mark.django_db
def test_negative_answer_is_not_flagged(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "No", timezone.now())

    assert is_flagged(incident) is False


@pytest.mark.django_db
def test_incident_without_answer_is_not_flagged(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]

    assert is_flagged(incident) is False


@pytest.mark.django_db
def test_latest_report_wins(populate_incident_db):
    """A later report correcting the answer to "no" clears the flag."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    early_warning = timezone.now() - datetime.timedelta(days=2)
    answer_cross_border(incident, "Yes", early_warning)
    assert is_flagged(incident) is True

    answer_cross_border(incident, "No", timezone.now())
    assert is_flagged(incident) is False


@pytest.mark.django_db
def test_later_report_raises_the_flag(populate_incident_db):
    """An incident that turns out to be cross-border later is picked up."""
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "No", timezone.now() - datetime.timedelta(days=2))
    assert is_flagged(incident) is False

    answer_cross_border(incident, "Yes", timezone.now())
    assert is_flagged(incident) is True


@pytest.mark.django_db
def test_other_incidents_are_untouched(populate_incident_db):
    activate("en")
    designate_cross_border_question()
    flagged_incident, other_incident = populate_incident_db["incidents"][:2]
    answer_cross_border(flagged_incident, "Yes", timezone.now())

    assert is_flagged(flagged_incident) is True
    assert is_flagged(other_incident) is False


@pytest.mark.django_db
def test_positive_answer_label_is_configurable(populate_incident_db):
    """A deployment whose questionnaire says "Oui" configures it."""
    activate("en")
    designate_cross_border_question(positive_answer="No")
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "No", timezone.now())

    assert is_flagged(incident) is True


@pytest.fixture
def observer_client(otp_client, populate_incident_db):
    """The seeded observer user, with the second factor satisfied."""
    user = next(u for u in populate_incident_db["users"] if u.email == "obsadm@cert1.lu")
    return otp_client(user)


@pytest.mark.django_db
def test_the_observer_list_view_carries_the_annotation(observer_client, populate_incident_db):
    """The view is what wires the annotation and the filter to the observer role.

    Covering the annotation alone leaves that wiring free to be rewritten from
    under it, which is exactly what a refactor of the observer scoping does.
    """
    activate("en")
    designate_cross_border_question()
    incident = populate_incident_db["incidents"][0]
    answer_cross_border(incident, "Yes", timezone.now())

    response = observer_client.get(reverse("incidents"))

    assert response.status_code == 200
    listed = {i.incident_id: i for i in response.context["incidents"].object_list}
    assert incident.incident_id in listed
    assert listed[incident.incident_id].is_cross_border_impact is True
    assert isinstance(response.context["filter"], ObserverIncidentFilter)


@pytest.mark.django_db
def test_the_observer_list_view_can_filter_on_it(observer_client, populate_incident_db):
    activate("en")
    designate_cross_border_question()
    flagged, plain = populate_incident_db["incidents"][0], populate_incident_db["incidents"][1]
    answer_cross_border(flagged, "Yes", timezone.now())
    answer_cross_border(plain, "No", timezone.now())

    response = observer_client.get(reverse("incidents"), {"cross_border_impact": "true"})

    listed = {i.incident_id for i in response.context["incidents"].object_list}
    assert flagged.incident_id in listed
    assert plain.incident_id not in listed
