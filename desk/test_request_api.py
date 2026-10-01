from datetime import date
from unittest.mock import patch

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Assignment, DatasetRequest, Episode, RequestStatus, User


class RequestAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_a = User.objects.create_user(username="client-a", email="a@example.com")
        cls.client_b = User.objects.create_user(username="client-b", email="b@example.com")
        cls.operator = User.objects.create_user(username="ops", email="ops@example.com", role="operator")
        cls.admin = User.objects.create_user(username="admin", email="admin@example.com", role="admin")
        cls.request_a = DatasetRequest.objects.create(
            client=cls.client_a, task_name="pick cup", episodes_requested=1, deadline=date(2026, 10, 3),
        )
        cls.request_b = DatasetRequest.objects.create(
            client=cls.client_b, task_name="fold towel", episodes_requested=1, deadline=date(2026, 10, 3),
        )
        cls.episode = Episode.objects.create(
            episode_id="EP-001", robot_id="arm-01", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds="45.50", operator_name="Kevin", quality="good",
        )
        for user in [cls.client_a, cls.client_b, cls.operator, cls.admin]:
            Token.objects.create(user=user)

    def authenticate_as(self, user):
        token = Token.objects.get(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def request_input(self):
        return {"task_name": "Pick Cup", "episodes_requested": 3, "deadline": "2026-10-03"}

    def change_status(self, new_status, pk=None):
        if pk is None:
            pk = self.request_a.pk
        return self.client.post(f"/api/requests/{pk}/status/", {"status": new_status}, format="json")

    def assign_episode(self):
        Assignment.objects.create(request=self.request_a, episode=self.episode, assigned_by=self.operator)

    def test_anonymous_cannot_access_requests(self):
        pk = self.request_a.pk
        for url in ["/api/requests/", f"/api/requests/{pk}/", f"/api/requests/{pk}/history/"]:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post("/api/requests/", self.request_input(), format="json").status_code, 401)
        self.assertEqual(self.change_status("in_progress").status_code, 401)

    def test_creation_uses_authenticated_owner_and_records_submission(self):
        self.authenticate_as(self.client_a)
        data = self.request_input()
        data.update({"client": self.client_b.pk, "status": "accepted"})
        response = self.client.post("/api/requests/", data, format="json")
        self.assertEqual(response.status_code, 201)
        created = DatasetRequest.objects.get(pk=response.data["id"])
        self.assertEqual(created.client, self.client_a)
        self.assertEqual(created.status, "submitted")
        self.assertEqual(created.task_name, "pick cup")
        history = created.status_changes.get()
        self.assertEqual((history.from_status, history.to_status), ("", "submitted"))
        self.assertEqual(history.changed_by, self.client_a)
        self.assertIsNotNone(history.changed_at)

    def test_operators_and_admins_cannot_create_client_requests(self):
        for user in [self.operator, self.admin]:
            self.authenticate_as(user)
            self.assertEqual(self.client.post("/api/requests/", self.request_input(), format="json").status_code, 403)
        self.assertEqual(DatasetRequest.objects.count(), 2)

    def test_clients_only_see_own_requests(self):
        for user, own in [(self.client_a, self.request_a), (self.client_b, self.request_b)]:
            self.authenticate_as(user)
            response = self.client.get("/api/requests/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["id"], own.pk)
            self.assertEqual(self.client.get(f"/api/requests/{own.pk}/").status_code, 200)

    def test_other_clients_detail_history_and_status_are_inaccessible(self):
        self.authenticate_as(self.client_b)
        pk = self.request_a.pk
        self.assertEqual(self.client.get(f"/api/requests/{pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/requests/{pk}/history/").status_code, 404)
        self.assertEqual(self.change_status("accepted").status_code, 404)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, "submitted")
        self.assertEqual(self.request_a.status_changes.count(), 0)

    def test_operators_and_admins_see_all_requests(self):
        for user in [self.operator, self.admin]:
            self.authenticate_as(user)
            self.assertEqual(self.client.get("/api/requests/").data["count"], 2)
            self.assertEqual(self.client.get(f"/api/requests/{self.request_b.pk}/").status_code, 200)
            self.assertEqual(self.client.get(f"/api/requests/{self.request_b.pk}/history/").status_code, 200)

    def test_all_status_pairs_follow_role_and_transition_rules(self):
        self.assign_episode()
        client_steps = [("delivered", "accepted"), ("delivered", "rejected")]
        ops_steps = [("submitted", "in_progress"), ("in_progress", "delivered"), ("rejected", "in_progress")]
        for user in [self.client_a, self.operator, self.admin]:
            self.authenticate_as(user)
            allowed = client_steps if user.role == "client" else ops_steps
            for old in RequestStatus.values:
                for new in RequestStatus.values:
                    with self.subTest(role=user.role, old=old, new=new):
                        DatasetRequest.objects.filter(pk=self.request_a.pk).update(status=old, delivered_at=None)
                        before = self.request_a.status_changes.count()
                        response = self.change_status(new)
                        self.request_a.refresh_from_db()
                        if (old, new) in allowed:
                            self.assertEqual(response.status_code, 200)
                            self.assertEqual(self.request_a.status, new)
                            self.assertEqual(self.request_a.status_changes.count(), before + 1)
                            history = self.request_a.status_changes.latest("id")
                            self.assertEqual((history.from_status, history.to_status), (old, new))
                            self.assertEqual(history.changed_by, user)
                        else:
                            self.assertIn(response.status_code, [400, 403])
                            self.assertEqual(self.request_a.status, old)
                            self.assertEqual(self.request_a.status_changes.count(), before)

    def test_delivery_requires_requested_count(self):
        self.authenticate_as(self.operator)
        self.assertEqual(self.change_status("in_progress").status_code, 200)
        before = self.request_a.status_changes.count()
        self.assertEqual(self.change_status("delivered").status_code, 400)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, "in_progress")
        self.assertIsNone(self.request_a.delivered_at)
        self.assertEqual(self.request_a.status_changes.count(), before)
        self.assign_episode()
        self.assertEqual(self.change_status("delivered").status_code, 200)
        self.request_a.refresh_from_db()
        self.assertIsNotNone(self.request_a.delivered_at)

    def test_rework_keeps_first_delivery_time_and_ordered_history(self):
        self.assign_episode()
        self.authenticate_as(self.operator)
        self.assertEqual(self.change_status("in_progress").status_code, 200)
        self.assertEqual(self.change_status("delivered").status_code, 200)
        self.request_a.refresh_from_db()
        first_delivery = self.request_a.delivered_at
        self.authenticate_as(self.client_a)
        self.assertEqual(self.change_status("rejected").status_code, 200)
        self.authenticate_as(self.admin)
        self.assertEqual(self.change_status("in_progress").status_code, 200)
        self.assertEqual(self.change_status("delivered").status_code, 200)
        self.authenticate_as(self.client_a)
        self.assertEqual(self.change_status("accepted").status_code, 200)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.delivered_at, first_delivery)
        response = self.client.get(f"/api/requests/{self.request_a.pk}/history/")
        self.assertEqual([entry["to_status"] for entry in response.data], [
            "in_progress", "delivered", "rejected", "in_progress", "delivered", "accepted",
        ])

    def test_unknown_status_and_missing_request_return_errors(self):
        self.authenticate_as(self.operator)
        self.assertEqual(self.change_status("cancelled").status_code, 400)
        self.assertEqual(self.change_status("in_progress", pk=999999).status_code, 404)

    def test_initial_request_rolls_back_if_history_fails(self):
        self.authenticate_as(self.client_a)
        before = DatasetRequest.objects.count()
        with patch("desk.views.StatusChange.objects.create", side_effect=RuntimeError("history unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post("/api/requests/", self.request_input(), format="json")
        self.assertEqual(DatasetRequest.objects.count(), before)

    def test_status_update_rolls_back_if_history_fails(self):
        self.authenticate_as(self.operator)
        with patch("desk.views.StatusChange.objects.create", side_effect=RuntimeError("history unavailable")):
            with self.assertRaises(RuntimeError):
                self.change_status("in_progress")
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, "submitted")
        self.assertEqual(self.request_a.status_changes.count(), 0)

    def test_request_list_is_paginated(self):
        self.authenticate_as(self.client_a)
        DatasetRequest.objects.bulk_create([
            DatasetRequest(client=self.client_a, task_name="pick cup", episodes_requested=1, deadline=date(2026, 10, 3))
            for _ in range(51)
        ])
        response = self.client.get("/api/requests/")
        self.assertEqual(response.data["count"], 52)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(len(self.client.get("/api/requests/?page=2").data["results"]), 2)

    def test_delivery_accepts_more_than_requested_count(self):
        self.authenticate_as(self.operator)
        self.assign_episode()
        extra = Episode.objects.create(
            episode_id="EP-002", robot_id="arm-02", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=30, operator_name="Eric", quality="usable",
        )
        Assignment.objects.create(request=self.request_a, episode=extra, assigned_by=self.operator)
        self.assertEqual(self.change_status("in_progress").status_code, 200)
        self.assertEqual(self.change_status("delivered").status_code, 200)

    def test_delivery_rejects_positive_but_insufficient_count(self):
        self.authenticate_as(self.operator)
        DatasetRequest.objects.filter(pk=self.request_a.pk).update(episodes_requested=2)
        self.assign_episode()
        self.assertEqual(self.change_status("in_progress").status_code, 200)
        self.assertEqual(self.change_status("delivered").status_code, 400)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.status, "in_progress")
