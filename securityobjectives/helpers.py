from typing import TYPE_CHECKING

from .globals import SO_COLUMN_GRID_TOTAL, SO_DECLARATION_COLUMNS

if TYPE_CHECKING:
    from governanceplatform.models import Company, Sector


def security_objective_exists(company: Company, year: int | None = None, sector: Sector | None = None) -> bool:
    """Whether the company has a submitted standard answer for that year and sector."""
    if not (year and sector):
        return False

    return company.standardanswer_set.filter(year_of_submission=year, sectors__in=[sector.id], status="PASSM").exists()


def set_declaration_column_widths(column_config: dict[str, dict[str, str | bool | int]]) -> dict[str, dict[str, str | bool | int]]:
    """Give each column a Bootstrap grid width so the visible ones still span the row.

    The visible columns are scaled up in proportion to the width they have when the
    whole table is shown, so a wide column gains more from a hidden one than a narrow
    column does.
    """
    visible = [key for key in SO_DECLARATION_COLUMNS if column_config[key]["visible"]]
    shown_total = sum(SO_DECLARATION_COLUMNS[key]["width"] for key in visible)
    scaled = {key: SO_DECLARATION_COLUMNS[key]["width"] * SO_COLUMN_GRID_TOTAL / shown_total for key in visible}
    widths = {key: int(width) for key, width in scaled.items()}

    # The grid counts in whole columns, so hand the units lost to truncation to the
    # largest fractions. Ties fall to the registry order, which keeps this stable.
    lost = SO_COLUMN_GRID_TOTAL - sum(widths.values())
    for key in sorted(visible, key=lambda key: scaled[key] - widths[key], reverse=True)[:lost]:
        widths[key] += 1

    for key, column in column_config.items():
        column["width"] = widths.get(key, SO_DECLARATION_COLUMNS[key]["width"])
    return column_config
