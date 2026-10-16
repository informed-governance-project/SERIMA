import logging
import os
from collections import defaultdict
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Max, Min
from django.template.loader import render_to_string
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from governanceplatform.helpers import is_user_regulator
from governanceplatform.utils.weasyprint_fetcher import RestrictedURLFetcher

from .globals import OPERATOR_STATUS, STANDARD_ANSWER_REVIEW_STATUS
from .helpers import can_see_review_comments, set_declaration_column_widths
from .models import MaturityLevel, SecurityMeasureAnswer, SecurityObjectiveStatus

if TYPE_CHECKING:
    from governanceplatform.models import User

    from .models import StandardAnswer

# Increasing weasyprint log level
for logger_name in ["weasyprint", "fontTools", "fontTools.subset"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)


def get_review_status_label(standard_answer: StandardAnswer, user: User) -> str:
    """The review status on the cover, which does not say whether the review was sent."""
    status = standard_answer.status
    if not is_user_regulator(user):
        status = OPERATOR_STATUS[status]
    status = {"PASSM": "PASS", "FAILM": "FAIL"}.get(status, status)
    return dict(STANDARD_ANSWER_REVIEW_STATUS)[status]


def get_declaration_pdf(standard_answer: StandardAnswer, user: User) -> bytes:
    """
    Renders a declaration as the given user sees it: an operator gets neither the review
    comments nor the verdict while the regulator is still reviewing.

    The standard answer must come from get_standard_answers_with_progress, whose
    annotations the template reads.
    """
    standard = standard_answer.standard
    show_review_comments = can_see_review_comments(user, standard_answer)

    levels = MaturityLevel.objects.filter(standard=standard).aggregate(first_level=Min("level"), last_level=Max("level"))
    security_objectives_queryset = standard.security_objectives_set.all().order_by("position")
    security_objectives = defaultdict(lambda: defaultdict(list))

    for so_in_standard in security_objectives_queryset:
        security_objective = so_in_standard.security_objective
        security_objective.declaration_status = standard_answer.status
        security_measures = security_objective.securitymeasure_set.all().order_by("position")
        try:
            so_status = SecurityObjectiveStatus.objects.get(
                standard_answer=standard_answer,
                security_objective=security_objective,
            )
            security_objective.status = so_status
        except SecurityObjectiveStatus.DoesNotExist:
            security_objective.status = None

        for measure in security_measures:
            try:
                sm_answer = SecurityMeasureAnswer.objects.get(
                    standard_answer=standard_answer,
                    security_measure=measure,
                )
                measure.is_implemented = sm_answer.is_implemented
                measure.justification = sm_answer.justification
                measure.review_comment = sm_answer.review_comment if show_review_comments else None
            except SecurityMeasureAnswer.DoesNotExist:
                measure.is_implemented = False

            security_objective = measure.security_objective
            maturity_level = measure.maturity_level
            security_objectives[security_objective][maturity_level].append(measure)

    security_objectives = {so: dict(levels) for so, levels in security_objectives.items()}
    static_theme_dir = settings.STATIC_THEME_DIR
    font_config = FontConfiguration()

    column_config = standard.get_column_config()
    column_config["review_comment"]["visible"] = column_config["review_comment"]["visible"] and show_review_comments
    set_declaration_column_widths(column_config)

    output_from_parsed_template = render_to_string(
        "report/security_objectives/template.html",
        {
            "last_maturity_level": levels["last_level"],
            "standard_answer": standard_answer,
            "review_status": get_review_status_label(standard_answer, user),
            "show_objective_status": is_user_regulator(user) or standard_answer.is_review_sent,
            "security_objectives": security_objectives,
            "column_config": column_config,
            "visible_column_count": sum(1 for column in column_config.values() if column["visible"]),
            "score_display": standard.get_score_display_config(),
            "actions_config": standard.get_actions_config(),
        },
    )

    htmldoc = HTML(
        string=output_from_parsed_template,
        base_url=static_theme_dir,
        url_fetcher=RestrictedURLFetcher(),
    )

    stylesheets = [
        CSS(os.path.join(static_theme_dir, "css/custom.css"), font_config=font_config),
        CSS(os.path.join(static_theme_dir, "css/report.css"), font_config=font_config),
    ]

    return htmldoc.write_pdf(stylesheets=stylesheets, font_config=font_config)
