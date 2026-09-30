import json
import os
import secrets
from pathlib import Path
from typing import NamedTuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now

from governanceplatform.models import Company, CompanyUser, Regulator, RegulatorUser, User
from governanceplatform.permissions import set_platform_admin_permissions

COMPANY_NAME = "Example Operator"
COMPANY_IDENTIFIER = "DEMO"
REGULATOR_NAME = "Example Regulator"
ADDRESS = "1 Demo Street"
CREDENTIALS_FILE = Path(settings.BASE_DIR) / "docs" / "screenshots" / ".fixture-credentials.json"


class Account(NamedTuple):
    email: str
    last_name: str
    password_env: str


# Keyed by the role names in docs/screenshots/shots.toml, which reads its
# credentials back from CREDENTIALS_FILE under the same keys. operator_admin
# comes before operator_user because the first user of an operator must be its
# administrator.
ACCOUNTS = {
    "operator_admin": Account("screenshots-operator-admin@example.org", "Operator Admin", "SERIMA_SHOT_OPERATOR_ADMIN_PASS"),
    "operator_user": Account("screenshots@example.org", "User", "SERIMA_SHOT_OPERATOR_PASS"),
    "regulator_admin": Account("screenshots-regulator-admin@example.org", "Regulator Admin", "SERIMA_SHOT_REGULATOR_ADMIN_PASS"),
    "regulator_user": Account("screenshots-regulator-user@example.org", "Regulator User", "SERIMA_SHOT_REGULATOR_PASS"),
    "platform_admin": Account("screenshots-platform-admin@example.org", "Platform Admin", "SERIMA_SHOT_PLATFORM_PASS"),
}


class Command(BaseCommand):
    help = "Create or remove the throwaway accounts used to capture documentation screenshots"

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--create", action="store_true", help="create the accounts, their operator and their regulator")
        group.add_argument("--delete", action="store_true", help="remove them again")
        parser.add_argument(
            "--password",
            help="password to set on every account; defaults to each role's $SERIMA_SHOT_*_PASS, else generated",
        )

    def handle(self, *args, **options) -> None:
        # The command mints working logins, so it stays out of any deployment
        # where DEBUG is off.
        if not settings.DEBUG:
            raise CommandError("refusing to run with DEBUG off")

        if options["create"]:
            self.create(options.get("password"))
        else:
            self.delete()

    @transaction.atomic
    def create(self, password: str | None) -> None:
        company, _ = Company.objects.get_or_create(
            name=COMPANY_NAME,
            defaults={
                "identifier": COMPANY_IDENTIFIER,
                "country": "LU",
                "address": ADDRESS,
                "email": ACCOUNTS["operator_admin"].email,
            },
        )
        regulator = self.get_or_create_regulator()

        stored = {}
        for role, account in ACCOUNTS.items():
            account_password = password or os.environ.get(account.password_env) or secrets.token_urlsafe(16)
            user, created = User.objects.get_or_create(
                email=account.email,
                defaults={
                    "first_name": "Demo",
                    "last_name": account.last_name,
                    "is_active": True,
                    "accepted_terms": True,
                    "accepted_terms_date": now(),
                },
            )
            user.set_password(account_password)
            user.save()

            # The post_save signals on CompanyUser and RegulatorUser assign the
            # matching group, exactly as when an administrator links a user.
            # A single link per account keeps the company-selection
            # interstitial out of every screenshot.
            if role.startswith("operator_"):
                CompanyUser.objects.update_or_create(
                    user=user,
                    company=company,
                    defaults={"approved": True, "is_company_administrator": role == "operator_admin"},
                )
            elif role.startswith("regulator_"):
                RegulatorUser.objects.update_or_create(
                    user=user,
                    regulator=regulator,
                    defaults={"is_regulator_administrator": role == "regulator_admin"},
                )
            else:
                set_platform_admin_permissions(user)

            stored[role] = {"username": account.email, "password": account_password}
            verb = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{verb} {account.email} ({role})"))

        # Handed to the capture script through a file so nothing has to be
        # exported by hand; readable only by the owner, and gitignored.
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps(stored, indent=2) + "\n")
        CREDENTIALS_FILE.chmod(0o600)
        self.stdout.write(f"credentials written to {CREDENTIALS_FILE}")

    def get_or_create_regulator(self) -> Regulator:
        regulator = Regulator.objects.filter(translations__name=REGULATOR_NAME).first()
        if regulator is None:
            regulator = Regulator(country="LU", address=ADDRESS)
            regulator.set_current_language("en")
            regulator.name = REGULATOR_NAME
            regulator.save()
        return regulator

    @transaction.atomic
    def delete(self) -> None:
        for account in ACCOUNTS.values():
            # Cascades to the account's TOTP device and its operator and
            # regulator links.
            deleted, _ = User.objects.filter(email=account.email).delete()
            self.stdout.write(self.style.SUCCESS(f"removed {account.email}") if deleted else f"{account.email} does not exist")

        CREDENTIALS_FILE.unlink(missing_ok=True)

        if company := Company.objects.filter(name=COMPANY_NAME).first():
            if CompanyUser.objects.filter(company=company).exists():
                self.stdout.write(f"kept {COMPANY_NAME}: other users are still linked to it")
            else:
                company.delete()
                self.stdout.write(self.style.SUCCESS(f"removed {COMPANY_NAME}"))

        if regulator := Regulator.objects.filter(translations__name=REGULATOR_NAME).first():
            if RegulatorUser.objects.filter(regulator=regulator).exists():
                self.stdout.write(f"kept {REGULATOR_NAME}: other users are still linked to it")
            else:
                regulator.delete()
                self.stdout.write(self.style.SUCCESS(f"removed {REGULATOR_NAME}"))
