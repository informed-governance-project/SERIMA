import pytest

from conftest import (
    list_admin_add_urls,
    list_url_freetext_filter,
    test_get_with_otp,
)
from governanceplatform.helpers import (
    can_access_incident,
    can_create_incident_report,
    can_edit_incident_report,
    user_in_group,
)
from governanceplatform.models import RegulatorUser


@pytest.mark.django_db
def test_incident_user_access_without_2FA(client, populate_incident_db):
    """
    Verify if the incident main pages are not accessible without 2FA
    """
    users = populate_incident_db["users"]

    for user in users:
        client.force_login(user)
        url_list = list_url_freetext_filter("incidents", "admin")
        for url in url_list:
            response = client.get("/" + url)
            assert response.status_code in (
                302,
                403,
            ), f"User {user.email} should not access to the admin without 2FA"


@pytest.mark.django_db
def test_incidents_admin_roles_addition_rights(otp_client, populate_incident_db):
    """
    Test the rights of each groups on the model of incidents
    """
    users = populate_incident_db["users"]
    regulator_admin_rights = [
        "email",
        "impact",
        "sectorregulation",
        "workflow",
        "question",
        "predefinedanswer",
        "sectorregulationworkflowemail",
    ]
    authorized_users = [u for u in users if user_in_group(u, "RegulatorAdmin")]
    for u in list_admin_add_urls("incidents"):
        if any(model in u for model in regulator_admin_rights):
            url = "/" + u
            test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_pdf_download_of_operator_incident(otp_client, populate_incident_db):
    """
    Test if the PDF download is accessible to the right users
    """
    users = populate_incident_db["users"]
    incidents = populate_incident_db["incidents"]
    # operator admin
    authorized_users = [
        u
        for u in users
        if u.email == "opadmin@com1.lu"
        or u.email == "obsadm@cert1.lu"  # receive all incident
        or u.email == "opuser@com1.lu"
        or u.email == "regadmin@reg1.lu"
    ]
    # asectorial workflow
    incident = next((u for u in incidents if u.incident_id == "XXXX-SSS-SSS-0001-2005"), None)
    url = "/incidents/download-pdf/" + str(incident.id)
    test_get_with_otp(otp_client, users, authorized_users, [], url)

    # Add a sector to test RegUser see the incident
    sectors = populate_incident_db["sectors"]
    sector = next((u for u in sectors if u.acronym == "ELEC"), None)
    if sector:
        incident.affected_sectors.add(sector)
        incident.save()
        regulator_user = next((u for u in users if u.email == "reguser@reg1.lu"), None)
        ru = RegulatorUser.objects.get(user=regulator_user, regulator=regulator_user.regulators.first())
        if ru:
            url = "/incidents/download-pdf/" + str(incident.id)
            authorized_users.append(regulator_user)
            ru.sectors.add(sector)
            test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_can_access_incident_function(populate_incident_db):
    """
    Test the can_access_incident function
    """
    users = populate_incident_db["users"]
    incidents = populate_incident_db["incidents"]
    # operator admin
    authorized_users = [
        u
        for u in users
        if u.email == "opadmin@com1.lu"
        or u.email == "obsadm@cert1.lu"  # receive all incident
        or u.email == "opuser@com1.lu"
        or u.email == "regadmin@reg1.lu"
    ]
    # asectorial workflow
    incident_operator = next((u for u in incidents if u.incident_id == "XXXX-SSS-SSS-0001-2005"), None)
    incident_regulator = next((u for u in incidents if u.incident_id == "RRR-SSS-SSS-0001-2005"), None)

    for u in users:
        company = -1
        if u.companies.first() is not None:
            company = u.companies.first().id
        if u in authorized_users:
            assert can_access_incident(u, incident_operator, company) is True
        else:
            assert can_access_incident(u, incident_operator, company) is False

    # Add a sector to test RegUser see the incident
    sectors = populate_incident_db["sectors"]
    sector = next((u for u in sectors if u.acronym == "ELEC"), None)
    regulator_user = next((u for u in users if u.email == "reguser@reg1.lu"), None)

    if sector:
        incident_operator.affected_sectors.add(sector)
        incident_operator.save()
        ru = RegulatorUser.objects.get(user=regulator_user, regulator=regulator_user.regulators.first())
        if ru:
            authorized_users.append(regulator_user)
            ru.sectors.add(sector)
            for u in users:
                company = -1
                if u.companies.first() is not None:
                    company = u.companies.first().id
                if u in authorized_users:
                    assert can_access_incident(u, incident_operator, company) is True
                else:
                    assert can_access_incident(u, incident_operator, company) is False

    # emulate an incident submitted by a RegulatorUser
    authorized_users = [
        u
        for u in users
        if u.email == "obsadm@cert1.lu"  # receive all incident
        or u.email == "reguser@reg1.lu"
        or u.email == "regadmin@reg1.lu"
    ]
    for u in users:
        if u in authorized_users:
            assert can_access_incident(u, incident_regulator, -1) is True
        else:
            assert can_access_incident(u, incident_regulator, -1) is False


