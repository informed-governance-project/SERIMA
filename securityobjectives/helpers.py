from typing import TYPE_CHECKING

from django.db.models import (
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)

from .globals import SO_COLUMN_GRID_TOTAL, SO_DECLARATION_COLUMNS
from .models import StandardAnswer

if TYPE_CHECKING:
    from governanceplatform.models import Company, Sector, User


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


def get_standard_answers_with_progress(standard_answer_queryset: QuerySet[StandardAnswer]) -> QuerySet[StandardAnswer]:
    return standard_answer_queryset.annotate(
        total_security_objectives=Count(
            "standard__security_objectives",
            distinct=True,
        ),
        total_security_objectives_answered=Count(
            "securityobjectivestatus",
            filter=Q(securityobjectivestatus__is_completely_filled_out=True),
            distinct=True,
        ),
        total_security_objectives_reviewed=Count(
            "securityobjectivestatus",
            filter=~Q(securityobjectivestatus__status="NOT_REVIEWED"),
            distinct=True,
        ),
        reviewed_percentage=Case(
            When(total_security_objectives=0, then=Value(0.0)),
            default=ExpressionWrapper(
                F("total_security_objectives_reviewed") * 100.0 / F("total_security_objectives"),
                output_field=FloatField(),
            ),
        ),
        answered_percentage=Case(
            When(total_security_objectives=0, then=Value(0.0)),
            default=ExpressionWrapper(
                F("total_security_objectives_answered") * 100.0 / F("total_security_objectives"),
                output_field=FloatField(),
            ),
        ),
    )


def can_export_security_objectives(user: User) -> bool:
    """Whether the regulator administrator granted this user the declaration export right.

    Operators and observers are out of scope of the feature, so only a user attached to a
    regulator can hold the right.
    """
    if not user.is_authenticated or not user.is_regulator():
        return False

    regulator = user.regulators.first()
    return bool(
        regulator
        and user.regulatoruser_set.filter(
            regulator=regulator,
            can_export_security_objectives=True,
        ).exists()
    )


def get_export_sector_ids(user: User, selected_sector_ids: list[str | int]) -> set[int]:
    """The selected sectors the user is actually allowed to see.

    Sectors outside the scope are dropped rather than rejected, so a crafted request
    cannot be used to probe which sectors exist beyond the user's own.
    """
    in_scope = set(user.get_sectors().all().values_list("id", flat=True))
    return in_scope & {int(sector_id) for sector_id in selected_sector_ids}


def get_scoped_standard_answers(user: User) -> QuerySet[StandardAnswer]:
    """The declarations the dashboard shows this regulator user, before any filtering."""
    regulator = user.regulators.first()
    queryset = StandardAnswer.objects.filter(standard__regulator=regulator)

    if not user.in_group("RegulatorAdmin"):
        queryset = queryset.filter(sectors__in=user.get_sectors().all())

    queryset = queryset.exclude(status="UNDE")

    # Only the most recent declaration of each group reaches the dashboard, and the export
    # has to show the same rows.
    latest_so_id = queryset.filter(group__id=OuterRef("group__id")).order_by("-last_update").values("id")[:1]
    return queryset.filter(id__in=Subquery(latest_so_id))


def get_exportable_standard_answers(user: User, filters: dict) -> QuerySet[StandardAnswer]:
    """The declarations the user may export, narrowed by the submitted filters.

    The scope is rebuilt from the user on every call, including inside the Celery task, so
    the filters can only narrow what the dashboard would already show them.
    """
    queryset = get_scoped_standard_answers(user).filter(
        standard__regulation_id=filters["regulation"],
        standard_id__in=filters["standards"],
        year_of_submission__in=filters["years"],
        status__in=filters["statuses"],
        sectors__id__in=get_export_sector_ids(user, filters["sectors"]),
    )

    return (
        get_standard_answers_with_progress(queryset)
        .select_related("standard", "group", "submitter_company")
        .prefetch_related("sectors")
        .distinct()
    )
