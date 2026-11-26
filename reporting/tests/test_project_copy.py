import pytest
from django.urls import reverse

from reporting.models import Project


@pytest.mark.django_db
def test_a_copied_project_gets_its_own_public_id(otp_client, regulator, project):
    response = otp_client(regulator).post(reverse("copy_report_project", args=[project.public_id]), {"name": "Copy"})

    assert response.status_code == 302
    copy = Project.objects.get(name="Copy")
    assert copy.pk != project.pk
    assert copy.public_id != project.public_id
