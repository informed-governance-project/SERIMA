import json
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now
from django_otp.plugins.otp_totp.models import TOTPDevice

from governanceplatform.models import Company, CompanyUser, User

EMAIL = "screenshots@example.org"
FIRST_NAME = "Demo"
LAST_NAME = "User"
COMPANY_NAME = "Example Operator"
COMPANY_IDENTIFIER = "DEMO"
GROUP = "OperatorUser"
CREDENTIALS_FILE = Path(settings.BASE_DIR) / "docs" / "screenshots" / ".fixture-credentials.json"


class Command(BaseCommand):
    help = "Create or remove the throwaway account used to capture documentation screenshots"

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--create", action="store_true", help="create the account and its company")
        group.add_argument("--delete", action="store_true", help="remove them again")
        parser.add_argument(
            "--password",
            help="password to set; defaults to $SERIMA_SHOT_OPERATOR_PASS, else generated",
        )

    def handle(self, *args, **options) -> None:
        # The command mints a working login, so it stays out of any deployment
        # where DEBUG is off.
        if not settings.DEBUG:
            raise CommandError("refusing to run with DEBUG off")

        if options["create"]:
            self.create(options.get("password") or os.environ.get("SERIMA_SHOT_OPERATOR_PASS"))
        else:
            self.delete()

    @transaction.atomic
    def create(self, password: str | None) -> None:
        password = password or secrets.token_urlsafe(16)

        company, _ = Company.objects.get_or_create(
            name=COMPANY_NAME,
            defaults={"identifier": COMPANY_IDENTIFIER, "country": "LU", "address": "1 Demo Street", "email": EMAIL},
        )

        user, created = User.objects.get_or_create(
            email=EMAIL,
            defaults={
                "first_name": FIRST_NAME,
                "last_name": LAST_NAME,
                "is_active": True,
                "accepted_terms": True,
                "accepted_terms_date": now(),
            },
        )
        user.set_password(password)
        user.save()
        user.groups.set([Group.objects.get(name=GROUP)])

        # A single approved company keeps the company-selection interstitial out
        # of every screenshot.
        CompanyUser.objects.update_or_create(
            user=user,
            company=company,
            defaults={"approved": True, "is_company_administrator": False},
        )

        # Handed to the capture script through a file so nothing has to be
        # exported by hand; readable only by the owner, and gitignored.
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps({"username": EMAIL, "password": password}, indent=2) + "\n")
        CREDENTIALS_FILE.chmod(0o600)

        verb = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {EMAIL} in {COMPANY_NAME}"))
        self.stdout.write(f"credentials written to {CREDENTIALS_FILE}")

    @transaction.atomic
    def delete(self) -> None:
        user = User.objects.filter(email=EMAIL).first()
        if user is None:
            self.stdout.write(f"{EMAIL} does not exist")
        else:
            TOTPDevice.objects.filter(user=user).delete()
            CompanyUser.objects.filter(user=user).delete()
            user.delete()
            self.stdout.write(self.style.SUCCESS(f"removed {EMAIL}"))

        CREDENTIALS_FILE.unlink(missing_ok=True)

        company = Company.objects.filter(name=COMPANY_NAME).first()
        if company is None:
            return

        if CompanyUser.objects.filter(company=company).exists():
            self.stdout.write(f"kept {COMPANY_NAME}: other users are still linked to it")
        else:
            company.delete()
            self.stdout.write(self.style.SUCCESS(f"removed {COMPANY_NAME}"))
