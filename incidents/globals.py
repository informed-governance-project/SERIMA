from django.utils.translation import gettext_lazy as _

try:
    from theme.globals import REGIONAL_AREA as regional_area
except ModuleNotFoundError:
    regional_area = []


QUESTION_TYPES = [
    ("FREETEXT", "Freetext"),
    ("MULTI", "Multiple Choice"),
    ("SO", "Single Option Choice"),
    ("MT", "Multiple Choice + Free Text"),
    ("ST", "Single Choice + Free Text"),
    ("CL", "Country list"),
    ("RL", "Region list"),
    ("DATE", "Date picker"),
]

CONDITIONAL_QUESTION_TYPES = ["MULTI", "SO", "MT", "ST"]


# The variables to use in the email template in the admin interface, and the corresponding attribute
INCIDENT_EMAIL_VARIABLES = [
    ("#INCIDENT_NOTIFICATION_DATE#", "incident_notification_date"),
    ("#INCIDENT_DETECTION_DATE#", "incident_detection_date"),
    ("#INCIDENT_STARTING_DATE#", "incident_starting_date"),
    ("#INCIDENT_ID#", "incident_id"),
    ("#DEADLINE#", "get_deadline"),
]

# the different trigger on when to send an email to the Incident.User
INCIDENT_EMAIL_TRIGGER_EVENT = [
    ("NOTIF_DATE", "Notification Date of the workflow"),
    ("PREV_WORK", "Previous Workflow date"),
    ("DETEC_DATE", "Incident detection date"),
]

INCIDENT_STATUS = [
    ("CLOSE", _("Closed")),
    ("GOING", _("Ongoing")),
]

REVIEW_STATUS = [
    ("UNDE", _("Unsubmitted")),
    ("DELIV", _("Under review")),
    ("PASS", _("Passed")),
    ("FAIL", _("Revision required")),
    ("OUT", _("Submission overdue")),
]

WORKFLOW_REVIEW_STATUS = [
    ("UNDE", _("Unsubmitted")),
    ("DELIV", _("Under review")),
    ("PASS", _("Passed")),
    ("FAIL", _("Revision required")),
    ("OUT", _("Submission overdue")),
    ("LATE", _("Late submission")),
]

# after this step the delay is running
SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT = [
    ("NONE", "None"),
    ("NOTIF_DATE", "Notification Date"),
    ("DETECT_DATE", "Detection Date"),
    ("PREV_WORK", "Previous Workflow"),
]


REGIONAL_AREA = regional_area


REPORT_STATUS_MAP = {
    "PASS": {
        "class": "passed",
        "label": _("Passed"),
        "tooltip": _("The report has passed the review."),
    },
    "FAIL": {
        "class": "failed",
        "label": _("Revision required"),
        "tooltip": _("The report has failed the review."),
    },
    "DELIV": {
        "class": "under-review",
        "label": _("Under review"),
        "tooltip": _("The report is currently under review."),
    },
    "LATE": {
        "class": "late-under-review",
        "label": _("Late submission"),
        "tooltip": _("The report is currently under review."),
    },
    "OUT": {
        "class": "overdue",
        "label": _("Submission overdue"),
        "tooltip": _("The submission of the report is overdue."),
    },
    "UNDE": {
        "class": "unsubmitted",
        "label": _("Unsubmitted"),
        "tooltip": _("The report has not been submitted yet."),
    },
}

ALLOWED_SORT_FIELDS = {
    "status": {
        "field": "incident_status",
        "type": "string",
    },
    "last_update": {
        "field": "incident_last_update",
        "type": "datetime",
    },
    "notification_date": {
        "field": "incident_notification_date",
        "type": "datetime",
    },
    "company_identifier": {
        "field": "sort_company_or_regulator_acronym",
        "type": "string",
    },
    "company_name": {
        "field": "sort_company_or_regulator_name",
        "type": "string",
    },
    "regulator": {
        "field": "sector_regulation__regulator__translations__name",
        "type": "string",
    },
    "regulation": {
        "field": "sector_regulation__regulation__translations__label",
        "type": "string",
    },
    "reference": {
        "field": "incident_id",
        "type": "string",
    },
    "sectors": {
        "field": "affected_sectors__translations__name",
        "type": "string",
    },
}
