import re

import pytest

from governanceplatform.helpers import user_in_group
from governanceplatform.models import User


@pytest.mark.django_db()
def test_standard_list_opens_a_standard_from_its_label_not_its_active_icon(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    admin = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))

    body = otp_client(admin).get("/admin/securityobjectives/standard/").content.decode()
    change_url = f"/admin/securityobjectives/standard/{standard.pk}/change/"

    assert re.search(rf'class="field-label_display[^"]*"><a href="{change_url}', body)
    assert not re.search(rf'class="field-active[^"]*"><a href="{change_url}', body)


@pytest.mark.django_db()
def test_import_and_export_sit_in_the_list_toolbar(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    admin = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))

    body = otp_client(admin).get("/admin/securityobjectives/standard/").content.decode()
    header, toolbar = body.split('class="changelist-tools"', 1)

    for link in ("standard/celery-import/", "standard/celery-export/"):
        assert link not in header
        assert link in toolbar
