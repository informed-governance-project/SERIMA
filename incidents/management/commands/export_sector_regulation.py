import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from incidents.configuration_export import SectorRegulationConfigurationExporter
from incidents.models import SectorRegulation


class Command(BaseCommand):
    help = "Export one SectorRegulation configuration to a portable JSON file."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "sector_regulation",
            type=int,
            help="Database primary key of the SectorRegulation to export.",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            help="Output path (default: sector_regulation_<id>.json).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite the output file if it already exists.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        sector_regulation_id = options["sector_regulation"]
        try:
            sector_regulation = (
                SectorRegulation.objects.select_related(
                    "regulation",
                    "regulator",
                    "opening_email",
                    "closing_email",
                    "report_status_changed_email",
                )
                .prefetch_related(
                    "translations",
                    "regulation__translations",
                    "regulator__translations",
                )
                .get(pk=sector_regulation_id)
            )
        except SectorRegulation.DoesNotExist as error:
            raise CommandError(f"SectorRegulation {sector_regulation_id} does not exist.") from error

        output_path = options["output"] or Path(f"sector_regulation_{sector_regulation_id}.json")
        if output_path.exists() and not options["force"]:
            raise CommandError(f"{output_path} already exists. Use --force to overwrite it.")
        if not output_path.parent.exists():
            raise CommandError(f"Output directory {output_path.parent} does not exist.")

        data = SectorRegulationConfigurationExporter(sector_regulation).export()
        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Exported SectorRegulation {sector_regulation_id} to {output_path}"))
