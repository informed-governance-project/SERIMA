import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils.translation import activate

from securityobjectives.models import (
    Domain,
    MaturityLevel,
    SecurityMeasure,
    SecurityObjective,
    SecurityObjectivesInStandard,
    Standard,
    StandardAnswer,
    StandardAnswerGroup,
)


@pytest.mark.django_db
def test_so_elements_in_db(populate_so_db):
    """
    Check if objects are present in DB
    """
    activate("en")
    assert Standard.objects.count() == 1
    assert MaturityLevel.objects.count() == 4
    assert Domain.objects.count() == 8
    assert SecurityMeasure.objects.count() == 174
    assert SecurityObjective.objects.count() == 29
    assert SecurityObjectivesInStandard.objects.count() == 29
    assert StandardAnswer.objects.count() == 1
    assert StandardAnswerGroup.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_duplicate_answers_are_deduplicated_before_unique_constraints_are_added():
    """Keep the lowest duplicate ID during migration, then enforce uniqueness."""
    migrate_from = [("securityobjectives", "0040_alter_securityobjectivestatus_status")]
    migrate_to = [("securityobjectives", "0041_deduplicate_answers_and_add_unique_constraints")]
    executor = MigrationExecutor(connection)
    executor.migrate(migrate_from)
    old_apps = executor.loader.project_state(migrate_from).apps

    StandardAnswerGroup = old_apps.get_model("securityobjectives", "StandardAnswerGroup")
    StandardAnswer = old_apps.get_model("securityobjectives", "StandardAnswer")
    SecurityObjective = old_apps.get_model("securityobjectives", "SecurityObjective")
    SecurityMeasure = old_apps.get_model("securityobjectives", "SecurityMeasure")
    SecurityMeasureAnswer = old_apps.get_model("securityobjectives", "SecurityMeasureAnswer")
    SecurityObjectiveStatus = old_apps.get_model("securityobjectives", "SecurityObjectiveStatus")

    group = StandardAnswerGroup.objects.create(group_id="MIGRATION-TEST")
    standard_answer = StandardAnswer.objects.create(
        group=group,
        year_of_submission=2026,
    )
    security_objective = SecurityObjective.objects.create(unique_code="MIGRATION-TEST")
    security_measure = SecurityMeasure.objects.create(security_objective=security_objective)

    kept_measure_answer = SecurityMeasureAnswer.objects.create(
        standard_answer=standard_answer,
        security_measure=security_measure,
        justification="oldest",
        review_comment="",
    )
    SecurityMeasureAnswer.objects.create(
        standard_answer=standard_answer,
        security_measure=security_measure,
        justification="newest",
        review_comment="",
    )
    kept_objective_status = SecurityObjectiveStatus.objects.create(
        standard_answer=standard_answer,
        security_objective=security_objective,
    )
    SecurityObjectiveStatus.objects.create(
        standard_answer=standard_answer,
        security_objective=security_objective,
        status="PASS",
    )

    # The loader still records 0041 as applied from before the rollback, so without a
    # rebuild the forward plan is empty and the migration under test never runs.
    executor.loader.build_graph()
    executor.migrate(migrate_to)
    new_apps = executor.loader.project_state(migrate_to).apps
    SecurityMeasureAnswer = new_apps.get_model("securityobjectives", "SecurityMeasureAnswer")
    SecurityObjectiveStatus = new_apps.get_model("securityobjectives", "SecurityObjectiveStatus")

    assert list(SecurityMeasureAnswer.objects.values_list("id", flat=True)) == [kept_measure_answer.id]
    assert list(SecurityObjectiveStatus.objects.values_list("id", flat=True)) == [kept_objective_status.id]

    with pytest.raises(IntegrityError), transaction.atomic():
        SecurityMeasureAnswer.objects.create(
            standard_answer_id=standard_answer.id,
            security_measure_id=security_measure.id,
            justification="duplicate",
            review_comment="",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        SecurityObjectiveStatus.objects.create(
            standard_answer_id=standard_answer.id,
            security_objective_id=security_objective.id,
        )
