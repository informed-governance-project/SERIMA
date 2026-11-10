from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

# The connector migrations were numbered 0065-0067 on feat/observer-connectors and renumbered
# after dev's migrations when the feature merged. A server that ran that branch already has
# their changes, under the old names, so a plain `migrate` would try to apply them again.
POC_MIGRATIONS = [
    ("governanceplatform", "0065_connectors"),
    ("governanceplatform", "0066_migrate_rt_to_connectors"),
    ("governanceplatform", "0067_remove_observer_rt_fields"),
    ("incidents", "0065_connectordelivery"),
    ("incidents", "0066_migrate_rttickets"),
    ("incidents", "0067_delete_rtticket"),
]
LAST_DEV_MIGRATIONS = [
    ("governanceplatform", "0071_apikey_company"),
    ("incidents", "0070_alter_answer_options_alter_incident_options_and_more"),
]
RENUMBERED_LEAVES = [
    ("governanceplatform", "0074_remove_observer_rt_fields"),
    ("incidents", "0073_delete_rtticket"),
]


class Command(BaseCommand):
    help = "Brings a database migrated on feat/observer-connectors in line with the renumbered connector migrations"

    def handle(self, *args, **options):
        applied = MigrationRecorder(connection).applied_migrations()
        poc_applied = [migration for migration in POC_MIGRATIONS if migration in applied]

        if not poc_applied or all(leaf in applied for leaf in RENUMBERED_LEAVES):
            self.stdout.write("No feat/observer-connectors migrations to carry over.")
            return

        if len(poc_applied) != len(POC_MIGRATIONS):
            # Faking is only safe when the old migrations ran to the end: anything less and
            # the schema is not what the renumbered migrations would have produced.
            missing = ", ".join(f"{app}.{name}" for app, name in POC_MIGRATIONS if (app, name) not in applied)
            raise CommandError(
                f"feat/observer-connectors migrations are only partly applied (missing: {missing}). Fix the database by hand."
            )

        # dev's own migrations run for real first, so that faking the connector ones marks only them.
        for app, name in LAST_DEV_MIGRATIONS:
            call_command("migrate", app, name, verbosity=options["verbosity"])
        for app, name in RENUMBERED_LEAVES:
            call_command("migrate", app, name, fake=True, verbosity=options["verbosity"])

        self.stdout.write(self.style.SUCCESS("feat/observer-connectors migrations carried over."))
