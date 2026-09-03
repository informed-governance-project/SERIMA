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
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--reuse",
            action="store_true",
            help=("Default. Reuse every matching configuration object and create only objects whose complete configuration differs."),
        )
        mode.add_argument(
            "--create-all",
            action="store_true",
            help=(
                "Create every object instead of reusing the ones that match. "
                "Unique suffixes are added when required by database constraints."
            ),
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
                    reuse_all=not options["create_all"],
                ).import_configuration()
        except (ConfigurationImportError, IntegrityError) as error:
            raise CommandError(f"Import failed; no changes were saved: {error}") from error

        reminders = result["reminder_emails"]
        rows = (
            ("Reports", result["reports_created"], result["reports_reused"], f"{result['report_links']} linked"),
            (
                "Emails",
                result["emails_created"],
                result["emails_reused"],
                f"{reminders} reminder{'' if reminders == 1 else 's'} created",
            ),
            ("Categories", result["categories_created"], result["categories_reused"], ""),
            ("Category options", result["category_options_created"], result["category_options_reused"], ""),
            ("Questions", result["questions_created"], result["questions_reused"], ""),
            ("Predefined answers", result["predefined_answers_created"], result["predefined_answers_reused"], ""),
            ("Question options", result["question_options_created"], result["question_options_reused"], ""),
            ("Conditional questions", result["conditional_questions_created"], result["conditional_questions_reused"], ""),
            ("Impacts", result["impacts_created"], result["impacts_reused"], ""),
            ("Sectors", result["sectors_created"], result["sectors_reused"], f"{result['sectors_linked']} linked"),
        )
        label_width = max(len(label) for label, *_ in rows)
        created_width = max(len(str(created)) for _, created, _, _ in rows)
        reused_width = max(len(str(reused)) for _, _, reused, _ in rows)

        self.stdout.write(self.style.SUCCESS(f"Imported configuration into SectorRegulation {options['sector_regulation']}"))
        for label, created, reused, extra in rows:
            line = f"  {label:<{label_width}}  {created:>{created_width}} created, {reused:>{reused_width}} reused"
            self.stdout.write(f"{line}, {extra}" if extra else line)
