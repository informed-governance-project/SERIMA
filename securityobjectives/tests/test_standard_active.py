"""Retiring an evaluation framework with Standard.active.

A deactivated framework accepts no new declaration: it leaves the operator's creation
picker and the regulator's import picker, and copying an earlier declaration onto it is
refused. Only the new-version path stays open, so an operator whose declaration the
regulator sent back can still revise it on the framework it was made against.
"""

import pytest
from django.urls import reverse

from governanceplatform.admin import admin_site
from governanceplatform.helpers import get_sectors_grouped
from governanceplatform.models import Functionality, Sector
from reporting.models import Project
from securityobjectives.models import Standard, StandardAnswer


class _CollectingMessages:
    """Stand-in for the message store MessageMiddleware normally attaches."""

    def __init__(self):
        self.added = []

    def add(self, level, message, extra_tags=""):
        self.added.append((level, message))


def _selectable_sector_ids():
    """The sector ids a picker actually offers; a parent with children is only a group."""
    return [str(option[0]) for _group, options in get_sectors_grouped(Sector.objects.all()) for option in options]


@pytest.fixture
def standard(populate_so_db):
    return populate_so_db["so_standard"][0]


@pytest.fixture
def declaration(populate_so_db):
    return populate_so_db["sas"][0]


@pytest.fixture
def operator_client(otp_client, populate_so_db, declaration):
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = declaration.submitter_company_id
    session.save()
    return client


@pytest.fixture
def regulator_user(populate_so_db):
    return next(user for user in populate_so_db["users"] if user.email == "regadmin@reg1.lu")


@pytest.fixture
def regulator_client(otp_client, regulator_user):
    return otp_client(regulator_user)


@pytest.fixture
def reporting_client(otp_client, regulator_user):
    """The reporting pages are gated per regulator, so grant the functionality first."""
    regulator = regulator_user.regulators.first()
    regulator.functionalities.add(Functionality.objects.get(type="reporting"))
    return otp_client(regulator_user)


@pytest.mark.django_db()
def test_a_framework_is_active_when_it_is_created(standard):
    """Retiring a framework is a deliberate act, so a new one is usable at once."""
    assert standard.active is True


@pytest.mark.django_db()
def test_creation_picker_drops_a_deactivated_framework(operator_client, standard):
    url = reverse("create_so_declaration")
    assert str(standard) in operator_client.get(url).content.decode()

    standard.active = False
    standard.save()

    assert str(standard) not in operator_client.get(url).content.decode()


@pytest.mark.django_db()
def test_creation_refuses_a_deactivated_framework(operator_client, standard):
    """The picker is the boundary: a forged id must not slip past the form."""
    standard.active = False
    standard.save()
    before = StandardAnswer.objects.count()

    operator_client.post(
        reverse("create_so_declaration"),
        data={"so_standard": standard.pk, "year": 2026, "sectors": _selectable_sector_ids()},
    )

    assert StandardAnswer.objects.count() == before


@pytest.mark.django_db()
def test_import_picker_drops_a_deactivated_framework(regulator_client, standard):
    url = reverse("import_so_declaration")
    assert str(standard) in regulator_client.get(url).content.decode()

    standard.active = False
    standard.save()

    assert str(standard) not in regulator_client.get(url).content.decode()


@pytest.mark.django_db()
def test_copy_is_refused_on_a_deactivated_framework(operator_client, standard, declaration):
    standard.active = False
    standard.save()
    before = StandardAnswer.objects.count()

    response = operator_client.post(
        reverse("copy_so_declaration", args=[declaration.group.pk]),
        data={"year": 2026, "sectors": _selectable_sector_ids()},
    )

    assert response.status_code == 403
    assert StandardAnswer.objects.count() == before


@pytest.mark.django_db()
def test_copy_succeeds_while_the_framework_is_active(operator_client, declaration):
    """Guards the copy check against over-blocking."""
    before = StandardAnswer.objects.count()

    operator_client.post(
        reverse("copy_so_declaration", args=[declaration.group.pk]),
        data={"year": 2026, "sectors": _selectable_sector_ids()},
    )

    assert StandardAnswer.objects.count() == before + 1


@pytest.mark.django_db()
def test_a_new_version_is_still_created_on_a_deactivated_framework(operator_client, standard, declaration):
    """An operator sent back for revision is not stranded by a framework retired meanwhile."""
    declaration.status = "FAIL"
    declaration.save()
    standard.active = False
    standard.save()
    before = StandardAnswer.objects.count()

    operator_client.get(f"{reverse('so_declaration')}?id={declaration.pk}&update=true")

    assert StandardAnswer.objects.count() == before + 1


@pytest.mark.django_db()
def test_report_project_creation_drops_a_deactivated_framework(reporting_client, standard):
    url = reverse("create_report_project")
    assert str(standard) in reporting_client.get(url).content.decode()

    standard.active = False
    standard.save()

    assert str(standard) not in reporting_client.get(url).content.decode()


@pytest.mark.django_db()
def test_report_project_editing_keeps_a_deactivated_framework(reporting_client, regulator_user, standard):
    """A project built on a framework since retired stays editable."""
    project = Project.objects.create(
        author=regulator_user,
        name="Report on a retired framework",
        standard=standard,
        years=[2025],
        reference_year=2025,
        selected_file_format="pdf",
    )
    standard.active = False
    standard.save()

    content = reporting_client.get(reverse("edit_report_project", args=[project.pk])).content.decode()

    assert str(standard) in content


@pytest.mark.django_db()
def test_the_active_flag_stays_editable_on_a_framework_in_use(rf, regulator_user, standard):
    """Retiring a framework operators have already answered against is the whole point.

    The in-use lock freezes the structural fields of a standard; were the active flag
    caught by it, the flag could only ever be set on frameworks nobody had used.
    """
    assert standard.is_in_use() is True
    request = rf.get("/")
    request.user = regulator_user
    request._messages = _CollectingMessages()
    standard_admin = admin_site._registry[Standard]

    assert standard_admin.has_change_permission(request, standard) is True
    assert "active" not in standard_admin.get_readonly_fields(request, standard)
