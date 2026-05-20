import hashlib
import secrets
from datetime import timedelta

import pytest
from django.utils.timezone import now

from governanceplatform.models import User, UserSession
from governanceplatform.sessions import SessionStore
from governanceplatform.signals import force_logout_user


@pytest.fixture
def simple_user(db):
    return User.objects.create_user(
        email="sessiontest@example.com",
        password="password",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        password="password",
    )


def _make_session(user=None, expired=False):
    key = hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:40]
    expire = now() + timedelta(seconds=-1 if expired else 3600)
    return UserSession.objects.create(
        session_key=key,
        session_data="",
        expire_date=expire,
        user=user,
    )


@pytest.mark.django_db(transaction=True)
def test_force_logout_deletes_only_target_user_sessions(simple_user, other_user):
    s1 = _make_session(user=simple_user)
    s2 = _make_session(user=simple_user)
    s_other = _make_session(user=other_user)
    s_anon = _make_session(user=None)

    force_logout_user(simple_user)

    remaining = set(UserSession.objects.values_list("session_key", flat=True))
    assert s1.session_key not in remaining
    assert s2.session_key not in remaining
    assert s_other.session_key in remaining
    assert s_anon.session_key in remaining


@pytest.mark.django_db(transaction=True)
def test_force_logout_noop_when_no_sessions(simple_user):
    force_logout_user(simple_user)
    assert UserSession.objects.filter(user=simple_user).count() == 0


@pytest.mark.django_db
def test_session_store_sets_user_id_on_create(simple_user):
    store = SessionStore()
    store["_auth_user_id"] = str(simple_user.pk)
    store.save()

    session = UserSession.objects.get(session_key=store.session_key)
    assert session.user_id == simple_user.pk
    store.delete()


@pytest.mark.django_db
def test_session_store_leaves_user_id_null_for_anonymous():
    store = SessionStore()
    store["foo"] = "bar"
    store.save()

    session = UserSession.objects.get(session_key=store.session_key)
    assert session.user_id is None
    store.delete()
