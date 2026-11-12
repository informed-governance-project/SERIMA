from itertools import groupby
from typing import TYPE_CHECKING

from django.db.models import (
    Case,
    Count,
    Exists,
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
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import is_user_regulator
from governanceplatform.models import Company

from .globals import SO_COLUMN_GRID_TOTAL, SO_DECLARATION_COLUMNS
from .models import SecurityObjectiveStatus, StandardAnswer

if TYPE_CHECKING:
    from governanceplatform.models import Sector, User

    from .models import SecurityObjective, SecurityObjectivesInStandard, Standard


def security_objective_exists(company: Company, year: int | None = None, sector: Sector | None = None) -> bool:
    """Whether the company has a submitted standard answer for that year and sector."""
    if not (year and sector):
        return False

    return (
        company.sectors.filter(id=sector.id).exists()
        and company.standardanswer_set.filter(year_of_submission=year, status="PASSM").exists()
    )


def filter_by_company_sectors(queryset: QuerySet[StandardAnswer], sectors) -> QuerySet[StandardAnswer]:
    """The declarations of the companies the regulator placed in one of the sectors.

    Matched through a subquery rather than a join, so a company in several of the sectors
    does not repeat its declarations.
    """
    return queryset.filter(submitter_company__in=Company.objects.filter(sectors__in=sectors))


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
        # A new version keeps the verdicts of the review it was copied from, so an objective can
        # be fully filled and still wait for the revision the regulator asked for.
        has_failed_objectives=Exists(SecurityObjectiveStatus.objects.filter(standard_answer=OuterRef("pk"), status="FAIL")),
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


def can_see_review_comments(user: User, standard_answer: StandardAnswer) -> bool:
    """Whether the user may read the review comments of the declaration.

    An operator reads them once the review is sent, or on a new version, which carries the
    comments of the review sent on the version it was copied from. While the regulator
    reviews, the comments are a draft.
    """
    if is_user_regulator(user):
        return True
    if standard_answer.is_review_in_progress:
        return False
    return bool(standard_answer.review_comment) or standard_answer.status != "UNDE"


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
        queryset = filter_by_company_sectors(queryset, user.get_sectors().all())

    queryset = queryset.exclude(status="UNDE")

    # Only the most recent declaration of each group reaches the dashboard, and the export
    # has to show the same rows.
    latest_so_id = queryset.filter(group__id=OuterRef("group__id")).order_by("-creation_date").values("id")[:1]
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
    )
    queryset = filter_by_company_sectors(queryset, get_export_sector_ids(user, filters["sectors"]))

    return (
        get_standard_answers_with_progress(queryset)
        .select_related("standard", "group", "submitter_company")
        .prefetch_related("submitter_company__sectors")
        .distinct()
    )


def get_objective_symbol(security_objective: SecurityObjective, standard_answer: StandardAnswer, is_regulator: bool) -> str:
    """The legend symbol of the objective's bullet, as the suffix of its `btn-` class.

    An operator follows how far each objective is filled until the review is sent, except
    on a new version, where an objective the regulator already judged keeps its verdict.
    """
    so_status = getattr(security_objective, "status", None)
    review_status = so_status.status if so_status else None
    follows_filling = (
        not is_regulator
        and not standard_answer.is_review_sent
        and (standard_answer.status != "UNDE" or review_status in (None, "NOT_REVIEWED"))
    )
    if follows_filling:
        state = security_objective.completion_state
        if state["is_completed"]:
            return "passed"
        if state["is_partially"]:
            return "partially"
        return "outline-uninitiated"
    if review_status == "PASS":
        return "passed"
    if review_status == "FAIL":
        return "failed"
    return "partially"


def get_domain_symbol(symbols: list[str], is_regulator: bool) -> str:
    """The one symbol a collapsed domain shows for the symbols of its objectives.

    A regulator's domain stays "not reviewed" until every objective in it is reviewed, so
    "revision required" means the domain's review is complete.
    """
    if is_regulator:
        if "partially" in symbols:
            return "partially"
        if "failed" in symbols:
            return "failed"
        return "passed"
    if "failed" in symbols:
        return "failed"
    if all(symbol == "passed" for symbol in symbols):
        return "passed"
    if all(symbol == "outline-uninitiated" for symbol in symbols):
        return "outline-uninitiated"
    return "partially"


