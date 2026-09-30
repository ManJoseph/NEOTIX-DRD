from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Assignment, Episode, User
from .serializers import (
    AssignmentSerializer,
    DatasetRequestSerializer,
    RequestStatusSerializer,
    UserSerializer,
)


class SerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            username="client@example.com", email="client@example.com", name="Test Client",
        )
        cls.operator = User.objects.create_user(
            username="ops@example.com", email="ops@example.com", role="operator",
        )
        cls.episode = Episode.objects.create(
            episode_id="EP-001", robot_id="arm-01", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=Decimal("45.50"),
            operator_name="Kevin", quality="good",
        )

    def request_input(self):
        return {
            "task_name": "  Pick   Cup ",
            "episodes_requested": 2,
            "deadline": "2026-10-03",
            "notes": "For robot training",
        }

    def test_client_cannot_choose_owner_status_or_delivery_time(self):
        data = self.request_input()
        data.update({
            "client": self.operator.pk,
            "status": "accepted",
            "delivered_at": "2026-10-01T10:00:00Z",
        })
        serializer = DatasetRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        for field in ["client", "status", "delivered_at"]:
            self.assertNotIn(field, serializer.validated_data)
        request = serializer.save(client=self.client_user)
        self.assertEqual(request.client, self.client_user)
        self.assertEqual(request.status, "submitted")
        self.assertIsNone(request.delivered_at)
        self.assertEqual(request.task_name, "pick cup")
        self.assertEqual(request.deadline, date(2026, 10, 3))

    def test_invalid_request_input_returns_field_errors(self):
        for field, value in [
            ("episodes_requested", 0),
            ("episodes_requested", -1),
            ("episodes_requested", 1.5),
            ("task_name", "   "),
            ("deadline", "not a date"),
        ]:
            with self.subTest(field=field, value=value):
                data = self.request_input()
                data[field] = value
                serializer = DatasetRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_password_and_superuser_flag_are_not_in_user_output(self):
        data = UserSerializer(self.client_user).data
        self.assertNotIn("password", data)
        self.assertNotIn("is_superuser", data)
        self.assertEqual(data["role"], "client")

    def test_bad_quality_episode_cannot_be_assigned(self):
        self.episode.quality = "bad"
        self.episode.save()
        serializer = AssignmentSerializer(data={"episode": self.episode.pk})
        self.assertFalse(serializer.is_valid())
        self.assertIn("episode", serializer.errors)

    def test_already_assigned_episode_returns_validation_error(self):
        serializer = DatasetRequestSerializer(data=self.request_input())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        request = serializer.save(client=self.client_user)
        Assignment.objects.create(
            request=request, episode=self.episode, assigned_by=self.operator,
        )
        serializer = AssignmentSerializer(data={"episode": self.episode.pk})
        self.assertFalse(serializer.is_valid())
        self.assertIn("episode", serializer.errors)

    def test_good_and_usable_episodes_are_eligible(self):
        for quality in ["good", "usable"]:
            with self.subTest(quality=quality):
                self.episode.quality = quality
                self.episode.save()
                serializer = AssignmentSerializer(data={
                    "episode": self.episode.pk,
                    "request": 9999,
                    "assigned_by": self.client_user.pk,
                })
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data["episode"], self.episode)
                self.assertNotIn("request", serializer.validated_data)
                self.assertNotIn("assigned_by", serializer.validated_data)

    def test_nonexistent_episode_returns_validation_error(self):
        serializer = AssignmentSerializer(data={"episode": self.episode.pk + 100})
        self.assertFalse(serializer.is_valid())
        self.assertIn("episode", serializer.errors)

    def test_status_input_rejects_unknown_name(self):
        serializer = RequestStatusSerializer(data={"status": "cancelled"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

class AccountSerializerTests(TestCase):
    def account_input(self):
        return {
            "username": "new-client@example.com",
            "email": "new-client@example.com",
            "name": "New Client",
            "organisation": "Example Robotics",
            "password": "A-long-test-password!42",
        }

    def test_creation_hashes_password_and_excludes_it_from_output(self):
        from .serializers import UserCreateSerializer

        data = self.account_input()
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertTrue(user.check_password(data["password"]))
        self.assertNotEqual(user.password, data["password"])
        self.assertEqual(user.role, "client")
        self.assertNotIn("password", serializer.data)

    def test_weak_password_returns_validation_error(self):
        from .serializers import UserCreateSerializer

        data = self.account_input()
        data["password"] = "123"
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_duplicate_username_and_email_return_validation_errors(self):
        from .serializers import UserCreateSerializer

        data = self.account_input()
        User.objects.create_user(
            username=data["username"], email=data["email"], name=data["name"],
        )
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)
        self.assertIn("email", serializer.errors)

    def test_creation_cannot_set_django_superuser_flags(self):
        from .serializers import UserCreateSerializer

        data = self.account_input()
        data.update({"is_superuser": True, "is_staff": True, "role": "operator"})
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.role, "operator")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_update_changes_role_and_active_state_only(self):
        from .serializers import UserUpdateSerializer

        user = User.objects.create_user(
            username="existing", email="existing@example.com", name="Existing User",
        )
        serializer = UserUpdateSerializer(user, data={
            "role": "operator", "is_active": False,
            "username": "changed", "is_superuser": True,
        }, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.role, "operator")
        self.assertFalse(user.is_active)
        self.assertEqual(user.username, "existing")
        self.assertFalse(user.is_superuser)

    def test_update_rejects_unknown_role(self):
        from .serializers import UserUpdateSerializer

        serializer = UserUpdateSerializer(data={"role": "owner"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("role", serializer.errors)
