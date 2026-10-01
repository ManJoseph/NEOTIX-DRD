import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import User


class ReviewerSeedTests(TestCase):
    def test_seed_creates_hashed_accounts_and_repeat_preserves_credentials(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory), DEBUG=True):
            output = StringIO()
            call_command("seed_reviewers", stdout=output)
            path = Path(directory) / ".run" / "reviewer-accounts.json"
            first = json.loads(path.read_text())
            self.assertEqual(User.objects.count(), 4)
            for username, account in first.items():
                user = User.objects.get(username=username)
                self.assertEqual(user.role, account["role"])
                self.assertTrue(user.check_password(account["password"]))
                self.assertNotEqual(user.password, account["password"])
                self.assertNotIn(account["password"], output.getvalue())
                self.assertFalse(user.is_superuser)
            call_command("seed_reviewers", stdout=StringIO())
            self.assertEqual(User.objects.count(), 4)
            self.assertEqual(json.loads(path.read_text()), first)

    def test_existing_account_is_not_reset(self):
        existing = User.objects.create_user(username="reviewer-client-a", email="personal@example.test", role="operator", is_active=False)
        original_hash = existing.password
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory), DEBUG=True):
            call_command("seed_reviewers", stdout=StringIO())
            existing.refresh_from_db()
            self.assertEqual(existing.password, original_hash)
            self.assertEqual(existing.role, "operator")
            self.assertFalse(existing.is_active)
            self.assertEqual(existing.email, "personal@example.test")

    @override_settings(DEBUG=False)
    def test_production_settings_refuse_reviewer_seed(self):
        with self.assertRaises(CommandError):
            call_command("seed_reviewers", stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)
