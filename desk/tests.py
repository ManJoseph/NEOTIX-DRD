from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import Assignment, DatasetRequest, Episode, User, UserRole


class ModelTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client@example.com", email="client@example.com",
            password="test-password", name="Test Client",
        )
        self.operator = User.objects.create_user(
            username="ops@example.com", email="ops@example.com",
            password="test-password", role=UserRole.OPERATOR,
        )
        self.request = DatasetRequest.objects.create(
            client=self.client_user, task_name="pick cup",
            episodes_requested=2, deadline=date(2026, 10, 3),
        )
        self.episode = Episode.objects.create(
            episode_id="EP-001", robot_id="arm-01", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=Decimal("45.50"),
            operator_name="Kevin", quality="good",
        )

    def test_password_is_hashed_and_new_user_is_client(self):
        self.assertNotEqual(self.client_user.password, "test-password")
        self.assertTrue(self.client_user.check_password("test-password"))
        self.assertEqual(self.client_user.role, "client")

    def test_superuser_has_business_admin_role(self):
        admin = User.objects.create_superuser(
            username="admin@example.com", email="admin@example.com",
            password="test-password",
        )
        self.assertEqual(admin.role, "admin")
        self.assertTrue(admin.is_superuser)

    def test_episode_cannot_be_assigned_to_two_requests(self):
        Assignment.objects.create(
            request=self.request, episode=self.episode, assigned_by=self.operator,
        )
        other_request = DatasetRequest.objects.create(
            client=self.client_user, task_name="pick cup",
            episodes_requested=1, deadline=date(2026, 10, 3),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Assignment.objects.create(
                    request=other_request, episode=self.episode, assigned_by=self.operator,
                )

    def test_episode_id_cannot_be_duplicated(self):
        self.episode.pk = None
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.episode.save()

    def test_request_count_cannot_be_zero(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DatasetRequest.objects.filter(pk=self.request.pk).update(episodes_requested=0)

    def test_invalid_episode_data_is_rejected_by_database(self):
        for fields in [
            {"quality": "excellent"},
            {"robot_id": "arm-99"},
            {"duration_seconds": 0},
            {"duration_seconds": -5},
        ]:
            with self.subTest(fields=fields):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Episode.objects.filter(pk=self.episode.pk).update(**fields)

    def test_invalid_status_and_role_are_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DatasetRequest.objects.filter(pk=self.request.pk).update(status="cancelled")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(pk=self.client_user.pk).update(role="owner")

    def test_client_with_request_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.client_user.delete()
