"""Whether a security-objectives object still has answers referencing it.

can_change_or_delete_obj asks each object this via is_in_use() to decide whether its
creator may still edit or delete it, so a method that answered from the wrong table
would silently unlock objects operators have already answered against.
"""

import pytest

from governanceplatform.helpers import can_change_or_delete_obj
from governanceplatform.models import User
from securityobjectives.models import (
    MaturityLevel,
    SecurityMeasureAnswer,
    SecurityObjectiveEmail,
    StandardAnswer,
)


class _CollectingMessages:
    """Stand-in for the message store MessageMiddleware normally attaches."""

    def __init__(self):
        self.added = []

    def add(self, level, message, extra_tags=""):
        self.added.append((level, message))


@pytest.fixture
def answered(populate_so_db):
    """One answered security measure, with the objective, domain and standard above it."""
    answer = SecurityMeasureAnswer.objects.select_related("security_measure__security_objective__domain").first()
    measure = answer.security_measure
    return {
        "standard": populate_so_db["sas"][0].standard,
        "domain": measure.security_objective.domain,
        "security_objective": measure.security_objective,
        "security_measure": measure,
    }


@pytest.mark.django_db()
def test_standard_is_in_use_while_an_answer_references_it(answered):
    standard = answered["standard"]
    assert standard.is_in_use() is True

    StandardAnswer.objects.filter(standard=standard).delete()

    assert standard.is_in_use() is False


@pytest.mark.django_db()
def test_security_measure_is_in_use_while_an_answer_references_it(answered):
    measure = answered["security_measure"]
    assert measure.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure=measure).delete()

    assert measure.is_in_use() is False


@pytest.mark.django_db()
def test_security_objective_is_in_use_through_its_measures(answered):
    security_objective = answered["security_objective"]
    assert security_objective.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective=security_objective).delete()

    assert security_objective.is_in_use() is False


@pytest.mark.django_db()
def test_domain_is_in_use_through_its_objectives(answered):
    domain = answered["domain"]
    assert domain.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective__domain=domain).delete()

    assert domain.is_in_use() is False


def test_maturity_levels_are_never_in_use():
    """Maturity levels are referenced by label, so answers never lock them."""
    assert MaturityLevel().is_in_use() is False


def test_email_templates_are_never_in_use():
    """Email templates stay editable so the wording can be revised."""
    assert SecurityObjectiveEmail().is_in_use() is False


@pytest.mark.django_db()
def test_can_change_or_delete_obj_refuses_a_domain_that_is_in_use(answered, rf):
    """The creator of an answered domain still may not change it."""
    domain = answered["domain"]
    creator_user = User.objects.filter(regulators=domain.creator).first()
    assert creator_user is not None

    request = rf.get("/")
    request.user = creator_user
    request._messages = _CollectingMessages()

    assert can_change_or_delete_obj(request, domain) is False

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective__domain=domain).delete()

    request = rf.get("/")
    request.user = creator_user
    request._messages = _CollectingMessages()

    assert can_change_or_delete_obj(request, domain) is True
