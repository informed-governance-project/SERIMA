"""Who may read, create and edit a given incident report."""

from governanceplatform.helpers import (
    is_observer_user,
    is_observer_user_viewing_all_incident,
    is_user_operator,
    is_user_regulator,
    user_in_group,
)
from governanceplatform.models import User  # noqa: TC001

from .models import Incident


def can_access_incident(user: User, incident: Incident, company_id: int | None = None) -> bool:
    # if it's regulator incident
    if (
        is_user_regulator(user)
        and Incident.objects.filter(
            pk=incident.id,
            regulator=user.regulators.first(),
        ).exists()
    ):
        return True

    # RegulatorUser can access only incidents from accessible sectors.
    if (
        user_in_group(user, "RegulatorUser")
        and Incident.objects.filter(pk=incident.id, sector_regulation__regulator=user.regulators.first()).exists()
    ):
        return incident.affected_sectors.filter(id__in=user.get_sectors().all()).exists()

    # RegulatorAdmin can access only incidents from accessible regulators.
    if (
        user_in_group(user, "RegulatorAdmin")
        and Incident.objects.filter(pk=incident.id, sector_regulation__regulator=user.regulators.first()).exists()
    ):
        return True
    # OperatorAdmin/User can access only incidents related to selected company.
    # company_id is None for non-operator roles; without the guard the lookups
    # would become IS NULL and match company-less incidents.
    if (
        company_id
        and is_user_operator(user)
        and user.companyuser_set.filter(company__id=company_id, approved=True).exists()
        and Incident.objects.filter(pk=incident.id, company__id=company_id).exists()
    ):
        return True
    # IncidentUser can access their reports.
    if user_in_group(user, "IncidentUser") and Incident.objects.filter(pk=incident.id, contact_user=user).exists():
        return True
    # ObserverUser access all incident if he is in a observer who can access all incident.
    if is_observer_user_viewing_all_incident(user):
        return True
    if is_observer_user(user):
        incident_lists = user.observers.first().get_incidents()
        if incident in incident_lists:
            return True

    return False


# check if the user is allowed to create an incident_workflow
def can_create_incident_report(user: User, incident: Incident, company_id: int | None = None) -> bool:
    # if it's incident user
    if user_in_group(user, "IncidentUser") and Incident.objects.filter(pk=incident.id, contact_user=user).exists():
        return True

    # if it's the incident of the user he can create
    if company_id and incident.contact_user == user and user.companyuser_set.filter(company__id=company_id, approved=True).exists():
        return True

    # if it's regulator incident
    if (
        is_user_regulator(user)
        and Incident.objects.filter(
            pk=incident.id,
            regulator=user.regulators.first(),
        ).exists()
    ):
        return True

    # OperatorAdmin/User can create only incidents related to selected company.
    if (
        company_id
        and is_user_operator(user)
        and user.companyuser_set.filter(company__id=company_id, approved=True).exists()
        and Incident.objects.filter(pk=incident.id, company__id=company_id).exists()
    ):
        return True

    return False


# check if the user is allowed to edit an incident_workflow
# for regulators to add message
def can_edit_incident_report(user: User, incident: Incident, company_id: int | None = None) -> bool:
    # Whoever may file a report may also edit it. Editing additionally lets the regulator
    # responsible for the incident's sector regulation add a message.
    if can_create_incident_report(user, incident, company_id):
        return True

    # Deleting a SectorRegulation leaves incidents behind (SET_NULL); they have no
    # regulator to match, so the remaining regulator branches cannot grant access.
    sector_regulation = incident.sector_regulation
    if sector_regulation is None:
        return False

    # if he is the regulator admin of the incident need to be link to his regulator
    if user_in_group(user, "RegulatorAdmin") and sector_regulation.regulator == user.regulators.first():
        return True
    # if he is the regulator user of the incident, he need to have the sectors
    if user_in_group(user, "RegulatorUser") and sector_regulation.regulator == user.regulators.first():
        return incident.affected_sectors.filter(id__in=user.get_sectors().all()).exists()

    return False
