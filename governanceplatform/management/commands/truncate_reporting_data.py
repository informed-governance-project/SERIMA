from django.core.management.base import BaseCommand
from django.db import connection, transaction

TABLES = [
    # Security Objectives
    "securityobjectives_standardanswer_sectors",
    "securityobjectives_logstandardanswer",
    "securityobjectives_securityobjectivestatus",
    "securityobjectives_securitymeasureanswer",
    "securityobjectives_standardanswer",
    "securityobjectives_standardanswergroup",
    # Reporting
    "reporting_riskdata_recommendations",
    "reporting_riskdata",
    "reporting_servicestat",
    "reporting_companyproject",
    "reporting_companyreporting",
    "reporting_generatedreport",
    "reporting_logreporting",
    "reporting_project_sectors",
    "reporting_project",
    "reporting_observationrecommendationthrough",
    "reporting_observationrecommendation_sectors",
    "reporting_observationrecommendation_translation",
    "reporting_observationrecommendation",
    "reporting_observation",
    "reporting_sectorreportconfiguration_so_excluded",
    "reporting_sectorreportconfiguration",
    "reporting_assetdata_translation",
    "reporting_assetdata",
    "reporting_threatdata_translation",
    "reporting_threatdata",
    "reporting_vulnerabilitydata_translation",
    "reporting_vulnerabilitydata",
    "reporting_recommendationdata",
]


class Command(BaseCommand):
    help = "Truncate all reporting and security objectives tables."

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