@pytest.mark.django_db()
def test_can_create_incident_report_function(populate_incident_db):
    """
    Test the can_create_incident_report function
    """
    users = populate_incident_db["users"]
    incidents = populate_incident_db["incidents"]
    incident_operator = next((u for u in incidents if u.incident_id == "XXXX-SSS-SSS-0001-2005"), None)
    incident_regulator = next((u for u in incidents if u.incident_id == "RRR-SSS-SSS-0001-2005"), None)
    # operator admin
    authorized_users = [u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu"]
    # operator incident
    for u in users:
        company = -1
        if u.companies.first() is not None:
            company = u.companies.first().id
        if u in authorized_users:
            assert can_create_incident_report(u, incident_operator, company) is True
        else:
            assert can_create_incident_report(u, incident_operator, company) is False

    # emulate an incident submitted by a RegulatorUser
    authorized_users = [u for u in users if u.email == "reguser@reg1.lu" or u.email == "regadmin@reg1.lu"]
    for u in users:
        if u in authorized_users:
            assert can_create_incident_report(u, incident_regulator, -1) is True
        else:
            assert can_create_incident_report(u, incident_regulator, -1) is False


@pytest.mark.django_db()
def test_can_edit_incident_report_function(populate_incident_db):
    """
    Test the can_edit_incident_report function
    """
    users = populate_incident_db["users"]
    incidents = populate_incident_db["incidents"]
    incident_operator = next((u for u in incidents if u.incident_id == "XXXX-SSS-SSS-0001-2005"), None)
    incident_regulator = next((u for u in incidents if u.incident_id == "RRR-SSS-SSS-0001-2005"), None)
    if incident_operator:
        authorized_users = [
            u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu" or u.email == "regadmin@reg1.lu"
        ]
        for u in users:
            company_id = -1
            if u.companies.first() is not None:
                company_id = u.companies.first().id
            if u in authorized_users:
                assert can_edit_incident_report(u, incident_operator, company_id) is True
            else:
                assert can_edit_incident_report(u, incident_operator, company_id) is False
    if incident_regulator:
        authorized_users = [u for u in users if u.email == "reguser@reg1.lu" or u.email == "regadmin@reg1.lu"]
        for u in users:
            if u in authorized_users:
                assert can_edit_incident_report(u, incident_regulator, -1) is True
            else:
                assert can_edit_incident_report(u, incident_regulator, -1) is False


@pytest.mark.django_db
def test_access_to_incident_log(otp_client, populate_incident_db):
    """
    Test access to the log of the incident (user view)
    """
    users = populate_incident_db["users"]
    incidents = populate_incident_db["incidents"]
    # operator admin
    authorized_users = [
        u
        for u in users
        if u.email == "opadmin@com1.lu"
        or u.email == "obsadm@cert1.lu"  # receive all incident
        or u.email == "opuser@com1.lu"
        or u.email == "regadmin@reg1.lu"
    ]
    # operator incident
    incident = next((u for u in incidents if u.incident_id == "XXXX-SSS-SSS-0001-2005"), None)
    url = "/incidents/access_log/" + str(incident.id)
    test_get_with_otp(otp_client, users, authorized_users, [], url)

    authorized_users = [
        u
        for u in users
        if u.email == "obsadm@cert1.lu"  # receive all incident
        or u.email == "reguser@reg1.lu"
        or u.email == "regadmin@reg1.lu"
    ]
    # regulator incident
    incident = next((u for u in incidents if u.incident_id == "RRR-SSS-SSS-0001-2005"), None)
    url = "/incidents/access_log/" + str(incident.id)
    test_get_with_otp(otp_client, users, authorized_users, [], url)
