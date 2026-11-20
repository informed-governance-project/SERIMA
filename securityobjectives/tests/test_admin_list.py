import re

import pytest
from django.urls import reverse
from import_export_extensions.models import ExportJob

from governanceplatform.admin import admin_site
from governanceplatform.helpers import user_in_group
from governanceplatform.models import User
from securityobjectives.admin import StandardResource
from securityobjectives.models import MaturityLevel, SecurityMeasure, SecurityObjectivesInStandard, Standard


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


def _regulator_admin(standard):
    return next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))


@pytest.mark.django_db()
def test_standard_export_lets_the_fields_be_chosen(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard

    body = otp_client(_regulator_admin(standard)).get("/admin/securityobjectives/standard/celery-export/").content.decode()

    assert body.count('class="selectable-field-export-row') > 1


@pytest.mark.django_db()
def test_standard_export_results_page_has_the_admin_layout(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    admin = _regulator_admin(standard)
    # bulk_create skips save(), which would start the export task.
    (job,) = ExportJob.objects.bulk_create(
        [
            ExportJob(
                resource_path="securityobjectives.admin.StandardResource",
                file_format_path="import_export.formats.base_formats.CSV",
                created_by=admin,
                resource_kwargs={},
                export_status="EXPORTED",
                data_file="exports/standards.csv",
            )
        ]
    )

    body = otp_client(admin).get(reverse("admin:securityobjectives_standard_export_job_results", args=[job.pk])).content.decode()

    assert 'id="nav-sidebar"' in body
    # Never the file's own URL: exports are not statically served, only through this view.
    assert reverse("admin:exportjob_download_and_delete", args=[job.pk]) in body
    assert "exports/standards.csv" not in body


@pytest.mark.django_db()
def test_export_selected_action_opens_the_export_of_the_chosen_standards(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard

    response = otp_client(_regulator_admin(standard)).post(
        "/admin/securityobjectives/standard/",
        {"action": "export_selected", "_selected_action": [standard.pk]},
    )

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('admin:securityobjectives_standard_export')}?id__in={standard.pk}"


@pytest.mark.django_db()
def test_export_form_names_how_many_standards_are_selected(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard

    url = f"/admin/securityobjectives/standard/celery-export/?id__in={standard.pk}"

    body = otp_client(_regulator_admin(standard)).get(url).content.decode()

    assert "Export 1 selected item." in " ".join(body.split())
    assert 'name="export_items"' not in body


@pytest.mark.django_db()
def test_export_of_selected_standards_leaves_the_others_out(populate_so_db, security_measure_from_another_standard, rf):
    standard = populate_so_db["sas"][0].standard
    request = rf.get(f"/?id__in={standard.pk}")
    request.user = _regulator_admin(standard)
    request.LANGUAGE_CODE = "en"  # set by LocaleMiddleware on a real request
    model_admin = admin_site._registry[Standard]

    dataset = StandardResource(**model_admin.get_export_resource_kwargs(request)).export()

    assert set(dataset["label"]) == {standard.label}


@pytest.mark.django_db()
@pytest.mark.parametrize("field", ["description", "evidence"])
def test_security_measure_translated_text_fields_are_unfold_textareas(populate_so_db, otp_client, field):
    standard = populate_so_db["sas"][0].standard

    body = otp_client(_regulator_admin(standard)).get("/admin/securityobjectives/securitymeasure/add/").content.decode()

    textarea = re.search(rf'<textarea[^>]*id="id_{field}"[^>]*>', body).group(0)
    assert "border-base-200" in textarea


def _security_measure_post(standard, **extra):
    security_objective = SecurityObjectivesInStandard.objects.filter(standard=standard).first().security_objective
    maturity_level = MaturityLevel.objects.filter(standard=standard).first()
    return {
        "security_objective": security_objective.pk,
        "maturity_level": maturity_level.pk,
        "position": 99,
        "description": "Measure added from the admin",
        "evidence": "Its evidence",
        **extra,
    }


@pytest.mark.django_db()
def test_security_measure_cannot_be_created_without_its_default_language(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    client = otp_client(_regulator_admin(standard))

    response = client.post("/admin/securityobjectives/securitymeasure/add/?language=fr", _security_measure_post(standard))

    assert response.status_code == 200
    assert "Default language translation (English) is missing" in response.content.decode()
    assert not SecurityMeasure.objects.filter(translations__description="Measure added from the admin").exists()


@pytest.mark.django_db()
def test_security_measure_is_created_in_its_default_language(populate_so_db, otp_client):
    standard = populate_so_db["sas"][0].standard
    client = otp_client(_regulator_admin(standard))

    response = client.post("/admin/securityobjectives/securitymeasure/add/?language=en", _security_measure_post(standard, en=""))

    assert response.status_code == 302
    assert SecurityMeasure.objects.filter(translations__description="Measure added from the admin").exists()
