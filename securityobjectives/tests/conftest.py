import pytest
from django.utils import timezone
from django.utils.translation import activate

import governanceplatform.tests.conftest as gp_conftest
from conftest import import_from_json
from securityobjectives.models import (
    Domain,
    MaturityLevel,
    SecurityMeasure,
    SecurityMeasureAnswer,
    SecurityObjective,
    SecurityObjectivesInStandard,
    SecurityObjectiveStatus,
    Standard,
    StandardAnswer,
    StandardAnswerGroup,
)
from securityobjectives.tests.so_data import (
    domains,
    levels,
    sms,
    sos,
    standard,
)


@pytest.fixture
def populate_db(db):
    # on rewrap fixture to expose localy and don't get flake error
    return gp_conftest.populate_db.__wrapped__(db)


@pytest.fixture
def populate_so_db(populate_db, create_standard_answer_group, create_standard_answer):
    """
    Populate the DB
    """
    # Force default language for translatable
    activate("en")

    # populate a standard
    populate_db["so_standard"] = import_from_json(Standard, standard, True, False)
    populate_db["so_maturity_level"] = import_from_json(MaturityLevel, levels, True, False)
    populate_db["so_domain"] = import_from_json(Domain, domains, True, False)
    populate_db["so_security_objectives"] = import_from_json(SecurityObjective, sos, True, False)
    populate_db["so_security_measures"] = import_from_json(SecurityMeasure, sms, True, False)
    # link SOs into standard
    for i, so in enumerate(populate_db["so_security_objectives"]):
        std = populate_db["so_standard"][0]
        SecurityObjectivesInStandard.objects.create(standard=std, security_objective=so, position=i)
    sags = []
    sas = []
    users = populate_db["users"]
    standards = populate_db["so_standard"]
    # operator admin
    user = next((u for u in users if u.email == "opadmin@com1.lu"), None)
    sag = create_standard_answer_group(company=user.companies.first())
    sa = create_standard_answer(
        standard=standards[0],
        submitter_user=user,
        submitter_company=user.companies.first(),
        creator_name="opadmin",
        creator_company_name="com1",
        sectors=populate_db["sectors"],
        group=sag,
    )
    sas.append(sa)
    sags.append(sag)
    populate_db["sas"] = sas
    populate_db["sags"] = sags
    for sa in sas:
        for sm in populate_db["so_security_measures"]:
            SecurityMeasureAnswer.objects.create(
                security_measure_notification_date=timezone.now(),
                standard_answer=sa,
                security_measure=sm,
            )
        for so in sa.standard.security_objectives.all():
            SecurityObjectiveStatus.objects.create(
                security_objective=so,
                standard_answer=sa,
                status="NOT_REVIEWED",
            )
    return populate_db


@pytest.fixture
def security_measure_from_another_standard(populate_so_db):
    regulator = populate_so_db["regulators"][0]
    other_standard = Standard(
        regulator=regulator,
        regulation=populate_so_db["regulations"][0],
    )
    other_standard.set_current_language("en")
    other_standard.label = "Other standard"
    other_standard.description = ""
    other_standard.save()

    other_domain = Domain(
        position=1,
        standard=other_standard,
        creator=regulator,
        creator_name=str(regulator),
    )
    other_domain.set_current_language("en")
    other_domain.label = "Other domain"
    other_domain.save()

    other_objective = SecurityObjective(
        unique_code="OTHER-SO",
        domain=other_domain,
        creator=regulator,
        creator_name=str(regulator),
    )
    other_objective.set_current_language("en")
    other_objective.objective = "Other objective"
    other_objective.description = "Other objective description"
    other_objective.save()
    SecurityObjectivesInStandard.objects.create(
        standard=other_standard,
        security_objective=other_objective,
    )

    other_level = MaturityLevel(
        level=1,
        standard=other_standard,
        creator=regulator,
        creator_name=str(regulator),
    )
    other_level.set_current_language("en")
    other_level.label = "Other level"
    other_level.save()

    other_measure = SecurityMeasure(
        security_objective=other_objective,
        maturity_level=other_level,
        position=1,
        creator=regulator,
        creator_name=str(regulator),
    )
    other_measure.set_current_language("en")
    other_measure.description = "Other measure"
    other_measure.evidence = "Other evidence"
    other_measure.save()

    return other_measure


@pytest.fixture
def create_standard_answer_group():
    """
    Fixture to create a standard answer group
    """

    def _create_standard_answer_group(
        company,
        group_id="XXXXXXXXXX-FFFFFFFFFF-SSS-SSS-NNNN-YYYY",
    ):
        return StandardAnswerGroup.objects.create(
            company=company,
            notification_date=timezone.now(),
            group_id=group_id,
        )

    return _create_standard_answer_group


@pytest.fixture
def create_standard_answer():
    """
    Fixture to create a standard answer
    """

    def _create_standard_answer(
        standard,
        submitter_user,
        submitter_company,
        creator_name,
        creator_company_name,
        sectors,
        group,
        status="DELIV",
        year_of_submission=2026,
        review_comment=None,
    ):
        sa = StandardAnswer.objects.create(
            standard=standard,
            submitter_user=submitter_user,
            submitter_company=submitter_company,
            creator_name=creator_name,
            creator_company_name=creator_company_name,
            group=group,
            creation_date=timezone.now(),
            last_update=timezone.now(),
            submit_date=timezone.now(),
            status=status,
            year_of_submission=year_of_submission,
            review_comment=review_comment,
        )
        if sectors:
            sa.sectors.set(sectors)
        sa.save()
        return sa

    return _create_standard_answer
