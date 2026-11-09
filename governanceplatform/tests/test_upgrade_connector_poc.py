import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from governanceplatform.management.commands.upgrade_connector_poc import POC_MIGRATIONS

RENUMBERED_MIGRATIONS = [
    ("governanceplatform", "0071_connectors"),
    ("governanceplatform", "0072_migrate_rt_to_connectors"),
    ("governanceplatform", "0073_remove_observer_rt_fields"),
    ("incidents", "0071_connectordelivery"),
    ("incidents", "0072_migrate_rttickets"),
    ("incidents", "0073_delete_rtticket"),
]


def _record_as_poc_server(poc_migrations):
    """Rewrite django_migrations as a server that ran feat/observer-connectors would have it."""
    recorder = MigrationRecorder(connection)
    for app, name in RENUMBERED_MIGRATIONS:
        recorder.record_unapplied(app, name)
    for app, name in poc_migrations:
        recorder.record_applied(app, name)
    return recorder


@pytest.mark.django_db
def test_a_database_that_never_ran_the_poc_branch_is_left_alone(capsys):
    before = set(MigrationRecorder(connection).applied_migrations())

    call_command("upgrade_connector_poc")

    assert set(MigrationRecorder(connection).applied_migrations()) == before
    assert "No feat/observer-connectors migrations to carry over." in capsys.readouterr().out


@pytest.mark.django_db
def test_a_poc_database_gets_the_renumbered_migrations_recorded():
    recorder = _record_as_poc_server(POC_MIGRATIONS)

    call_command("upgrade_connector_poc", verbosity=0)

    applied = recorder.applied_migrations()
    assert all(migration in applied for migration in RENUMBERED_MIGRATIONS)


@pytest.mark.django_db
def test_a_poc_database_already_carried_over_is_left_alone(capsys):
    _record_as_poc_server(POC_MIGRATIONS)
    call_command("upgrade_connector_poc", verbosity=0)
    capsys.readouterr()

    call_command("upgrade_connector_poc")

    assert "No feat/observer-connectors migrations to carry over." in capsys.readouterr().out


@pytest.mark.django_db
def test_a_partly_migrated_poc_database_stops_the_upgrade():
    recorder = _record_as_poc_server(POC_MIGRATIONS[:4])

    with pytest.raises(CommandError, match="incidents.0066_migrate_rttickets"):
        call_command("upgrade_connector_poc", verbosity=0)

    applied = recorder.applied_migrations()
    assert not any(migration in applied for migration in RENUMBERED_MIGRATIONS)
