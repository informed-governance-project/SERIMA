import pytest

from governanceplatform.helpers import user_in_group
from governanceplatform.models import (
    Observer,
    ObserverConnector,
    User,
)


@pytest.mark.django_db(transaction=True)
def test_add_user_via_admin(otp_client, populate_db):
    """
    Test that when a user creates another via the admin interface,
    the new user's role is correct depending on the creator.
    """
    users = populate_db["users"]
    url = "/admin/governanceplatform/user/add/"

    # role mapping creator --> creation
    role_mapping = {
        "PlatformAdmin": "PlatformAdmin",
        "RegulatorAdmin": "RegulatorUser",
        "RegulatorUser": "OperatorUser",
        "OperatorAdmin": "OperatorUser",
        "ObserverAdmin": "ObserverUser",
    }

    for index, creator in enumerate(users, start=1):
        # new user data
        email = f"new_user{index}@serima.exemple.lu"
        data = {
            "email": email,
            "first_name": "test",
            "last_name": "test",
        }

        client = otp_client(creator)

        # check if the user is in a group who can create a user
        creator_group = next((group for group in role_mapping if user_in_group(creator, group)), None)
        if not creator_group:
            continue

        expected_group = role_mapping[creator_group]

        response = client.post(url, data, follow=True)
        assert response.status_code == 200
        created_user = User.objects.get(email=email)
        assert user_in_group(created_user, expected_group), f"{creator_group} → {expected_group} expected, but got something else"


@pytest.fixture
def observer_connector(populate_db):
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["rt"]
    observer.save()
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="rt",
        name="RT",
        config={"url": "https://rt.example.com", "queue": "incidents"},
    )
    connector.secret = "rt-token"
    connector.save()
    return connector


@pytest.mark.django_db
def test_connector_admin_scoped_to_own_observer(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    foreign_observer = Observer.objects.create(
        id=999,
        country="LU",
        address="456 rue de Luxembourg",
        email_for_notification="cert2@cert2.lu",
        name="CERT2",
    )
    foreign_connector = ObserverConnector.objects.create(observer=foreign_observer, connector_type="email", name="Email", config={})

    client = otp_client(obs_admin)
    response = client.get("/admin/governanceplatform/observerconnector/")
    assert response.status_code == 200
    assert observer_connector.name.encode() in response.content

    response = client.get(f"/admin/governanceplatform/observerconnector/{foreign_connector.pk}/change/")
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_connector_admin_masks_secret(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observerconnector/{observer_connector.pk}/change/")

    assert response.status_code == 200
    assert b"rt-token" not in response.content
    assert ("*" * len("rt-token")).encode() in response.content


@pytest.mark.django_db
def test_connector_test_endpoint_permissions(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))
    url = f"/admin/governanceplatform/observerconnector/{observer_connector.pk}/test-connection/"

    client = otp_client(obs_admin)
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_allowed_connector_types_hidden_from_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b"allowed_connector_types" not in response.content


@pytest.mark.django_db
def test_allowed_connector_types_visible_to_platform_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    platform_admin = next(user for user in users if user_in_group(user, "PlatformAdmin"))

    client = otp_client(platform_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b"allowed_connector_types" in response.content


@pytest.mark.django_db
def test_observer_admin_add_connector_limited_to_allowed_types(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get("/admin/governanceplatform/observerconnector/add/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="gpg_json"' in content
    assert 'value="rt"' not in content
    assert 'value="webhook"' not in content


@pytest.mark.django_db
def test_removing_allowed_type_deactivates_its_connectors(populate_db):
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["rt", "gpg_json"]
    observer.save()
    rt = ObserverConnector.objects.create(observer=observer, connector_type="rt", name="RT", config={})
    gpg_json = ObserverConnector.objects.create(observer=observer, connector_type="gpg_json", name="GPG JSON", config={})

    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    observer.deactivate_disallowed_connectors()

    rt.refresh_from_db()
    gpg_json.refresh_from_db()
    assert rt.is_active is False
    assert gpg_json.is_active is True


@pytest.mark.django_db
def test_disallowed_type_connector_hidden_from_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    hidden = ObserverConnector.objects.create(observer=observer, connector_type="rt", name="RT hidden", config={})
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    list_response = client.get("/admin/governanceplatform/observerconnector/")
    change_response = client.get(f"/admin/governanceplatform/observerconnector/{hidden.pk}/change/")

    assert list_response.status_code == 200
    assert b"RT hidden" not in list_response.content
    assert change_response.status_code in (302, 404)


@pytest.mark.django_db
def test_notification_mode_editable_by_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b'name="notification_mode"' in response.content


@pytest.mark.django_db
def test_connector_two_step_add_flow(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    # step 1: the add form has no config fields and must save without them
    response = client.post(
        "/admin/governanceplatform/observerconnector/add/",
        {"observer": observer.pk, "connector_type": "gpg_json", "name": "GPG JSON", "is_active": "on"},
    )
    connector = ObserverConnector.objects.get(observer=observer, name="GPG JSON")
    # step 2: redirected straight to the change view where the config fields live
    assert response.status_code == 302
    assert response.url == f"/admin/governanceplatform/observerconnector/{connector.pk}/change/"
    change_page = client.get(response.url)
    assert change_page.status_code == 200
    assert b'name="config__gpg_public_key"' in change_page.content
