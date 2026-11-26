import re
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from securityobjectives.models import StandardAnswer

# Integer-keyed declaration links and ids as the pages built them before #936. The lookahead keeps
# the all-zero placeholder UUID the templates reverse from counting as an integer; the versions list
# is JSON inside an HTML attribute, so its quotes are escaped.
SEQUENTIAL_ID_PATTERNS = [
    r"/securityobjectives/(?:copy|submit|delete|review_comment|download|access_log)/\d+(?![0-9a-fA-F-])",
    r"[?&]id=\d+(?![0-9a-fA-F-])",
    r'data-standard-answer-id="\d+"',
    r"(?:\"|&quot;)id(?:\"|&quot;): \d+",
]


def get_user(populate_so_db, email: str):
    return next(u for u in populate_so_db["users"] if u.email == email)


def submitted_declaration(populate_so_db) -> StandardAnswer:
    declaration = populate_so_db["sas"][0]
    StandardAnswer.objects.filter(pk=declaration.pk).update(status="PASSM", submit_date=timezone.now())
    declaration.refresh_from_db()
    return declaration


@pytest.mark.django_db
def test_a_declaration_url_does_not_resolve_with_the_primary_key(otp_client, populate_so_db):
    declaration = populate_so_db["sas"][0]

    response = otp_client(get_user(populate_so_db, "opadmin@com1.lu")).get(f"/securityobjectives/access_log/{declaration.pk}")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_declaration_is_reached_by_its_public_id(otp_client, populate_so_db):
    declaration = populate_so_db["sas"][0]

    response = otp_client(get_user(populate_so_db, "opadmin@com1.lu")).get(reverse("so_declaration"), {"id": declaration.public_id})

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["", "1", "not-a-uuid", str(uuid4())])
def test_a_declaration_with_a_malformed_or_unknown_id_sends_back_to_the_list(otp_client, populate_so_db, value):
    response = otp_client(get_user(populate_so_db, "opadmin@com1.lu")).get(reverse("so_declaration"), {"id": value})

    assert response.status_code == 302
    assert response.url == reverse("securityobjectives")


@pytest.mark.django_db
def test_a_declaration_page_does_not_accept_the_primary_key(otp_client, populate_so_db):
    declaration = populate_so_db["sas"][0]

    response = otp_client(get_user(populate_so_db, "opadmin@com1.lu")).get(reverse("so_declaration"), {"id": declaration.pk})

    assert response.status_code == 302


@pytest.mark.django_db
def test_a_new_version_gets_its_own_public_id(otp_client, populate_so_db):
    declaration = submitted_declaration(populate_so_db)
    client = otp_client(get_user(populate_so_db, "opadmin@com1.lu"))

    response = client.get(reverse("so_declaration"), {"id": declaration.public_id, "update": "true"})

    new_version = StandardAnswer.objects.filter(group=declaration.group).exclude(pk=declaration.pk).get()
    assert new_version.public_id != declaration.public_id
    assert response.url == f"{reverse('so_declaration')}?id={new_version.public_id}"


@pytest.mark.django_db
def test_a_declaration_is_copied_by_its_group_public_id(otp_client, populate_so_db):
    declaration = populate_so_db["sas"][0]
    client = otp_client(get_user(populate_so_db, "opadmin@com1.lu"))

    assert client.get(reverse("copy_so_declaration", args=[declaration.group.public_id])).status_code == 200
    assert client.get(f"/securityobjectives/copy/{declaration.group.pk}").status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("email", ["opadmin@com1.lu", "regadmin@reg1.lu"])
def test_the_dashboard_never_shows_a_sequential_id(otp_client, populate_so_db, email):
    submitted_declaration(populate_so_db)

    response = otp_client(get_user(populate_so_db, email)).get(reverse("securityobjectives"))

    assert response.status_code == 200
    content = response.content.decode()
    assert any(str(declaration.public_id) in content for declaration in populate_so_db["sas"])
    for pattern in SEQUENTIAL_ID_PATTERNS:
        assert not re.search(pattern, content), pattern


@pytest.mark.django_db
def test_the_declaration_page_never_shows_a_sequential_id(otp_client, populate_so_db):
    declaration = submitted_declaration(populate_so_db)

    client = otp_client(get_user(populate_so_db, "regadmin@reg1.lu"))

    content = client.get(reverse("so_declaration"), {"id": declaration.public_id}).content.decode()

    assert str(declaration.public_id) in content
    for pattern in SEQUENTIAL_ID_PATTERNS:
        assert not re.search(pattern, content), pattern


@pytest.mark.django_db(transaction=True)
def test_the_migration_gives_each_existing_row_its_own_public_id():
    before = ("securityobjectives", "0048_email_content_markdown_to_html")
    after = ("securityobjectives", "0051_alter_public_id_unique")

    executor = MigrationExecutor(connection)
    executor.migrate([before])
    apps = executor.loader.project_state([before]).apps
    historical_group = apps.get_model("securityobjectives", "StandardAnswerGroup")
    historical_answer = apps.get_model("securityobjectives", "StandardAnswer")
    groups = [historical_group.objects.create(group_id=f"LEGACY_{n}") for n in range(3)]
    for group in groups:
        historical_answer.objects.create(group=group, year_of_submission=2026)

    try:
        executor = MigrationExecutor(connection)
        executor.migrate([after])
        apps = executor.loader.project_state([after]).apps

        group_ids = list(apps.get_model("securityobjectives", "StandardAnswerGroup").objects.values_list("public_id", flat=True))
        answer_ids = list(apps.get_model("securityobjectives", "StandardAnswer").objects.values_list("public_id", flat=True))
        assert None not in group_ids + answer_ids
        assert len(set(group_ids)) == len(groups)
        assert len(set(answer_ids)) == len(groups)
    finally:
        # Going back to `before` also unapplied every later migration; the teardown flush
        # needs the schema the current models describe.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
