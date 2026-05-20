"""
Data migration: copy non-expired sessions from django_session into the new
UserSession table and populate the user FK from the encoded session data.

Note: decoding requires the application SECRET_KEY that was active when the
sessions were written.  If SECRET_KEY rotated between writes and this
migration, those sessions will fail to decode; user_id will be NULL for them
and they will not benefit from forced-logout-by-user until the next login.
This is acceptable — they will simply expire naturally.
"""

from django.db import migrations


def populate_user_sessions(apps, schema_editor):
    from django.contrib.sessions.backends.db import SessionStore
    from django.utils.timezone import now

    UserSession = apps.get_model("governanceplatform", "UserSession")
    Session = apps.get_model("sessions", "Session")
    db = schema_editor.connection.alias

    rows = Session.objects.using(db).filter(expire_date__gt=now()).values_list(
        "session_key", "session_data", "expire_date"
    )

    to_create = []
    for session_key, session_data, expire_date in rows:
        # SessionStore.decode() returns {} on any decode/signature failure
        decoded = SessionStore().decode(session_data)
        raw_id = decoded.get("_auth_user_id")
        try:
            user_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            user_id = None

        to_create.append(
            UserSession(
                session_key=session_key,
                session_data=session_data,
                expire_date=expire_date,
                user_id=user_id,
            )
        )

    UserSession.objects.using(db).bulk_create(to_create, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("governanceplatform", "0062_usersession"),
        # Ensures django_session table exists before we read from it
        ("sessions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            populate_user_sessions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
