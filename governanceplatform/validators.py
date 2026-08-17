import ipaddress
import socket
from urllib.parse import urlparse

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Nothing trims PasswordUserHistory, so the table grows for the lifetime of an account.
# Comparing every entry would let one password-change attempt force unbounded hashing.
PASSWORD_HISTORY_DEPTH = 24


class NoReusePasswordValidator:
    """
    Validator to ensure users don't reuse previously used passwords.
    """

    def validate(self, password, user=None):
        if not user or user.pk is None:
            return

        # hashers.check_password is used rather than user.check_password: the model method
        # installs a setter that rehashes and calls save() whenever a match needs a hash
        # upgrade, which would persist the very password this validator is about to reject.
        if check_password(password, user.password):
            raise ValidationError(
                _("Your new password must differ from your current password."),
                code="password_same_as_current",
            )

        # Each comparison costs a full password hash, so bound the work one attempt can force.
        previous_hashes = user.passworduserhistory_set.order_by("-timestamp").values_list("hashed_password", flat=True)[
            :PASSWORD_HISTORY_DEPTH
        ]

        for previous_hash in previous_hashes:
            if check_password(password, previous_hash):
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
