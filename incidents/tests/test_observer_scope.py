"""Which incidents an observer is entitled to see.

These two used to be Observer methods, which forced governanceplatform.models to import
Incident. The seeded observer holds a sector-less rule for every regulation, so the
existing access-control tests only exercise that broadest rule.
"""

import pytest

from governanceplatform.models import ObserverRegulation
from incidents.access_control import get_observer_incidents, observer_can_access_incident


@pytest.fixture
def observer(populate_incident_db):
    """The seeded observer, stripped of its rules so each test sets the ones deciding access."""
    observer = populate_incident_db["observers"][0]
    observer.observerregulation_set.all().delete()
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
def test_a_rule_without_sectors_covers_every_sector_of_its_regulation(observer, incident):
    _scope_to(observer, incident, sectors=[])

    assert observer_can_access_incident(observer, incident) is True


@pytest.mark.django_db()
def test_a_rule_without_sectors_covers_asectorial_incidents(observer, populate_incident_db):
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    assert not incident.affected_sectors.exists()
    _scope_to(observer, incident, sectors=[])

    assert observer_can_access_incident(observer, incident) is True


@pytest.mark.django_db()
def test_a_rule_with_sectors_excludes_asectorial_incidents(observer, populate_incident_db):
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    _scope_to(observer, incident, sectors=populate_incident_db["sectors"])

    assert observer_can_access_incident(observer, incident) is False


@pytest.mark.django_db()
def test_a_rule_without_sectors_is_limited_to_its_regulation(observer, incident, populate_incident_db):
    other = next(r for r in populate_incident_db["regulations"] if r != incident.sector_regulation.regulation)
    ObserverRegulation.objects.create(observer=observer, regulation=other)

    assert observer_can_access_incident(observer, incident) is False


@pytest.mark.django_db()
def test_incidents_without_a_sector_regulation_are_never_included(observer, incident):
    """sector_regulation is SET_NULL, and an orphaned incident has no regulation to match."""
    _scope_to(observer, incident, sectors=[])
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
