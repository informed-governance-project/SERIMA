import importlib

import pytest
from django.apps import apps

from governanceplatform.helpers import user_in_group
from governanceplatform.models import User
from securityobjectives.models import SecurityObjectiveEmail

migration = importlib.import_module("securityobjectives.migrations.0048_email_content_markdown_to_html")


@pytest.mark.django_db()
def test_email_content_is_edited_in_the_rich_text_editor(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    admin = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))

    body = otp_client(admin).get("/admin/securityobjectives/securityobjectiveemail/add/").content.decode()

    assert '<trix-editor input="wysiwyg-content"' in body


@pytest.mark.django_db()
def test_migration_converts_the_markdown_content_to_html(populate_so_db):
    email = SecurityObjectiveEmail(name="Status")
    email.set_current_language("en")
    email.subject = "Status changed"
    email.content = "Dear **operator**"
    email.save()

    migration.markdown_to_html(apps, None)

    email.refresh_from_db()
    assert email.safe_translation_getter("content", language_code="en") == "<p>Dear <strong>operator</strong></p>"


@pytest.mark.django_db()
def test_import_and_export_sit_in_the_list_toolbar(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    admin = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))

    body = otp_client(admin).get("/admin/securityobjectives/standard/").content.decode()
    header, toolbar = body.split('class="changelist-tools"', 1)

    for link in ("standard/celery-import/", "standard/celery-export/"):
        assert link not in header
        assert link in toolbar
