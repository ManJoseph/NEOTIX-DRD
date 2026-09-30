from unittest.mock import patch

from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import User
from .throttles import LoginThrottle


class AuthenticationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "A-long-test-password!42"
        cls.admin = User.objects.create_user(
            username="admin@example.com", email="admin@example.com",
            name="Admin", role="admin", password=cls.password,
        )
        cls.client_user = User.objects.create_user(
            username="client@example.com", email="client@example.com",
            name="Client", password=cls.password,
        )
        cls.operator = User.objects.create_user(
            username="ops@example.com", email="ops@example.com",
            name="Operator", role="operator", password=cls.password,
        )

    def setUp(self):
        cache.clear()

    def authenticate_as(self, user):
        token, created = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token

    def test_login_returns_token_and_safe_user_details(self):
        response = self.client.post("/api/auth/login/", {
            "username": self.client_user.username, "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["id"], self.client_user.pk)
        self.assertNotIn("password", response.data["user"])
        self.assertTrue(Token.objects.filter(key=response.data["token"], user=self.client_user).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.client_user.pk)

    def test_wrong_password_and_inactive_account_cannot_login(self):
        response = self.client.post("/api/auth/login/", {
            "username": self.client_user.username, "password": "incorrect-password",
        }, format="json")
        self.assertEqual(response.status_code, 401)
        self.client_user.is_active = False
        self.client_user.save()
        response = self.client.post("/api/auth/login/", {
            "username": self.client_user.username, "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Token.objects.filter(user=self.client_user).exists())

    def test_login_reuses_existing_token(self):
        existing = Token.objects.create(user=self.client_user)
        response = self.client.post("/api/auth/login/", {
            "username": self.client_user.username, "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], existing.key)
        self.assertEqual(Token.objects.filter(user=self.client_user).count(), 1)

    def test_missing_login_fields_return_validation_error(self):
        response = self.client.post("/api/auth/login/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("password", response.data)

    def test_anonymous_and_invalid_tokens_cannot_access_protected_routes(self):
        for url in ["/api/auth/me/", "/api/users/", f"/api/users/{self.client_user.pk}/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid-token")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 401)

    def test_logout_revokes_token(self):
        token = self.authenticate_as(self.client_user)
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_clients_and_operators_cannot_manage_users(self):
        for user in [self.client_user, self.operator]:
            with self.subTest(role=user.role):
                self.authenticate_as(user)
                self.assertEqual(self.client.get("/api/users/").status_code, 403)
                self.assertEqual(self.client.post("/api/users/", {}, format="json").status_code, 403)
                url = f"/api/users/{self.client_user.pk}/"
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.patch(url, {"role": "admin"}, format="json").status_code, 403)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, "client")

    def test_admin_can_create_and_list_users_without_password_exposure(self):
        self.authenticate_as(self.admin)
        response = self.client.post("/api/users/", {
            "username": "new@example.com", "email": "new@example.com",
            "name": "New Operator", "role": "operator", "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        user = User.objects.get(pk=response.data["id"])
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.role, "operator")
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        for account in response.data:
            self.assertNotIn("password", account)

    def test_admin_can_change_role_and_deactivate_user(self):
        self.authenticate_as(self.admin)
        token = Token.objects.create(user=self.client_user)
        url = f"/api/users/{self.client_user.pk}/"
        response = self.client.patch(url, {"role": "operator"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "operator")
        response = self.client.patch(url, {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_admin_cannot_deactivate_or_demote_self(self):
        self.authenticate_as(self.admin)
        url = f"/api/users/{self.admin.pk}/"
        for data in [{"role": "client"}, {"is_active": False}]:
            with self.subTest(data=data):
                response = self.client.patch(url, data, format="json")
                self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")
        self.assertTrue(self.admin.is_active)

    def test_duplicate_account_and_invalid_role_return_readable_errors(self):
        self.authenticate_as(self.admin)
        response = self.client.post("/api/users/", {
            "username": self.client_user.username, "email": self.client_user.email,
            "name": "Duplicate", "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        response = self.client.patch(
            f"/api/users/{self.client_user.pk}/", {"role": "owner"}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_login_attempts_are_throttled(self):
        # Lower the limit for this test so we do not need 21 login attempts.
        with patch.object(LoginThrottle, "rate", "1/min"):
            data = {"username": self.client_user.username, "password": "incorrect-password"}
            self.assertEqual(self.client.post("/api/auth/login/", data, format="json").status_code, 401)
            self.assertEqual(self.client.post("/api/auth/login/", data, format="json").status_code, 429)
