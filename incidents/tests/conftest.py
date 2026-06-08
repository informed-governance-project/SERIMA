import pytest
from django.utils import timezone
from django.utils.translation import activate

import governanceplatform.tests.conftest as gp_conftest
from conftest import import_from_json
from governanceplatform.helpers import (
    is_user_operator,
    is_user_regulator,
)
from governanceplatform.settings import TIME_ZONE
from incidents.models import (
    Email,
    Impact,
    Incident,
    IncidentWorkflow,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulation,
    SectorRegulationWorkflow,
    Workflow,
)
from incidents.tests.incidents_data import (
    emails,
    impacts,
    predefined_answers,
    question_category,
    question_category_option,
    question_options,
    questions,
    reports,
    workflows,
    workflows_reports,
)


@pytest.fixture
def populate_db(db):
    # on rewrap fixture to expose localy and don't get flake error
    return gp_conftest.populate_db.__wrapped__(db)


@pytest.fixture
def populate_incident_db(populate_db, create_incident):
    """
    Populate the DB
    """
    # Force default language for translatable
    activate("en")

    # Create emails
    populate_db["incidents_email"] = import_from_json(Email, emails)

    # Create questions
    populate_db["incidents_questions"] = import_from_json(Question, questions)
    populate_db["incidents_predefined_answers"] = import_from_json(PredefinedAnswer, predefined_answers)
    populate_db["incidents_question_category"] = import_from_json(QuestionCategory, question_category)

    # Create reports
    populate_db["incidents_question_category_options"] = import_from_json(QuestionCategoryOptions, question_category_option, True, False)
    populate_db["incidents_reports"] = import_from_json(Workflow, reports)
    populate_db["incidents_question_options"] = import_from_json(QuestionOptions, question_options, True, False)

    # Create Workflows
    populate_db["incidents_workflows"] = import_from_json(SectorRegulation, workflows, True, False)
    import_from_json(SectorRegulationWorkflow, workflows_reports, True, False)

    # Create impacts
    populate_db["incidents_impacts"] = import_from_json(Impact, impacts)

    incidents = []
    users = populate_db["users"]
    # operator admin
    user = next((u for u in users if u.email == "opadmin@com1.lu"), None)
    # asectorial workflow
    workflow = next((u for u in populate_db["incidents_workflows"] if u.id == 1), None)
    incident_operator = create_incident(
        user=user,
        workflow=workflow,
        sectors=None,
        impacts=None,
        is_significative_impact=False,
        incident_id="XXXX-SSS-SSS-0001-2005",
        incident_detection_date=timezone.now(),
    )
    incidents.append(incident_operator)

    regulator_user = next((u for u in users if u.email == "reguser@reg1.lu"), None)
    incident_regulator = create_incident(
        user=regulator_user,
        workflow=workflow,
        sectors=None,
        impacts=None,
        is_significative_impact=False,
        incident_id="RRR-SSS-SSS-0001-2005",
        incident_detection_date=timezone.now(),
    )
    incidents.append(incident_regulator)
    populate_db["incidents"] = incidents

    return populate_db


@pytest.fixture
def create_incident():
    """
    Fixture to create an incident
    """

    def _create_incident(
        user,
        workflow,
        sectors=None,
        impacts=None,
        is_significative_impact=False,
        incident_id="",
        incident_detection_date=timezone.now,
    ):
        incident = Incident.objects.create(
            incident_id=incident_id,
            incident_timezone=TIME_ZONE,
            incident_detection_date=incident_detection_date,
            company=user.companies.first() if is_user_operator(user) else None,
            regulator=user.regulators.first() if is_user_regulator(user) else None,
            contact_user=user,
            sector_regulation=workflow,
            is_significative_impact=is_significative_impact,
        )
        if sectors:
            incident.affected_sectors.set(sectors)
        if impacts:
            incident.impacts.set(impacts)
        incident.save()
        return incident

    return _create_incident


@pytest.fixture
def create_incident_report():
    """
    Fixture to create a report of an incident
    """

    def _create_incident_report(
        incident,
        report,
        impacts=None,
        comment="",
    ):
        incident_report = IncidentWorkflow.objects.create(
            incident=incident,
            report=report,
            comment=comment,
        )
        if impacts:
            incident_report.impacts.set(impacts)
        incident_report.save()
        return incident_report

    return _create_incident_report
