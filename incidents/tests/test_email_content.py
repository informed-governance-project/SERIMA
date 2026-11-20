import importlib

import pytest
from django.apps import apps

from governanceplatform.helpers import user_in_group
from governanceplatform.models import User
from incidents.models import Email

migration = importlib.import_module("incidents.migrations.0074_email_content_markdown_to_html")


@pytest.mark.django_db
def test_migration_converts_the_markdown_content_to_html():
    email = Email(name="Opening")
    email.set_current_language("en")
    email.subject = "Opened"
    email.content = "Dear **operator**,\n\n* first\n* second"
    email.save()

    migration.markdown_to_html(apps, None)

    email.refresh_from_db()
    assert email.safe_translation_getter("content", language_code="en") == (
        "<p>Dear <strong>operator</strong>,</p>\n<ul>\n<li>first</li>\n<li>second</li>\n</ul>"
    )


@pytest.mark.django_db
def test_email_content_is_edited_in_the_rich_text_editor(otp_client, populate_db):
    admin = next(user for user in User.objects.all() if user_in_group(user, "RegulatorAdmin"))

    body = otp_client(admin).get("/admin/incidents/email/add/").content.decode()

    assert '<trix-editor input="wysiwyg-content"' in body
