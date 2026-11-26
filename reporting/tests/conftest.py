import pytest

import governanceplatform.tests.conftest as gp_conftest
from governanceplatform.models import Functionality, Regulation, Sector, User
from reporting.models import Project
from securityobjectives.models import Standard


@pytest.fixture
def populate_db(db):
    # on rewrap fixture to expose localy and don't get flake error
    return gp_conftest.populate_db.__wrapped__(db)


def reporting_regulator(email: str) -> User:
    """A regulator administrator whose regulator has the reporting module."""
    user = User.objects.get(email=email)
    user.regulators.first().functionalities.add(Functionality.objects.get(type="reporting"))
    return user


@pytest.fixture
def regulator(populate_db):
    return reporting_regulator("regadmin@reg1.lu")


@pytest.fixture
def other_regulator(populate_db):
    return reporting_regulator("regadmin@reg2.lu")


@pytest.fixture
def project(regulator):
    standard = Standard.objects.create(
        label="Standard", regulator=regulator.regulators.first(), regulation=Regulation.objects.create(label="Regulation")
    )
    project = Project.objects.create(
        author=regulator,
        standard=standard,
        name="Original",
        reference_year=2026,
        years=[2024],
        top_ranking=3,
        threshold_for_high_risk=50,
        selected_file_format="docx",
        selected_languages=["en"],
    )
    project.sectors.add(Sector.objects.create(name="Energy"))
    return project
