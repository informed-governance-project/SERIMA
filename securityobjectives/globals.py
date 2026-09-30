from django.utils.translation import gettext_lazy as _

# Marks a group id as a security objectives declaration
REFERENCE_PREFIX = "SO_"

STANDARD_ANSWER_REVIEW_STATUS = [
    ("UNDE", _("Unsubmitted")),
    ("DELIV", _("Under review")),
    ("PASS", _("Passed")),
    ("PASSM", _("Passed and sent")),
    ("FAIL", _("Revision required")),
    ("FAILM", _("Revision required and sent")),
]

SO_EMAIL_VARIABLES = [
    ("#SO_REFERENCE#", "group_id"),
]

# Internal state of the export job, polled by the browser and never shown to a user.
SO_EXPORT_STATUS = [
    ("RUNNING", "Running"),
    ("DONE", "Successful"),
    ("FAIL", "Failed"),
]

SO_EXPORT_DIRECTORY = "security_objectives_exports"

# Columns of the export, in the order and with the labels the dashboard uses.
SO_EXPORT_COLUMNS = [
    _("Status"),
    _("Last update"),
    _("Submission date"),
    _("Identifier"),
    _("Evaluation Framework"),
    _("Company"),
    _("Sectors"),
    _("Year"),
    _("Progress"),
]

ALLOWED_SORT_FIELDS = {
    "status": {
        "field": "status",
        "type": "string",
    },
    "last_update": {
        "field": "last_update",
        "type": "datetime",
    },
    "submit_date": {
        "field": "submit_date",
        "type": "datetime",
    },
    "identifier": {
        "field": "group__group_id",
        "type": "string",
    },
    "framework": {
        "field": "standard__translations__label",
        "type": "string",
    },
    "company_name": {
        "field": "creator_company_name",
        "type": "string",
    },
    "creator": {
        "field": "creator_name",
        "type": "string",
    },
    "sectors": {
        "field": "sectors__translations__name",
        "type": "string",
    },
    "year": {
        "field": "year_of_submission",
        "type": "number",
    },
    "reviewed_percentage": {
        "field": "reviewed_percentage",
        "type": "number",
    },
}

# Columns of the security objectives declaration table, in render order. The key
# doubles as the suffix of the per-Standard override fields (e.g. "evidence" ->
# Standard.evidence_label, Standard.show_evidence_column). "toggleable" marks the
# columns an admin may hide; the rest always render.
# The widths are the Bootstrap grid columns each one spans when the whole table is
# shown, and they total SO_COLUMN_GRID_TOTAL.
SO_DECLARATION_COLUMNS = {
    "maturity_level": {"label": _("Maturity level"), "width": 1, "toggleable": True},
    "security_measure": {"label": _("Security Measure"), "width": 3},
    "evidence": {"label": _("Evidence"), "width": 3, "toggleable": True},
    "is_implemented": {"label": _("Measure Implemented?"), "width": 1},
    "justification": {"label": _("Justification"), "width": 2, "toggleable": True},
    "review_comment": {"label": _("Review comment"), "width": 2, "toggleable": True},
}

# The planned measures row spans the whole table rather than occupying a column,
# so it carries no grid width and stays out of SO_DECLARATION_COLUMNS.
SO_ACTIONS_LABEL = _("Planned Measures")

SO_COLUMN_GRID_TOTAL = 12

# How the security objective score is presented on the declaration page and in the
# PDF export. Hiding the maximum keeps the score itself, which suits a standard
# whose maturity levels are not a scale out of a meaningful total.
SO_SCORE_DISPLAY = [
    ("FULL", _("Score and maximum")),
    ("SCORE", _("Score only")),
    ("NONE", _("Hidden")),
]
