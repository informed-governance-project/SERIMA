import json

import pytest
from django.urls import reverse

from conftest import (
    list_admin_add_urls,
    list_url_freetext_filter,
    test_get_with_otp,
)
from governanceplatform.helpers import (
    user_in_group,
)
from securityobjectives.models import SecurityMeasureAnswer, SecurityObjectiveStatus


@pytest.mark.django_db
def test_so_user_access_without_2FA(client, populate_so_db):
    """
    Verify if the security objective main pages are not accessible without 2FA
    """
    users = populate_so_db["users"]

    for user in users:
        client.force_login(user)
        url_list = list_url_freetext_filter("securityobjectives", "")
        for url in url_list:
            response = client.get("/" + url)
            assert response.status_code in (
                302,
                403,
            ), f"User {user.email} should not access to the admin without 2FA"


@pytest.mark.django_db
def test_so_admin_roles_addition_rights(otp_client, populate_so_db):
    """
    Test the rights of each groups on the model of security objectives
    """
    users = populate_so_db["users"]
    regulator_admin_rights = [
        "domain",
        "securityobjectiveemail",
        "maturitylevel",
        "securitymeasure",
        "securityobjective",
        "standard",
    ]
    authorized_users = [u for u in users if user_in_group(u, "RegulatorAdmin")]
    for u in list_admin_add_urls("securityobjective"):
        if any(model in u for model in regulator_admin_rights):
            url = "/" + u
            test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_can_access_so(otp_client, populate_so_db):
    """
    Test if the SO is accessible by the correct user
    """
    users = populate_so_db["users"]
    sas = populate_so_db["sas"]
    # operator admin
    authorized_users = [u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu" or u.email == "regadmin@reg1.lu"]
    unaccess_module_users = [
        u
        for u in users
        if u.email == "reguser@reg2.lu"
        or u.email == "regadmin@reg2.lu"
        or u.email == "obsadm@cert1.lu"
        or u.email == "iu1@iu.lu"
        or u.email == "iu2@iu.lu"
    ]
    # standard answer
    sa = sas[0]

    url = "/securityobjectives/declaration?id=" + str(sa.pk)
    test_get_with_otp(otp_client, users, authorized_users, unaccess_module_users, url)


@pytest.mark.django_db
def test_pdf_download_so(otp_client, populate_so_db):
    """
    Test if the PDF download is accessible to the right users
    """
    users = populate_so_db["users"]
    sas = populate_so_db["sas"]
    # authorized user
    authorized_users = [u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu" or u.email == "regadmin@reg1.lu"]
    # user with 404
    unauthorized_user = [
        u
        for u in users
        if u.email == "regadmin@reg2.lu"
        or u.email == "reguser@reg2.lu"
        or u.email == "obsadm@cert1.lu"
        or u.email == "iu1@iu.lu"
        or u.email == "iu2@iu.lu"
    ]
    # only one Standard answers in the DB
    sa = next((u for u in sas), None)
    url = "/securityobjectives/download/" + str(sa.id)
    test_get_with_otp(otp_client, users, authorized_users, unauthorized_user, url)


@pytest.mark.django_db
def test_cannot_update_security_objective_from_another_standard(
    otp_client,
    populate_so_db,
    security_measure_from_another_standard,
):
    standard_answer = populate_so_db["sas"][0]
    regulator = next(user for user in populate_so_db["users"] if user.email == "regadmin@reg1.lu")
    client = otp_client(regulator)
    foreign_objective = security_measure_from_another_standard.security_objective

    response = client.post(
        f"{reverse('so_declaration')}?id={standard_answer.pk}",
        data=json.dumps({"id": foreign_objective.pk, "status": "PASS"}),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not SecurityObjectiveStatus.objects.filter(
        standard_answer=standard_answer,
        security_objective=foreign_objective,
    ).exists()


@pytest.mark.django_db
def test_cannot_update_security_measure_from_another_standard(
    otp_client,
    populate_so_db,
    security_measure_from_another_standard,
):
    standard_answer = populate_so_db["sas"][0]
    standard_answer.status = "UNDE"
    standard_answer.save()
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = standard_answer.submitter_company_id
    session.save()

    response = client.post(
        f"{reverse('so_declaration')}?id={standard_answer.pk}",
        data=json.dumps({"id": security_measure_from_another_standard.pk, "is_implemented": True}),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not SecurityMeasureAnswer.objects.filter(
        standard_answer=standard_answer,
        security_measure=security_measure_from_another_standard,
    ).exists()
