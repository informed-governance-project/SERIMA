import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError, transaction

from incidents.configuration_import import (
    ConfigurationImportError,
    SectorRegulationConfigurationImporter,
)
from incidents.models import SectorRegulation


class Command(BaseCommand):
    help = "Import JSON configuration into an existing blank SectorRegulation."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "input",
            type=Path,
            help="Path to a JSON file created by export_sector_regulation.",
        )
        parser.add_argument(
            "sector_regulation",
            type=int,
            help="Primary key of the blank destination SectorRegulation.",
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--usesectorsandquestions",
            action="store_true",
            help=("Reuse sectors whose acronyms already exist and questions whose references already exist."),
        )
        mode.add_argument(
            "--create",
            action="store_true",
            help=(
                "Create questions even when their references already exist. "
                "Unique suffixes are added when required by database constraints."
            ),
        )
        mode.add_argument(
            "--reuse",
            action="store_true",
            help=("Reuse every matching configuration object and create only objects whose complete configuration differs."),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        input_path = options["input"]
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CommandError(f"{input_path} does not exist.") from error
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Cannot read {input_path}: {error}") from error
        if not isinstance(data, dict):
            raise CommandError("The JSON document must contain an object.")

        try:
            with transaction.atomic():
                try:
                    target = (
                        SectorRegulation.objects.select_for_update()
                        .select_related("regulation", "regulator")
                        .prefetch_related("regulator__translations")
                        .get(pk=options["sector_regulation"])
                    )
                except SectorRegulation.DoesNotExist as error:
                    raise ConfigurationImportError(f"SectorRegulation {options['sector_regulation']} does not exist.") from error

                result = SectorRegulationConfigurationImporter(
                    data,
                    target,
                    create_all=options["create"],
                    reuse_all=options["reuse"],
                ).import_configuration()
        except (ConfigurationImportError, IntegrityError) as error:
            raise CommandError(f"Import failed; no changes were saved: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                "Imported configuration into SectorRegulation "
                f"{options['sector_regulation']}: "
                f"{result['reports_created']} reports created, "
                f"{result['reports_reused']} reports reused, "
                f"{result['report_links']} report links, "
                f"{result['emails_created']} emails created, "
                f"{result['emails_reused']} emails reused, "
                f"{result['categories_created']} categories created, "
                f"{result['categories_reused']} categories reused, "
                f"{result['category_options_created']} category options created, "
                f"{result['category_options_reused']} category options reused, "
                f"{result['questions_created']} questions created, "
                f"{result['questions_reused']} questions reused, "
                f"{result['predefined_answers_created']} predefined answers created, "
                f"{result['predefined_answers_reused']} predefined answers reused, "
                f"{result['predefined_answers_skipped']} predefined answers skipped, "
                f"{result['question_options_created']} question options created, "
                f"{result['question_options_reused']} question options reused, "
                f"{result['conditional_questions_created']} conditional questions created, "
                f"{result['conditional_questions_reused']} conditional questions reused, "
                f"{result['reminder_emails']} reminder emails created, "
                f"{result['impacts_created']} impacts created, "
                f"{result['impacts_reused']} impacts reused, "
                f"{result['sectors_created']} sectors created, "
                f"{result['sectors_reused']} sectors reused, "
                f"{result['sectors_linked']} sectors linked."
            )
        )