def is_objective_open(symbol: str, is_regulator: bool) -> bool:
    """Whether the objective still needs the user: not fully filled, or not reviewed yet."""
    return symbol == "partially" if is_regulator else symbol != "passed"


def get_navigation_labels(standard_answer: StandardAnswer, is_regulator: bool) -> dict:
    """The legend names of the symbols the bar can show, and how it counts the progress of a domain."""
    if not is_regulator and not standard_answer.is_review_sent:
        return {
            "symbols": {
                "outline-uninitiated": _("Not filled"),
                "partially": _("Partially filled"),
                "passed": _("Fully filled"),
                "failed": _("Revision required"),
            },
            "done_symbols": ["passed"],
            # Translators: read out for a domain of the objective selector, e.g. "D6, Systems and development, 3 of 9 filled".
            "progress": _("%(code)s, %(label)s, %(done)s of %(total)s filled"),
        }
    return {
        "symbols": {
            "partially": _("Not reviewed"),
            "passed": _("Review passed"),
            "failed": _("Revision required"),
        },
        "done_symbols": ["passed", "failed"],
        # Translators: read out for a domain of the objective selector, e.g. "D6, Systems and development, 3 of 9 reviewed".
        "progress": _("%(code)s, %(label)s, %(done)s of %(total)s reviewed"),
    }


def objectives_in_domain_order(standard: Standard) -> QuerySet[SecurityObjectivesInStandard]:
    """The objectives of the standard domain by domain, so their numbers follow the domains first."""
    return (
        standard.security_objectives_set.select_related("security_objective__domain")
        .prefetch_related("security_objective__domain__translations")
        .order_by(
            F("security_objective__domain__position").asc(nulls_last=True),
            "security_objective__domain_id",
            "position",
        )
    )


def group_objectives_by_domain(security_objectives: list[SecurityObjective]) -> list[dict]:
    """Group the objectives by domain, giving each one its domain and its place in it.

    The objectives must already be in their display order, domain by domain.
    """
    domains: list[dict] = []
    for domain, objectives in groupby(security_objectives, key=lambda security_objective: security_objective.domain):
        domains.append(
            {
                "code": f"D{domain.position}" if domain else "–",
                "label": domain.label if domain else _("No domain"),
                "objectives": list(objectives),
            }
        )
    for domain in domains:
        for position, security_objective in enumerate(domain["objectives"], start=1):
            security_objective.nav_domain = domain
            security_objective.nav_position_in_domain = position
    return domains


def build_objective_navigation(security_objectives: list[SecurityObjective], standard_answer: StandardAnswer, is_regulator: bool) -> dict:
    """Group the objectives of the declaration by domain, for the objective selector.

    The objectives must already be in their display order, domain by domain. Each one is
    given its slide index, its number in the bar, its symbol and its domain. The page
    opens on the first objective still to fill or to review.
    """
    domains = group_objectives_by_domain(security_objectives)

    index = 0
    initial_slide = None
    for domain in domains:
        domain["first_open"] = None
        for security_objective in domain["objectives"]:
            security_objective.nav_index = index
            security_objective.nav_number = index + 1
            security_objective.nav_symbol = get_objective_symbol(security_objective, standard_answer, is_regulator)
            if domain["first_open"] is None and is_objective_open(security_objective.nav_symbol, is_regulator):
                domain["first_open"] = index
            index += 1
        domain["symbol"] = get_domain_symbol([so.nav_symbol for so in domain["objectives"]], is_regulator)
        domain["first_number"] = domain["objectives"][0].nav_number
        domain["last_number"] = domain["objectives"][-1].nav_number
        if initial_slide is None:
            initial_slide = domain["first_open"]

    return {
        "domains": domains,
        "is_grouped": len(domains) > 1,
        "initial_slide": initial_slide or 0,
        "shows_failed": any(so.nav_symbol == "failed" for domain in domains for so in domain["objectives"]),
        "rule": "regulator" if is_regulator else "operator",
        "labels": get_navigation_labels(standard_answer, is_regulator),
    }
