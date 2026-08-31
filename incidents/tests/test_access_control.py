"""Unit checks for the incident permission predicates.

The integration coverage lives in test_incidents_views.py, which drives these against
real users and incidents; these pin the individual branches.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from incidents import access_control


def test_can_access_incident_for_incident_owner(monkeypatch):
    """Allow an incident user to access an incident they own."""
    user = object()
    incident = SimpleNamespace(id=7)
    monkeypatch.setattr(access_control, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(access_control, "is_user_operator", lambda user: False)
    monkeypatch.setattr(access_control, "is_observer_user", lambda user: False)
    monkeypatch.setattr(access_control, "is_observer_user_viewing_all_incident", lambda user: False)
    monkeypatch.setattr(access_control, "user_in_group", lambda user, group: group == "IncidentUser")
    incident_filter = MagicMock()
    incident_filter.exists.return_value = True
    monkeypatch.setattr(access_control.Incident.objects, "filter", lambda **kwargs: incident_filter)

    assert access_control.can_access_incident(user, incident) is True


def test_can_access_incident_rejects_non_owner(monkeypatch):
    """Reject an incident user who does not own the incident."""
    user = object()
    incident = SimpleNamespace(id=7)
    monkeypatch.setattr(access_control, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(access_control, "is_user_operator", lambda user: False)
    monkeypatch.setattr(access_control, "is_observer_user", lambda user: False)
    monkeypatch.setattr(access_control, "is_observer_user_viewing_all_incident", lambda user: False)
    monkeypatch.setattr(access_control, "user_in_group", lambda user, group: group == "IncidentUser")
    incident_filter = MagicMock()
    incident_filter.exists.return_value = False
    monkeypatch.setattr(access_control.Incident.objects, "filter", lambda **kwargs: incident_filter)

    assert access_control.can_access_incident(user, incident) is False


def test_can_create_incident_report_rejects_unrelated_user(monkeypatch):
    """Reject report creation when the user has no relationship to the incident."""
    monkeypatch.setattr(access_control, "user_in_group", lambda user, group: False)
    monkeypatch.setattr(access_control, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(access_control, "is_user_operator", lambda user: False)

    assert access_control.can_create_incident_report(object(), SimpleNamespace(contact_user=None)) is False


def test_can_edit_incident_report_for_matching_regulator_admin(monkeypatch):
    """Allow a regulator administrator to edit an incident for their regulator."""
    regulator = object()
    user = SimpleNamespace(regulators=SimpleNamespace(first=lambda: regulator))
    incident = SimpleNamespace(contact_user=None, sector_regulation=SimpleNamespace(regulator=regulator))
    monkeypatch.setattr(access_control, "user_in_group", lambda user, group: group == "RegulatorAdmin")
    monkeypatch.setattr(access_control, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(access_control, "is_user_operator", lambda user: False)

    assert access_control.can_edit_incident_report(user, incident) is True


def test_can_edit_incident_report_grants_whatever_creation_grants(monkeypatch):
    """Editing delegates to creation, so whoever may file a report may also edit it."""
    monkeypatch.setattr(access_control, "can_create_incident_report", lambda user, incident, company_id: True)

    assert access_control.can_edit_incident_report(object(), SimpleNamespace(sector_regulation=None)) is True
