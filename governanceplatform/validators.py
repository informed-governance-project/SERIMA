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


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # ::ffff:127.0.0.1 reaches the same host as 127.0.0.1, so judge it on its IPv4 form.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def resolve_rt_url(base_url: str) -> list[str]:
    """
    Validate an RT URL and return every address it currently resolves to.

    Every A and AAAA record has to be safe: a host answering with one public and one
    internal address would otherwise be reachable on retry. DNS can still change between
    this call and the connection, so callers must validate immediately before requesting.
    """
    parsed = urlparse(base_url)

    if parsed.scheme != "https":
        raise ValidationError(_("Only HTTPS allowed"))

    if parsed.username or parsed.password:
        raise ValidationError(_("Credentials in URL are not allowed"))

    if not parsed.hostname:
        raise ValidationError(_("Invalid host"))

    try:
        # Reading .port also validates it: an out-of-range port raises ValueError here.
        addr_info = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValidationError(_("Invalid host")) from exc

    addresses = []
    for *_unused, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_internal(ip):
            raise ValidationError(_("Internal addresses are not allowed"))
        addresses.append(str(ip))

    if not addresses:
        raise ValidationError(_("Invalid host"))

    return addresses


def validate_rt_url(base_url: str) -> bool:
    """Field validator for Observer.rt_url. Referenced by name in migration 0056."""
    resolve_rt_url(base_url)
    return True
