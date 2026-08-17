"""
SSRF guard for Observer.rt_url.

DNS is stubbed throughout: these must not depend on whichever resolver CI happens to have.
"""

import socket

import pytest
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError

from governanceplatform.models import PasswordUserHistory, User
from governanceplatform.validators import (
    PASSWORD_HISTORY_DEPTH,
    NoReusePasswordValidator,
    resolve_rt_url,
    validate_rt_url,
)


def _stub_dns(monkeypatch, *addresses):
    """Make getaddrinfo answer with the given addresses, IPv4 or IPv6."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        infos = []
        for address in addresses:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
            infos.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
        return infos

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def test_accepts_public_https_host(monkeypatch):
    _stub_dns(monkeypatch, "93.184.216.34")

    assert resolve_rt_url("https://rt.example.org") == ["93.184.216.34"]
    assert validate_rt_url("https://rt.example.org") is True


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://rt.example.org", "plain HTTP"),
        ("ftp://rt.example.org", "non-HTTP scheme"),
        ("https://user:secret@rt.example.org", "credentials in the URL"),
        ("https://", "no hostname"),
        ("/REST/2.0/ticket", "no scheme"),
    ],
)
def test_rejects_malformed_url(monkeypatch, url, reason):
    _stub_dns(monkeypatch, "93.184.216.34")

    with pytest.raises(ValidationError):
        resolve_rt_url(url)


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("127.0.0.1", "loopback"),
        ("10.0.0.5", "private class A"),
        ("192.168.1.10", "private class C"),
        ("172.16.0.1", "private class B"),
        ("169.254.169.254", "cloud metadata endpoint"),
        ("0.0.0.0", "unspecified"),
        ("224.0.0.1", "multicast"),
        ("240.0.0.1", "reserved"),
        ("::1", "IPv6 loopback"),
        ("fd00::1", "IPv6 unique local"),
        ("fe80::1", "IPv6 link local"),
        ("::ffff:127.0.0.1", "IPv4-mapped loopback"),
    ],
)
def test_rejects_internal_address(monkeypatch, address, reason):
    _stub_dns(monkeypatch, address)

    with pytest.raises(ValidationError):
        resolve_rt_url("https://rt.example.org")


def test_rejects_when_any_record_is_internal(monkeypatch):
    """A host answering with one public and one internal address is unsafe."""
    _stub_dns(monkeypatch, "93.184.216.34", "127.0.0.1")

    with pytest.raises(ValidationError):
        resolve_rt_url("https://rt.example.org")


def test_rejects_unresolvable_host(monkeypatch):
    def boom(*args, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", boom)

    with pytest.raises(ValidationError):
        resolve_rt_url("https://nonexistent.invalid")


def test_rejects_out_of_range_port(monkeypatch):
    _stub_dns(monkeypatch, "93.184.216.34")

    with pytest.raises(ValidationError):
        resolve_rt_url("https://rt.example.org:99999")


def test_returns_every_resolved_address(monkeypatch):
    """All records are returned so a caller can see exactly what was approved."""
    _stub_dns(monkeypatch, "93.184.216.34", "2606:2800:220:1::1")

    assert resolve_rt_url("https://rt.example.org") == ["93.184.216.34", "2606:2800:220:1::1"]


@pytest.fixture
def user_with_history(db):
    """A user whose stored history entry uses a weaker hasher than the current default."""
    user = User.objects.create(email="reuse@example.org")
    user.set_password("current-password")
    user.save()
    # An outdated hash is what makes Django's check_password want to rehash and save.
    PasswordUserHistory.objects.create(
        user=user,
        hashed_password=make_password("old-password-1", hasher="pbkdf2_sha1"),
    )
    return user


@pytest.mark.django_db()
def test_rejects_reused_password(user_with_history):
    with pytest.raises(ValidationError):
        NoReusePasswordValidator().validate("old-password-1", user_with_history)


@pytest.mark.django_db()
def test_rejects_current_password(user_with_history):
    with pytest.raises(ValidationError):
        NoReusePasswordValidator().validate("current-password", user_with_history)


@pytest.mark.django_db()
def test_accepts_unused_password(user_with_history):
    assert NoReusePasswordValidator().validate("a-brand-new-password", user_with_history) is None


@pytest.mark.django_db()
def test_rejecting_a_reused_password_does_not_store_it(user_with_history):
    """
    user.check_password() rehashes and saves on a match that needs upgrading, which would
    persist the rejected password. Validation must leave the stored credential untouched.
    """
    stored_before = User.objects.get(pk=user_with_history.pk).password

    with pytest.raises(ValidationError):
        NoReusePasswordValidator().validate("old-password-1", user_with_history)

    reloaded = User.objects.get(pk=user_with_history.pk)
    assert reloaded.password == stored_before
    assert reloaded.check_password("current-password")
    assert not reloaded.check_password("old-password-1")


@pytest.mark.django_db()
def test_validation_leaves_the_in_memory_user_unchanged(user_with_history):
    """The validator must not leave a historical hash on the instance it was handed."""
    password_before = user_with_history.password

    NoReusePasswordValidator().validate("a-brand-new-password", user_with_history)

    assert user_with_history.password == password_before


@pytest.mark.django_db()
def test_only_the_most_recent_history_entries_are_compared(user_with_history):
    """Older entries beyond the cap are not hashed against, bounding the work per attempt."""
    for index in range(PASSWORD_HISTORY_DEPTH + 1):
        PasswordUserHistory.objects.create(
            user=user_with_history,
            hashed_password=make_password(f"filler-{index}", hasher="pbkdf2_sha1"),
        )

    # "old-password-1" is now the oldest entry, pushed past the cap by the fillers.
    assert NoReusePasswordValidator().validate("old-password-1", user_with_history) is None
