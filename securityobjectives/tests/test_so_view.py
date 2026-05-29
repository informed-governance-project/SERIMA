import pytest

from conftest import (
    list_admin_add_urls,
    list_url_freetext_filter,
    test_get_with_otp,
)
from governanceplatform.helpers import (
    user_in_group,
)


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
