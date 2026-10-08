from django.utils.translation import gettext_lazy as _

RISK_TREATMENT = [
    ("REDUC", _("Reduction")),
    ("DENIE", _("Deny")),
    ("ACCEP", _("Acceptation")),
    ("SHARE", _("Shared")),
    ("UNTRE", _("Untreated")),
]

TRANSLATIONS_CONTEXT = {
    "domain": _("Domain"),
    "evolution": _("Evolution"),
    "sector_average": _("Sector average"),
    "contact": _("Contact"),
    "downward": _("Downward"),
    "stable": _("Stable"),
    "upward": _("Upward"),
    "sector_ranking": _("Sector ranking"),
    "sector_scores": _("Sector scores"),
    "operator_scores": _("Operator scores"),
    "objective": _("Objective"),
    "id": _("ID"),
    "asset": _("Asset"),
    "threat": _("Threat"),
    "vulnerability": _("Vulnerability"),
    "current_risk_max": _("Current risk (max)"),
    "residual_risk": _("Residual risk"),
    "treatment": _("Treatment"),
    "year": _("Year"),
    "treated_risks": _("Treated Risks"),
    "untreated_risks": _("Untreated Risks"),
    "avg_treated_current_risks": _("Average treated current risks"),
    "high_risks": _("High risks"),
    "avg_high_risks": _("Average high risks"),
    "avg_residual_risks": _("Average residual risks"),
    "reduced_risks": _("Reduced risks"),
    "rejected_risks": _("Rejected risks"),
    "accepted_risks": _("Accepted risks"),
    "shared_risks": _("Shared risks"),
    "recommendation": _("Recommendation"),
    "deadline": _("Deadline"),
    "status": _("Status"),
}

CELERY_TASK_STATUS = [
    ("FAIL", _("Failed")),
    ("DONE", _("Successful")),
    ("ABORT", _("Aborted")),
    ("RUNNING", _("Running")),
]

ALLOWED_DASHBOARD_SORT_FIELDS = {
    "updated_at": {
        "field": "updated_at",
        "type": "datetime",
    },
    "created_at": {
        "field": "created_at",
        "type": "datetime",
    },
    "created_by": {
        "field": "author__first_name",
        "type": "string",
    },
    "name": {
        "field": "name",
        "type": "string",
    },
    "regulation": {
        "field": "standard__regulation__translations__label",
        "type": "string",
    },
    "standard": {
        "field": "standard__translations__label",
        "type": "string",
    },
    "year": {
        "field": "reference_year",
        "type": "number",
    },
    "sectors": {
        "field": "sectors__translations__name",
        "type": "string",
    },
}

ALLOWED_PROJECT_DASHBOARD_SORT_FIELDS = {
    "is_selected": {
        "field": "is_selected",
        "type": "boolean",
    },
    "company": {
        "field": "company__name",
        "type": "datetime",
    },
    "sector": {
        "field": "sector__translations__name",
        "type": "string",
    },
    "year": {
        "field": "year",
        "type": "number",
    },
    "has_security_objectives": {
        "field": "has_security_objectives",
        "type": "boolean",
    },
    "has_risk_assessment": {
        "field": "has_risk_assessment",
        "type": "boolean",
    },
    "statistic_selected": {
        "field": "statistic_selected",
        "type": "boolean",
    },
    "governance_report_selected": {
        "field": "governance_report_selected",
        "type": "boolean",
    },
}
