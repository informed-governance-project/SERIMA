import ipaddress
import socket
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class NoReusePasswordValidator:
    """
    Validator to ensure users don't reuse previously used passwords.
    """

    def validate(self, password, user=None):
        if not user or user.pk is None:
            return

        if user.check_password(password):
            raise ValidationError(
                _("Your new password must differ from your current password."),
                code="password_same_as_current",
            )

        old_passwords = user.passworduserhistory_set.all().values_list("hashed_password", flat=True)

        for old_password in old_passwords:
            # Temporarily set the old hashed password
            user.password = old_password
            if user.check_password(password):
                raise ValidationError(
                    _("Reusing a previously used password is not permitted."),
                    code="password_reuse",
                )

    def get_help_text(self):
        return _("Your password must not match any previously used passwords.")


def validate_rt_url(base_url: str):
    parsed = urlparse(base_url)

    if parsed.scheme != "https":
        raise ValidationError(_("Only HTTPS allowed"))

    if parsed.username or parsed.password:
        raise ValidationError(_("Credentials in URL are not allowed"))

    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    except Exception:
        raise ValidationError(_("Invalid host"))

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValidationError(_("Internal addresses are not allowed"))

    return True
