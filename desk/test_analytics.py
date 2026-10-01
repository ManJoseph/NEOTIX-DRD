from datetime import date, datetime, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .analytics import build_analytics
from .models import DatasetRequest, Episode, User


class AnalyticsAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(username="ops", email="ops@example.com", role="operator")
        cls.admin = User.objects.create_user(username="admin", email="admin@example.com", role="admin")
        cls.client_user = User.objects.create_user(username="client", email="client@example.com")
        for user in [cls.operator, cls.admin, cls.client_user]:
            Token.objects.create(user=user)

    def setUp(self):
        self.authenticate_as(self.operator)
        self.params = {"start_date": "2026-10-01", "end_date": "2026-10-01"}

    def authenticate_as(self, user):
        token = Token.objects.get(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def add_episode(self, episode_id, recorded_at="2026-10-01T10:00:00+02:00", robot="arm-01", task="pick cup", quality="good"):
        return Episode.objects.create(
            episode_id=episode_id, robot_id=robot, task_name=task,
            recorded_at=datetime.fromisoformat(recorded_at), duration_seconds=30,
            operator_name="Kevin", quality=quality,
        )

    def add_request(self, status="submitted", seconds=None, created_at="2026-10-01T10:00:00+02:00"):
        request = DatasetRequest.objects.create(
            client=self.client_user, task_name="pick cup", episodes_requested=1,
            deadline=date(2026, 10, 3), status=status,
        )
        submitted_at = datetime.fromisoformat(created_at)
        delivered_at = None if seconds is None else submitted_at + timedelta(seconds=seconds)
        # Override the automatic timestamp only to make test fixtures reproducible.
        DatasetRequest.objects.filter(pk=request.pk).update(created_at=submitted_at, delivered_at=delivered_at)
        return request

    def report(self):
        response = self.client.get("/api/analytics/", self.params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_operator_and_admin_access_but_client_and_anonymous_denied(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/analytics/", self.params).status_code, 401)
        self.authenticate_as(self.client_user)
        self.assertEqual(self.client.get("/api/analytics/", self.params).status_code, 403)
        self.authenticate_as(self.admin)
        self.assertEqual(self.client.get("/api/analytics/", self.params).status_code, 200)

    def test_empty_range_returns_zero_counts_and_null_median(self):
        report = self.report()
        self.assertEqual(report["episodes_per_day_per_robot"], [])
        self.assertEqual(report["top_good_tasks"], [])
        self.assertIsNone(report["request_fulfilment"]["median_delivery_seconds"])
        self.assertEqual(report["request_fulfilment"]["counts_by_status"], {
            "submitted": 0, "in_progress": 0, "delivered": 0, "accepted": 0, "rejected": 0,
        })

    def test_daily_robot_counts_respect_kigali_midnight_boundaries(self):
        self.add_episode("EP-BEFORE", "2026-09-30T21:59:59+00:00")
        self.add_episode("EP-START", "2026-09-30T22:00:00+00:00")
        self.add_episode("EP-LAST", "2026-10-01T21:59:59+00:00", quality="bad")
        self.add_episode("EP-AFTER", "2026-10-01T22:00:00+00:00")
        self.add_episode("EP-ROBOT2", robot="arm-02")
        self.assertEqual(self.report()["episodes_per_day_per_robot"], [
            {"day": "2026-10-01", "robot_id": "arm-01", "count": 2},
            {"day": "2026-10-01", "robot_id": "arm-02", "count": 1},
        ])

    def test_multi_day_counts_keep_days_separate(self):
        self.add_episode("EP-1")
        self.add_episode("EP-2", "2026-10-02T10:00:00+02:00")
        self.params["end_date"] = "2026-10-02"
        self.assertEqual([entry["day"] for entry in self.report()["episodes_per_day_per_robot"]], ["2026-10-01", "2026-10-02"])

    def test_request_status_counts_use_submission_date(self):
        for status in ["submitted", "in_progress", "delivered", "accepted", "rejected"]:
            self.add_request(status=status)
        self.add_request(created_at="2026-09-30T23:59:59+02:00")
        self.add_request(created_at="2026-10-02T00:00:00+02:00")
        self.assertEqual(self.report()["request_fulfilment"]["counts_by_status"], {
            "submitted": 1, "in_progress": 1, "delivered": 1, "accepted": 1, "rejected": 1,
        })

    def test_odd_median_is_middle_value_and_ignores_never_delivered_requests(self):
        for seconds in [10, 20, 100]:
            self.add_request(status="delivered", seconds=seconds)
        self.add_request()
        self.add_request(status="delivered", seconds=99999, created_at="2026-09-30T10:00:00+02:00")
        self.assertEqual(self.report()["request_fulfilment"]["median_delivery_seconds"], 20.0)

    def test_even_median_averages_middle_two_values(self):
        for seconds in [10, 20, 100, 200]:
            self.add_request(status="accepted", seconds=seconds)
        self.assertEqual(self.report()["request_fulfilment"]["median_delivery_seconds"], 60.0)

    def test_first_deliveries_outside_range_and_reworked_requests_are_included(self):
        self.add_request(status="rejected", seconds=86400)
        self.add_request(status="in_progress", seconds=172800)
        self.assertEqual(self.report()["request_fulfilment"]["median_delivery_seconds"], 129600.0)

    def test_top_five_tasks_only_count_good_episodes(self):
        for task, count in [("task-a", 7), ("task-b", 6), ("task-c", 5), ("task-d", 4), ("task-e", 3), ("task-f", 2)]:
            for number in range(count):
                self.add_episode(f"{task}-{number}", task=task)
        for number in range(10):
            self.add_episode(f"BAD-{number}", task="task-f", quality="bad")
            self.add_episode(f"USABLE-{number}", task="task-f", quality="usable")
        self.add_episode("OUTSIDE", task="task-f", recorded_at="2026-09-01T10:00:00+02:00")
        self.assertEqual(self.report()["top_good_tasks"], [
            {"task_name": "task-a", "count": 7}, {"task_name": "task-b", "count": 6},
            {"task_name": "task-c", "count": 5}, {"task_name": "task-d", "count": 4},
            {"task_name": "task-e", "count": 3},
        ])

    def test_invalid_missing_and_reversed_dates_return_validation_errors(self):
        for params in [{}, {"start_date": "invalid", "end_date": "2026-10-01"},
                       {"start_date": "2026-10-02", "end_date": "2026-10-01"},
                       {"start_date": "2026-10-01", "end_date": "9999-12-31"}]:
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/analytics/", params).status_code, 400)

    def test_report_uses_four_database_aggregate_queries(self):
        with CaptureQueriesContext(connection) as queries:
            build_analytics(date(2026, 10, 1), date(2026, 10, 1))
        self.assertEqual(len(queries), 4)
        sql = " ".join(query["sql"].lower() for query in queries)
        self.assertIn("percentile_cont", sql)
        self.assertIn("group by", sql)
        self.assertIn("limit 5", sql)
