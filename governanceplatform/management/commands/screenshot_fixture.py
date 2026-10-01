import json
import os
import secrets
from pathlib import Path
from typing import NamedTuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now
from django_otp.plugins.otp_totp.models import TOTPDevice

from governanceplatform.models import User
from governanceplatform.permissions import set_platform_admin_permissions

SCREENSHOTS_DIR = Path(settings.BASE_DIR) / "docs" / "screenshots"
FIXTURE = SCREENSHOTS_DIR / "fixture.json"
CREDENTIALS_FILE = SCREENSHOTS_DIR / ".fixture-credentials.json"


class Account(NamedTuple):
    email: str
    password_env: str


# Keyed by the role names in docs/screenshots/shots.toml, which reads its
# credentials back from CREDENTIALS_FILE under the same keys. The accounts, and
# the operators, regulators and observer they belong to, come from FIXTURE.
ACCOUNTS = {
    "operator_admin": Account("operator-admin@example.org", "SERIMA_SHOT_OPERATOR_ADMIN_PASS"),
    "operator_user": Account("operator-user@example.org", "SERIMA_SHOT_OPERATOR_PASS"),
    "regulator_admin": Account("regulator-admin@example.org", "SERIMA_SHOT_REGULATOR_ADMIN_PASS"),
    "regulator_user": Account("regulator-user@example.org", "SERIMA_SHOT_REGULATOR_PASS"),
    "observer_admin": Account("observer-admin@example.org", "SERIMA_SHOT_OBSERVER_ADMIN_PASS"),
    "platform_admin": Account("platform-admin@example.org", "SERIMA_SHOT_PLATFORM_PASS"),
}


class Command(BaseCommand):
    help = "Give the screenshot accounts of docs/screenshots/fixture.json a password, or take it away again"

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--create", action="store_true", help="set a password on every account and reset its 2FA")
        group.add_argument("--delete", action="store_true", help="make every account unusable again")
        parser.add_argument(
            "--password",
            help="password to set on every account; defaults to each role's $SERIMA_SHOT_*_PASS, else generated",
        )

    def handle(self, *args, **options) -> None:
        # The command mints working logins, so it stays out of any deployment
        # where DEBUG is off.
        if not settings.DEBUG:
            raise CommandError("refusing to run with DEBUG off")

        users = {role: User.objects.filter(email=account.email).first() for role, account in ACCOUNTS.items()}
        if missing := [ACCOUNTS[role].email for role, user in users.items() if user is None]:
            raise CommandError(f"{', '.join(missing)} not found: load the fixture first (manage.py loaddata {FIXTURE})")

        if options["create"]:
            self.create(users, options.get("password"))
        else:
            self.delete(users)

    @transaction.atomic
    def create(self, users: dict[str, User], password: str | None) -> None:
        stored = {}
        for role, user in users.items():
            account = ACCOUNTS[role]
            account_password = password or os.environ.get(account.password_env) or secrets.token_urlsafe(16)
            user.set_password(account_password)
            user.accepted_terms = True
            user.accepted_terms_date = now()
            user.save()
            # The 2FA enrolment shots need an account with no device, and they
            # leave one behind when they complete the wizard.
            TOTPDevice.objects.filter(user=user).delete()
            if role == "platform_admin":
                set_platform_admin_permissions(user)

            stored[role] = {"username": user.email, "password": account_password}
            self.stdout.write(self.style.SUCCESS(f"set a password on {user.email} ({role})"))

        # Handed to the capture script through a file so nothing has to be
        # exported by hand; readable only by the owner, and gitignored.
        CREDENTIALS_FILE.write_text(json.dumps(stored, indent=2) + "\n")
        CREDENTIALS_FILE.chmod(0o600)
        self.stdout.write(f"credentials written to {CREDENTIALS_FILE}")

    @transaction.atomic
    def delete(self, users: dict[str, User]) -> None:
        # The accounts stay: incidents, declarations and logs in the fixture
        # point at them. Only the ability to log in goes.
        for user in users.values():
            user.set_unusable_password()
            user.save()
            TOTPDevice.objects.filter(user=user).delete()
            self.stdout.write(self.style.SUCCESS(f"{user.email} can no longer log in"))

        CREDENTIALS_FILE.unlink(missing_ok=True)
