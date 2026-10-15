from typing import TypedDict

from django.utils.translation import gettext_lazy as _


def get_functionality_choices():
    return FUNCTIONALITIES


# New flag used for logs
ADDITION = 1
CHANGE = 2
DELETION = 3
VIEW = 4
CONNECTION = 5
DECONNECTION = 6
EXPORT = 7

ACTION_FLAG_CHOICES = {
    ADDITION: _("Addition"),
    CHANGE: _("Modification"),
    DELETION: _("Deletion"),
    # VIEW: _('View'),
    CONNECTION: _("Login"),
    DECONNECTION: _("Logout"),
    EXPORT: _("Export"),
}

# Functionalities list
FUNCTIONALITIES = {
    "securityobjectives": _("Security Objective"),
    "reporting": _("Reporting"),
}

# Roles a platform admin may enable on each functionality. A role left out here can
# never reach the module, so offering it in the admin would be a switch that does nothing.
FUNCTIONALITY_ELIGIBLE_ROLES = {
    "securityobjectives": ["RegulatorAdmin", "RegulatorUser", "OperatorAdmin", "OperatorUser"],
    "reporting": ["RegulatorAdmin", "RegulatorUser"],
}

# Crockford base32 omits I, L, O and U so a reference survives being read aloud or
# transcribed from a PDF without being confused for 1 or 0.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERENCE_TOKEN_LENGTH = 8
CROCKFORD_INPUT_TRANSLATION = str.maketrans({"I": "1", "L": "1", "O": "0", "U": "V"})

# List pages whose display choices are kept per user across sessions (UserPreference).
# Column names follow the table's data-sort-field so they survive columns being added
# or reordered; a column whose content depends on the role gets one neutral name.
INCIDENT_LIST_COLUMNS = (
    "status",
    "last_update",
    "notification_date",
    "detection_date",
    "starting_date",
    "resolution_date",
    "company_identifier",
    "company_name",
    "regulator",
    "regulation",
    "reference",
    "sectors",
    "report",
)
INCIDENT_LIST_HIDDEN_COLUMNS = ("detection_date", "starting_date", "resolution_date", "reference")


class ListPreferencePage(TypedDict, total=False):
    aspects: tuple[str, ...]
    # A key of the module's ALLOWED_SORT_FIELDS, and the direction.
    default_sort: tuple[str, str]
    columns: tuple[str, ...]
    hidden_columns: tuple[str, ...]


LIST_PREFERENCE_PAGES: dict[str, ListPreferencePage] = {
    "incidents": {
        "aspects": ("filters", "sort", "columns", "legend"),
        "default_sort": ("last_update", "desc"),
        "columns": INCIDENT_LIST_COLUMNS,
        "hidden_columns": INCIDENT_LIST_HIDDEN_COLUMNS,
    },
    "regulator_incidents": {
        "aspects": ("filters", "sort", "columns", "legend"),
        "default_sort": ("last_update", "desc"),
        "columns": INCIDENT_LIST_COLUMNS,
        "hidden_columns": INCIDENT_LIST_HIDDEN_COLUMNS,
    },
    "securityobjectives": {
        "aspects": ("filters", "sort", "columns", "legend"),
        "default_sort": ("last_update", "desc"),
        "columns": (
            "status",
            "last_update",
            "submit_date",
            "identifier",
            "framework",
            "company",
            "sectors",
            "year",
            "progress",
        ),
    },
    "so_declaration": {
        "aspects": ("legend",),
    },
    "reporting": {
        "aspects": ("filters", "sort", "columns"),
        "default_sort": ("updated_at", "desc"),
        "columns": ("updated_at", "created_at", "created_by", "name", "regulation", "standard", "year", "sectors"),
    },
    "reporting_project_dashboard": {
        "aspects": ("filters", "sort"),
        "default_sort": ("company", "desc"),
    },
    "report_recommendations": {
        "aspects": ("filters",),
    },
}

# Written by the preferences endpoint; filters and sort are written by the list views.
CLIENT_PREFERENCE_ASPECTS = ("columns", "legend")

# Kept in the session only: a search or a page number carried into the next login would
# hide rows without the user remembering why.
SESSION_ONLY_LIST_PARAMS = ("search", "page")

# Shared by every list: they all render the same pagination component. Keep it ascending:
# the template reads the first entry as the smallest page size, below which it hides pagination.
PER_PAGE_CHOICES = (10, 25, 50, 100)
DEFAULT_PER_PAGE = 10
