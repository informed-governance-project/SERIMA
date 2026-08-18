"""Which incidents an observer is entitled to see.

These two used to be Observer methods, which forced governanceplatform.models to import
Incident. The seeded observer receives every incident, so the rule-driven path below is
not reachable through the existing access-control tests.
"""

import pytest

from governanceplatform.models import ObserverRegulation
from incidents.access_control import get_observer_incidents, observer_can_access_incident


@pytest.fixture
def observer(populate_incident_db):
    """The seeded observer, narrowed so its regulation rules actually decide access."""
    observer = populate_incident_db["observers"][0]
    observer.is_receiving_all_incident = False
    observer.save()
    return observer


@pytest.fixture
def incident(populate_incident_db):
    """The seeded incident, given a sector.

    It is seeded asectorial, and an observer rule matches on affected_sectors, so an
    incident with none can never satisfy one.
    """
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    incident.affected_sectors.add(populate_incident_db["sectors"][0])
    return incident


def _scope_to(observer, incident, sectors=None):
    rule = ObserverRegulation.objects.create(
        observer=observer,
        regulation=incident.sector_regulation.regulation,
        incident_rule={},
    )
    rule.sectors.set(sectors if sectors is not None else incident.affected_sectors.all())
    return rule


@pytest.mark.django_db()
def test_an_observer_receiving_everything_gets_every_regulated_incident(populate_incident_db, incident):
    observer = populate_incident_db["observers"][0]
    assert observer.is_receiving_all_incident is True

    assert incident in get_observer_incidents(observer)


@pytest.mark.django_db()
def test_incidents_without_a_sector_regulation_are_never_included(populate_incident_db, incident):
    """sector_regulation is SET_NULL, and an orphaned incident has no regulation to match."""
    observer = populate_incident_db["observers"][0]
    incident.sector_regulation = None
    incident.save()

    assert incident not in get_observer_incidents(observer)


@pytest.mark.django_db()
def test_an_observer_without_regulations_gets_nothing(observer):
    assert not get_observer_incidents(observer).exists()


@pytest.mark.django_db()
def test_a_regulation_rule_matching_the_incident_grants_access(observer, incident):
    _scope_to(observer, incident)

    assert observer_can_access_incident(observer, incident) is True


@pytest.mark.django_db()
def test_a_regulation_rule_for_other_sectors_denies_access(observer, incident, populate_incident_db):
    covered = set(incident.affected_sectors.values_list("id", flat=True))
    other = [s for s in populate_incident_db["sectors"] if s.id not in covered]
    assert other, "fixture must supply a sector the incident does not have"
    _scope_to(observer, incident, sectors=other)

    assert observer_can_access_incident(observer, incident) is False


@pytest.mark.django_db()
def test_an_exclude_condition_removes_the_incidents_company(observer, incident, populate_incident_db):
    """A rule may exclude incidents whose company holds a given entity category."""
    category = populate_incident_db["entity_categories"][0]
    incident.company.entity_categories.add(category)
    rule = _scope_to(observer, incident)
    rule.incident_rule = {"conditions": [{"include": [], "exclude": [category.code]}]}
    rule.save()

    assert observer_can_access_incident(observer, incident) is False

    rule.incident_rule = {"conditions": [{"include": [category.code], "exclude": []}]}
    rule.save()

    assert observer_can_access_incident(observer, incident) is True
