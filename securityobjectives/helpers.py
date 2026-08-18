from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from governanceplatform.models import Company, Sector


def security_objective_exists(company: Company, year: int | None = None, sector: Sector | None = None) -> bool:
    """Whether the company has a submitted standard answer for that year and sector."""
    if not (year and sector):
        return False

    return company.standardanswer_set.filter(year_of_submission=year, sectors__in=[sector.id], status="PASSM").exists()
