"""Create local reviewer accounts without publishing passwords or replacing users."""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from desk.models import User


REVIEWER_USERS = [
    ("reviewer-admin", "admin"),
    ("reviewer-operator", "operator"),
    ("reviewer-client-a", "client"),
    ("reviewer-client-b", "client"),
]


class Command(BaseCommand):
    help = "Create development-only reviewer users; save generated credentials locally."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Reviewer seeding is development-only; DJANGO_DEBUG must be True.")
        path = Path(settings.BASE_DIR) / ".run" / "reviewer-accounts.json"
        credentials = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        with transaction.atomic():
            for username, role in REVIEWER_USERS:
                email = f"{username}@example.test"
                user = User.objects.filter(username=username).first()
                if user is None:
                    if User.objects.filter(email=email).exists():
                        raise CommandError(f"Reviewer email is already in use for {username}; no account was replaced.")
                    password = secrets.token_urlsafe(18)
                    user = User.objects.create_user(
                        username=username, email=email, password=password,
                        name=username.replace("-", " ").title(),
                        organisation="Local assessment review", role=role,
                    )
                    credentials[username] = {"username": username, "role": role, "password": password}
                else:
                    # Never reset an existing user's role, active flag, or password.
                    saved = credentials.get(username)
                    if saved is None or not user.check_password(saved.get("password") or ""):
                        credentials[username] = {"username": username, "role": user.role, "password": None}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(credentials, indent=2) + "\n", encoding="utf-8")
        self.stdout.write("Reviewer setup complete. Credentials: .run/reviewer-accounts.json (local, ignored by Git).")
        self.stdout.write("Existing accounts are unchanged. A null password means use the account's existing password.")
