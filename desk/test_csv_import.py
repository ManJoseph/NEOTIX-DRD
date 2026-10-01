import csv
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .csv_import import CSV_COLUMNS, import_episodes
from .models import Episode, User


class CSVImportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(username="ops", email="ops@example.com", role="operator")
        cls.admin = User.objects.create_user(username="admin", email="admin@example.com", role="admin")
        cls.client_user = User.objects.create_user(username="client", email="client@example.com")
        for user in [cls.operator, cls.admin, cls.client_user]:
            Token.objects.create(user=user)

    def setUp(self):
        self.authenticate_as(self.operator)

    def authenticate_as(self, user):
        token = Token.objects.get(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def valid_row(self, episode_id="EP-001"):
        return [episode_id, "arm-01", "pick cup", "2026-08-14T09:15:00", "45.5", "Kevin", "good"]

    def csv_text(self, rows):
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
        return stream.getvalue()

    def upload(self, text):
        file = SimpleUploadedFile("episodes.csv", text.encode("utf-8"), content_type="text/csv")
        return self.client.post("/api/episodes/import/", {"file": file}, format="multipart")

    def test_only_operators_and_admins_can_import(self):
        self.client.credentials()
        self.assertEqual(self.upload(self.csv_text([self.valid_row()])).status_code, 401)
        self.authenticate_as(self.client_user)
        self.assertEqual(self.upload(self.csv_text([self.valid_row()])).status_code, 403)
        self.assertEqual(Episode.objects.count(), 0)
        for user, episode_id in [(self.operator, "EP-OPS"), (self.admin, "EP-ADMIN")]:
            self.authenticate_as(user)
            response = self.upload(self.csv_text([self.valid_row(episode_id)]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["imported"], 1)

    def test_same_file_can_be_imported_twice_without_duplicates(self):
        text = self.csv_text([self.valid_row(), self.valid_row("EP-002")])
        first = self.upload(text)
        second = self.upload(text)
        self.assertEqual(first.data["imported"], 2)
        self.assertEqual(second.data["imported"], 0)
        self.assertEqual(second.data["skipped"], 2)
        self.assertEqual(Episode.objects.count(), 2)

    def test_normalizes_case_whitespace_and_decimal_duration(self):
        row = [" ep-001 ", " ARM-01 ", "  Pick   Cup ", "2026-08-14 09:15:00", "45.5", " Kevin ", " Good "]
        report = import_episodes(self.csv_text([row]))
        self.assertEqual(report["imported"], 1)
        episode = Episode.objects.get()
        self.assertEqual(episode.episode_id, "EP-001")
        self.assertEqual(episode.robot_id, "arm-01")
        self.assertEqual(episode.task_name, "pick cup")
        self.assertEqual(episode.quality, "good")
        self.assertEqual(str(episode.duration_seconds), "45.50")
        self.assertEqual(episode.operator_name, "Kevin")
        self.assertEqual(timezone.localtime(episode.recorded_at).hour, 9)

    def test_mixed_dates_and_quoted_comma_task_are_supported(self):
        rows = []
        for number, date_value in enumerate(["2026-08-14T09:15:00", "2026-08-14 09:15:00", "14/08/2026 09:15", "2026-08-14T09:15:00Z"]):
            row = self.valid_row(f"EP-{number}")
            row[3] = date_value
            row[2] = "pick cup, then place"
            rows.append(row)
        report = import_episodes(self.csv_text(rows))
        self.assertEqual(report["imported"], 4)
        self.assertEqual(Episode.objects.filter(task_name="pick cup, then place").count(), 4)
        self.assertEqual(Episode.objects.get(episode_id="EP-3").recorded_at.hour, 9)

    def test_identical_and_conflicting_duplicates_keep_first_record(self):
        first = self.valid_row()
        conflict = self.valid_row("ep-001")
        conflict[6] = "bad"
        report = import_episodes(self.csv_text([first, first, conflict]))
        self.assertEqual((report["imported"], report["skipped"]), (1, 2))
        self.assertIn("Duplicate", report["skipped_rows"][0]["reason"])
        self.assertIn("Conflicting", report["skipped_rows"][1]["reason"])
        self.assertEqual(Episode.objects.get().quality, "good")

    def test_invalid_rows_report_reasons_without_blocking_valid_rows(self):
        rows = [self.valid_row()]
        bad_values = [(0, ""), (1, "arm-99"), (2, ""), (3, "not a date"),
                      (4, ""), (4, "-5"), (4, "NaN"), (4, "Infinity"),
                      (4, "N/A"), (4, "999999"), (4, "0.001"), (5, ""), (6, "excellent")]
        for number, (column, value) in enumerate(bad_values):
            row = self.valid_row(f"EP-INVALID-{number}")
            row[column] = value
            rows.append(row)
        future = self.valid_row("EP-FUTURE")
        future[3] = (timezone.now() + timedelta(days=1)).isoformat()
        rows.extend([future, ["too", "few"], [], ["   "]])
        report = import_episodes(self.csv_text(rows))
        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["skipped"], len(rows) - 1)
        self.assertEqual(len(report["skipped_rows"]), len(rows) - 1)
        self.assertTrue(all(entry["reason"] for entry in report["skipped_rows"]))
        self.assertEqual(report["skipped_rows"][0]["row"], 3)

    def test_invalid_first_occurrence_does_not_reserve_episode_id(self):
        invalid = self.valid_row()
        invalid[6] = "excellent"
        report = import_episodes(self.csv_text([invalid, self.valid_row()]))
        self.assertEqual((report["imported"], report["skipped"]), (1, 1))

    def test_exact_minimum_duration_is_valid(self):
        row = self.valid_row()
        row[4] = "0.01"
        self.assertEqual(import_episodes(self.csv_text([row]))["imported"], 1)

    def test_bad_quality_is_imported_but_not_upgraded_by_duplicate(self):
        first = self.valid_row()
        first[6] = "bad"
        report = import_episodes(self.csv_text([first, self.valid_row()]))
        self.assertEqual(report["imported"], 1)
        self.assertEqual(Episode.objects.get().quality, "bad")
        self.assertIn("Conflicting", report["skipped_rows"][0]["reason"])

    def test_empty_wrong_header_and_broken_csv_have_no_writes(self):
        valid = self.csv_text([self.valid_row()])
        for text in ["", "wrong,header\na,b", valid + '"unclosed quote']:
            with self.subTest(text=text):
                response = self.upload(text)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Episode.objects.count(), 0)

    def test_missing_file_encoding_and_upload_limit_return_errors(self):
        self.assertEqual(self.client.post("/api/episodes/import/", {}, format="multipart").status_code, 400)
        for payload in [b"\xff\xfe", b"x" * (5 * 1024 * 1024 + 1)]:
            file = SimpleUploadedFile("episodes.csv", payload, content_type="text/csv")
            response = self.client.post("/api/episodes/import/", {"file": file}, format="multipart")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Episode.objects.count(), 0)

    def test_candidate_pack_import_counts_and_repeatability(self):
        text = (Path(settings.BASE_DIR) / "seed" / "episodes.csv").read_text(encoding="utf-8-sig")
        # Fix the clock so the known future-date row remains invalid in later test runs.
        fixed_now = datetime(2026, 10, 1, tzinfo=datetime_timezone.utc)
        with patch("desk.csv_import.timezone.now", return_value=fixed_now):
            first = import_episodes(text)
            second = import_episodes(text)
        self.assertEqual((first["imported"], first["skipped"]), (172, 19))
        self.assertEqual((second["imported"], second["skipped"]), (0, 191))
        self.assertEqual(Episode.objects.count(), 172)

    def test_unexpected_database_failure_rolls_back_import(self):
        original = Episode.objects.get_or_create

        def fail_second_row(**kwargs):
            if kwargs["episode_id"] == "EP-002":
                raise IntegrityError("simulated database failure")
            return original(**kwargs)

        with patch("desk.csv_import.Episode.objects.get_or_create", side_effect=fail_second_row):
            with self.assertRaises(IntegrityError):
                import_episodes(self.csv_text([self.valid_row(), self.valid_row("EP-002")]))
        self.assertEqual(Episode.objects.count(), 0)

    def test_record_limit_is_checked_before_database_writes(self):
        text = self.csv_text([self.valid_row()] * 10001)
        response = self.upload(text)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Episode.objects.count(), 0)
