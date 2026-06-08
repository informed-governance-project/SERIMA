from datetime import datetime

from django.core.management.base import BaseCommand

from incidents.models import Incident


class Command(BaseCommand):
    help = "Check the incidents which don't have any workflow"

    def add_arguments(self, parser):
        parser.add_argument(
            "-s",
            "--show",
            action="store_true",
            help="show the list of incident which don't have any workflow",
        )

        parser.add_argument(
            "-d",
            "--delete",
            action="store_true",
            help="Delete incidents which don't have any workflow",
        )

    def handle(self, *args, **options):
        # helper safe formatter
        def safe(v, fmt=None):
            if v is None:
                return ""
            if fmt and isinstance(v, (datetime,)):
                try:
                    return v.strftime(fmt)
                except Exception:
                    return str(v)
            return str(v)

        incidents = Incident.objects.filter(sector_regulation__isnull=True)
        show = options.get("show")
        delete = options.get("delete")
        if show:
            # define columns
            headers = ["ID", "Incident Notif Date", "Reference", "Contact email"]
            rows = [
                [
                    safe(i.id),
                    safe(i.incident_notification_date, "%d/%m/%Y - %H:%M:%S"),
                    safe(i.incident_id),
                    safe(i.contact_email),
                ]
                for i in incidents
            ]

            # column width
            col_widths = [max(len(row[col]) for row in ([headers] + rows)) for col in range(len(headers))]

            # Line formatting
            def format_row(row):
                return " | ".join(row[col].ljust(col_widths[col]) for col in range(len(headers)))

            self.stdout.write(self.style.SUCCESS(format_row(headers)))
            self.stdout.write("-" * (sum(col_widths) + (3 * (len(headers) - 1))))

            for row in rows:
                self.stdout.write(format_row(row))

        if delete:
            count = incidents.count()
            if count == 0:
                self.stdout.write(self.style.WARNING("No incidents to delete."))
                return

            confirm = input(f"Are you sure you want to delete {count} incidents? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write(self.style.NOTICE("Deletion cancelled."))
                return

            incidents.delete()
            self.stdout.write(self.style.SUCCESS(f"{count} incidents without workflows deleted"))
