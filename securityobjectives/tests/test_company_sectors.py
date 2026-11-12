"""A declaration's sectors are those the regulator assigned to the submitting company (#911).

The operator no longer picks sectors, and only regulators see them, so the regulator's
configuration in the backend decides which regulator users see a declaration and which
reporting projects it feeds.
"""

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from governanceplatform.models import RegulatorUser, Sector
from securityobjectives.helpers import security_objective_exists
from securityobjectives.models import StandardAnswer


@pytest.fixture
def declaration(populate_so_db):
    return populate_so_db["sas"][0]


@pytest.fixture
def company(declaration):
    return declaration.submitter_company


@pytest.fixture
def leaf_sectors():
    return list(Sector.objects.filter(parent__isnull=False).order_by("id")[:2])


@pytest.fixture
def operator_client(otp_client, populate_so_db, company):
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = company.id
    session.save()
    return client


@pytest.fixture
def regulator_user(populate_so_db):
    return next(user for user in populate_so_db["users"] if user.email == "reguser@reg1.lu")


@pytest.fixture
def regulator_client(otp_client, regulator_user):
    return otp_client(regulator_user)


def assign_regulator_user_sectors(regulator_user, sectors):
    RegulatorUser.objects.get(user=regulator_user, regulator=regulator_user.regulators.first()).sectors.set(sectors)


def dashboard_declarations(client):
    return list(client.get(reverse("securityobjectives")).context["standard_answers"])


@pytest.mark.django_db()
def test_an_operator_creates_a_declaration_without_choosing_a_sector(operator_client, populate_so_db, company):
    before = StandardAnswer.objects.count()

    operator_client.post(reverse("create_so_declaration"), data={"so_standard": populate_so_db["so_standard"][0].pk, "year": 2026})

    assert StandardAnswer.objects.count() == before + 1
    created = StandardAnswer.objects.latest("id")
    assert set(created.get_sectors()) == set(company.sectors.all())


@pytest.mark.django_db()
def test_an_operator_duplicates_a_declaration_without_choosing_a_sector(operator_client, declaration):
    before = StandardAnswer.objects.count()

    operator_client.post(reverse("copy_so_declaration", args=[declaration.group.pk]), data={"year": 2026})

    assert StandardAnswer.objects.count() == before + 1


@pytest.mark.django_db()
def test_the_creation_modal_offers_no_sector(operator_client):
    assert "sectors" not in operator_client.get(reverse("create_so_declaration")).context["form"].fields


@pytest.mark.django_db()
def test_the_operator_dashboard_has_no_sector_filter(operator_client):
    assert "sectors" not in operator_client.get(reverse("securityobjectives")).context["filter"].form.fields


@pytest.mark.django_db()
def test_the_regulator_dashboard_keeps_the_sector_filter(regulator_client):
    assert "sectors" in regulator_client.get(reverse("securityobjectives")).context["filter"].form.fields


@pytest.mark.django_db()
def test_a_regulator_user_sees_a_declaration_through_the_company_sector(
    regulator_client, regulator_user, declaration, company, leaf_sectors
):
    company.sectors.set([leaf_sectors[0]])
    assign_regulator_user_sectors(regulator_user, [leaf_sectors[0]])

    assert declaration in dashboard_declarations(regulator_client)


@pytest.mark.django_db()
def test_a_regulator_user_does_not_see_a_company_outside_their_sectors(
    regulator_client, regulator_user, declaration, company, leaf_sectors
):
    company.sectors.set([leaf_sectors[0]])
    assign_regulator_user_sectors(regulator_user, [leaf_sectors[1]])

    assert declaration not in dashboard_declarations(regulator_client)


@pytest.mark.django_db()
def test_a_company_in_several_sectors_is_listed_once(regulator_client, regulator_user, declaration, company, leaf_sectors):
    company.sectors.set(leaf_sectors)
    assign_regulator_user_sectors(regulator_user, leaf_sectors)

    assert dashboard_declarations(regulator_client).count(declaration) == 1


@pytest.mark.django_db()
def test_a_sector_change_in_the_backend_reaches_existing_declarations(regulator_client, regulator_user, declaration, company, leaf_sectors):
    company.sectors.set([leaf_sectors[0]])
    assign_regulator_user_sectors(regulator_user, [leaf_sectors[1]])
    assert declaration not in dashboard_declarations(regulator_client)

    company.sectors.set([leaf_sectors[1]])

    assert list(declaration.get_sectors()) == [leaf_sectors[1]]
    assert declaration in dashboard_declarations(regulator_client)


@pytest.mark.django_db()
def test_reporting_finds_an_accepted_declaration_through_the_company_sector(declaration, company, leaf_sectors):
    declaration.status = "PASSM"
    declaration.save()
    company.sectors.set([leaf_sectors[1]])

    assert security_objective_exists(company, declaration.year_of_submission, leaf_sectors[1]) is True
    assert security_objective_exists(company, declaration.year_of_submission, leaf_sectors[0]) is False


def declaration_page(client, declaration):
    return client.get(f"{reverse('so_declaration')}?id={declaration.id}").content.decode()


@pytest.mark.django_db()
def test_the_operator_declaration_page_does_not_show_the_sector(operator_client, declaration, company, leaf_sectors):
    company.sectors.set([leaf_sectors[0]])

    assert leaf_sectors[0].get_safe_translation() not in declaration_page(operator_client, declaration)


@pytest.mark.django_db()
def test_the_regulator_declaration_page_shows_the_sector(regulator_client, regulator_user, declaration, company, leaf_sectors):
    company.sectors.set([leaf_sectors[0]])
    assign_regulator_user_sectors(regulator_user, [leaf_sectors[0]])

    assert leaf_sectors[0].get_safe_translation() in declaration_page(regulator_client, declaration)


def pdf_cover(user, declaration):
    request = RequestFactory().get("/")
    request.user = user
    return render_to_string("report/security_objectives/cover.html", {"standard_answer": declaration}, request=request)


@pytest.mark.django_db()
def test_the_operator_pdf_cover_does_not_show_the_sector(populate_so_db, declaration, company, leaf_sectors):
    company.sectors.set([leaf_sectors[0]])
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")

    assert str(leaf_sectors[0]) not in pdf_cover(operator, declaration)


@pytest.mark.django_db()
def test_the_regulator_pdf_cover_shows_the_sector(regulator_user, declaration, company, leaf_sectors):
    company.sectors.set([leaf_sectors[0]])

    assert str(leaf_sectors[0]) in pdf_cover(regulator_user, declaration)
