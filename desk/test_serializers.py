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
