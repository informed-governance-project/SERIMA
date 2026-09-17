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
FUNCTIONALITIES = {"securityobjectives": _("Security objective")}

# Crockford base32 omits I, L, O and U so a reference survives being read aloud or
# transcribed from a PDF without being confused for 1 or 0.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERENCE_TOKEN_LENGTH = 8
CROCKFORD_INPUT_TRANSLATION = str.maketrans({"I": "1", "L": "1", "O": "0", "U": "V"})
