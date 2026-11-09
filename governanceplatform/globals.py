from django.utils.translation import gettext_lazy as _


def get_functionality_choices():
    return FUNCTIONALITIES


def get_api_module_choices():
    return API_MODULES


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

# Modules the read-only API serves, one per viewset `module`. Listed explicitly rather than derived from
# FUNCTIONALITIES: a module belongs here only once it has an endpoint, or granting it would do nothing.
# Incidents is not a functionality: every role reaches it on the web. The APIModuleAccess rows follow
# this dict on every migrate (signals.sync_api_modules).
API_MODULES = {
    "incidents": _("Incident notification"),
    "securityobjectives": FUNCTIONALITIES["securityobjectives"],
    "reporting": FUNCTIONALITIES["reporting"],
}

# Roles a platform admin may grant API access to, per module. The API never widens web access, so
# each list stays within the roles that reach the module on the web.
API_ELIGIBLE_ROLES = {
    "incidents": ["RegulatorAdmin", "RegulatorUser", "OperatorAdmin", "OperatorUser", "IncidentUser", "ObserverAdmin", "ObserverUser"],
    "securityobjectives": FUNCTIONALITY_ELIGIBLE_ROLES["securityobjectives"],
    "reporting": FUNCTIONALITY_ELIGIBLE_ROLES["reporting"],
}

# Crockford base32 omits I, L, O and U so a reference survives being read aloud or
# transcribed from a PDF without being confused for 1 or 0.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERENCE_TOKEN_LENGTH = 8
CROCKFORD_INPUT_TRANSLATION = str.maketrans({"I": "1", "L": "1", "O": "0", "U": "V"})
