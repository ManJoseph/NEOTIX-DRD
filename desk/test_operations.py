import json
from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError
from django.test import RequestFactory, SimpleTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .middleware import RequestLoggingMiddleware
from .models import User


class OperationsAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "A-long-test-password!42"
        cls.user = User.objects.create_user(
            username="client", email="client@example.com", password=cls.password,
        )
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self):
        cache.clear()

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_health_requires_authentication(self):
        self.assertEqual(self.client.get("/health").status_code, 401)

    def test_health_checks_database_and_returns_ok(self):
        self.authenticate()
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_database_check_failure_returns_safe_503(self):
        self.client.force_authenticate(user=self.user)
        with patch("desk.views.connection.cursor", side_effect=OperationalError("private database details")):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Database unavailable. Try again later."})
        self.assertNotIn("private", response.content.decode())

    def test_database_failure_during_token_authentication_returns_503(self):
        self.authenticate()
        with patch("rest_framework.authentication.TokenAuthentication.authenticate_credentials", side_effect=OperationalError("private database details")):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", response.content.decode())

    def test_authenticated_request_has_one_structured_access_log(self):
        self.authenticate()
        with self.assertLogs("desk.requests", level="INFO") as logs:
            response = self.client.get("/api/auth/me/?password=do-not-log")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(logs.records), 1)
        entry = json.loads(logs.records[0].getMessage())
        self.assertEqual(entry["method"], "GET")
        self.assertEqual(entry["path"], "/api/auth/me/")
        self.assertEqual(entry["status"], 200)
        self.assertEqual(entry["user_id"], self.user.pk)
        self.assertGreaterEqual(entry["duration_ms"], 0)
        self.assertIn("timestamp", entry)
        self.assertNotIn(self.token.key, logs.records[0].getMessage())
        self.assertNotIn("do-not-log", logs.records[0].getMessage())

    def test_anonymous_and_not_found_requests_are_logged(self):
        for url, expected in [("/api/auth/me/", 401), ("/missing-route/", 404)]:
            with self.subTest(url=url):
                with self.assertLogs("desk.requests", level="INFO") as logs:
                    self.client.get(url)
                self.assertEqual(len(logs.records), 1)
                entry = json.loads(logs.records[0].getMessage())
                self.assertEqual(entry["status"], expected)
                self.assertIsNone(entry["user_id"])

    def test_denied_action_logs_authenticated_user_id(self):
        self.authenticate()
        with self.assertLogs("desk.requests", level="INFO") as logs:
            self.client.get("/api/users/")
        entry = json.loads(logs.records[0].getMessage())
        self.assertEqual(entry["status"], 403)
        self.assertEqual(entry["user_id"], self.user.pk)

    def test_successful_login_logs_user_id_without_password_or_token(self):
        with self.assertLogs("desk.requests", level="INFO") as logs:
            response = self.client.post("/api/auth/login/", {
                "username": self.user.username, "password": self.password,
            }, format="json")
        self.assertEqual(response.status_code, 200)
        entry = json.loads(logs.records[0].getMessage())
        self.assertEqual(entry["user_id"], self.user.pk)
        self.assertNotIn(self.password, logs.records[0].getMessage())
        self.assertNotIn(response.data["token"], logs.records[0].getMessage())


class LoggingMiddlewareTests(SimpleTestCase):
    def test_unhandled_failure_still_produces_one_500_access_log(self):
        def broken_response(request):
            raise RuntimeError("simulated failure")

        middleware = RequestLoggingMiddleware(broken_response)
        request = RequestFactory().get("/broken/")
        with self.assertLogs("desk.requests", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                middleware(request)
        self.assertEqual(len(logs.records), 1)
        entry = json.loads(logs.records[0].getMessage())
        self.assertEqual(entry["status"], 500)
        self.assertIsNone(entry["user_id"])
