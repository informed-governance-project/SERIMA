from django.core.management.base import BaseCommand
from django.db import connection, transaction

TABLES = [
    # Django
    "django_session",
    "django_admin_log",
    # Captcha
    "captcha_captchastore",
    # Governance
    "governanceplatform_scriptlogentry",
    "governanceplatform_usersession",
    # Answers
    "incidents_answer_predefined_answers",
    "incidents_answer",
    # Incident workflow
    "incidents_incidentworkflow_impacts",
    "incidents_incidentworkflow",
    "incidents_logreportread",
    "incidents_reporttimeline",
    "incidents_rtticket",
    # Incident
    "incidents_incident_affected_services",
    "incidents_incident_affected_sectors",
    "incidents_incident_impacts",
    "incidents_incident_authorities",
    "incidents_incident",
]


class Command(BaseCommand):
    help = "Truncate all incident data while keeping configuration data (workflows, regulators, regulations, sectors, questions, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Actually perform the truncation.",
        )

    def handle(self, *args, **options):
        if not options["force"]:
            self.stdout.write(self.style.WARNING("This command will permanently delete all data.\nRun again with --force to continue."))
            return

        sql = "TRUNCATE TABLE " + ", ".join(f'"{table}"' for table in TABLES) + " RESTART IDENTITY CASCADE;"

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS(f"Successfully truncated {len(TABLES)} tables."))
