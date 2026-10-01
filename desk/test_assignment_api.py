from datetime import date

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Assignment, DatasetRequest, Episode, RequestStatus, User


class AssignmentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_a = User.objects.create_user(username="a", email="a@example.com")
        cls.client_b = User.objects.create_user(username="b", email="b@example.com")
        cls.operator = User.objects.create_user(username="ops", email="ops@example.com", role="operator")
        cls.admin = User.objects.create_user(username="admin", email="admin@example.com", role="admin")
        cls.request_a = DatasetRequest.objects.create(
            client=cls.client_a, task_name="pick cup", episodes_requested=1,
            deadline=date(2026, 10, 3), status="in_progress",
        )
        cls.request_b = DatasetRequest.objects.create(
            client=cls.client_b, task_name="pick cup", episodes_requested=1,
            deadline=date(2026, 10, 3), status="in_progress",
        )
        cls.good = Episode.objects.create(
            episode_id="EP-GOOD", robot_id="arm-01", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=30, operator_name="Kevin", quality="good",
        )
        cls.usable = Episode.objects.create(
            episode_id="EP-USABLE", robot_id="arm-02", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=45, operator_name="Eric", quality="usable",
        )
        cls.bad = Episode.objects.create(
            episode_id="EP-BAD", robot_id="arm-03", task_name="pick cup",
            recorded_at=timezone.now(), duration_seconds=40, operator_name="Kevin", quality="bad",
        )
        cls.other_task = Episode.objects.create(
            episode_id="EP-OTHER", robot_id="arm-01", task_name="fold towel",
            recorded_at=timezone.now(), duration_seconds=60, operator_name="Kevin", quality="good",
        )
        for user in [cls.client_a, cls.client_b, cls.operator, cls.admin]:
            Token.objects.create(user=user)

    def authenticate_as(self, user):
        token = Token.objects.get(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def setUp(self):
        self.authenticate_as(self.operator)

    def assign(self, episode, request=None):
        if request is None:
            request = self.request_a
        return self.client.post(
            f"/api/requests/{request.pk}/assignments/", {"episode": episode.pk}, format="json",
        )

    def remove(self, assignment_id, request=None):
        if request is None:
            request = self.request_a
        return self.client.delete(f"/api/requests/{request.pk}/assignments/{assignment_id}/")

    def test_anonymous_cannot_access_episode_or_assignment_endpoints(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/episodes/").status_code, 401)
        self.assertEqual(self.client.get(f"/api/requests/{self.request_a.pk}/assignments/").status_code, 401)
        self.assertEqual(self.assign(self.good).status_code, 401)
        self.assertEqual(self.remove(999).status_code, 401)

    def test_clients_cannot_browse_inventory_or_modify_assignments(self):
        for user in [self.client_a, self.client_b]:
            self.authenticate_as(user)
            self.assertEqual(self.client.get("/api/episodes/").status_code, 403)
            self.assertEqual(self.assign(self.good).status_code, 403)
            self.assertEqual(self.remove(999).status_code, 403)
        self.assertEqual(Assignment.objects.count(), 0)

    def test_inventory_filters_task_quality_and_availability(self):
        self.assign(self.good)
        response = self.client.get("/api/episodes/", {
            "task_name": "  Pick   Cup ", "quality": " GOOD ", "available": "true",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        response = self.client.get("/api/episodes/", {"task_name": "pick cup", "quality": "good"})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get("/api/episodes/", {"available": "false"})
        self.assertEqual(response.data["results"][0]["id"], self.good.pk)
        self.assertEqual(response.data["count"], 1)
        response = self.client.get("/api/episodes/", {"available": "true"})
        self.assertEqual(response.data["count"], 3)

    def test_invalid_inventory_filters_return_errors(self):
        for params in [{"quality": "excellent"}, {"available": "sometimes"}]:
            self.assertEqual(self.client.get("/api/episodes/", params).status_code, 400)

    def test_operator_and_admin_can_assign_eligible_episodes(self):
        for user, episode in [(self.operator, self.good), (self.admin, self.usable)]:
            self.authenticate_as(user)
            response = self.assign(episode)
            self.assertEqual(response.status_code, 201)
            assignment = Assignment.objects.get(pk=response.data["id"])
            self.assertEqual(assignment.assigned_by, user)
            self.assertEqual(assignment.request, self.request_a)
            self.assertEqual(response.data["episode_details"]["quality"], episode.quality)

    def test_bad_quality_and_wrong_task_are_rejected(self):
        for episode in [self.bad, self.other_task]:
            response = self.assign(episode)
            self.assertEqual(response.status_code, 400)
            self.assertIn("episode", response.data)
        self.assertEqual(Assignment.objects.count(), 0)

    def test_duplicate_assignment_is_rejected_for_same_and_other_request(self):
        self.assertEqual(self.assign(self.good).status_code, 201)
        self.assertEqual(self.assign(self.good).status_code, 400)
        self.assertEqual(self.assign(self.good, self.request_b).status_code, 400)
        self.assertEqual(Assignment.objects.filter(episode=self.good).count(), 1)

    def test_request_and_actor_are_chosen_by_server(self):
        response = self.client.post(f"/api/requests/{self.request_a.pk}/assignments/", {
            "episode": self.good.pk, "request": self.request_b.pk, "assigned_by": self.client_a.pk,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        assignment = Assignment.objects.get(pk=response.data["id"])
        self.assertEqual(assignment.request, self.request_a)
        self.assertEqual(assignment.assigned_by, self.operator)

    def test_clients_only_read_assignments_for_owned_request(self):
        self.assign(self.good)
        self.authenticate_as(self.client_a)
        response = self.client.get(f"/api/requests/{self.request_a.pk}/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["episode_details"]["task_name"], "pick cup")
        self.authenticate_as(self.client_b)
        self.assertEqual(self.client.get(f"/api/requests/{self.request_a.pk}/assignments/").status_code, 404)

    def test_assignments_only_change_in_progress(self):
        assignment_id = self.assign(self.good).data["id"]
        for current_status in RequestStatus.values:
            if current_status == "in_progress":
                continue
            with self.subTest(status=current_status):
                DatasetRequest.objects.filter(pk=self.request_a.pk).update(status=current_status)
                self.assertEqual(self.assign(self.usable).status_code, 400)
                self.assertEqual(self.remove(assignment_id).status_code, 400)
        self.assertEqual(Assignment.objects.count(), 1)

    def test_removal_releases_episode_for_another_request(self):
        response = self.assign(self.good)
        self.assertEqual(self.remove(response.data["id"]).status_code, 204)
        self.assertEqual(Assignment.objects.count(), 0)
        self.assertTrue(Episode.objects.filter(pk=self.good.pk).exists())
        self.assertEqual(self.assign(self.good, self.request_b).status_code, 201)

    def test_assignment_id_must_belong_to_url_request(self):
        assignment_id = self.assign(self.good).data["id"]
        self.assertEqual(self.remove(assignment_id, self.request_b).status_code, 404)
        self.assertTrue(Assignment.objects.filter(pk=assignment_id).exists())

    def test_missing_episode_and_request_return_errors(self):
        response = self.client.post(f"/api/requests/{self.request_a.pk}/assignments/", {"episode": 999999}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/requests/999999/assignments/", {"episode": self.good.pk}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.remove(999999).status_code, 404)

    def test_delivery_review_and_rework_use_assignment_endpoints(self):
        assignment_id = self.assign(self.good).data["id"]
        url = f"/api/requests/{self.request_a.pk}/status/"
        self.assertEqual(self.client.post(url, {"status": "delivered"}, format="json").status_code, 200)
        self.assertEqual(self.remove(assignment_id).status_code, 400)
        self.authenticate_as(self.client_a)
        self.assertEqual(self.client.post(url, {"status": "rejected"}, format="json").status_code, 200)
        self.authenticate_as(self.operator)
        self.assertEqual(self.client.post(url, {"status": "in_progress"}, format="json").status_code, 200)
        self.assertEqual(self.remove(assignment_id).status_code, 204)
        self.assertEqual(self.assign(self.usable).status_code, 201)
        self.assertEqual(self.client.post(url, {"status": "delivered"}, format="json").status_code, 200)
        self.authenticate_as(self.client_a)
        self.assertEqual(self.client.post(url, {"status": "accepted"}, format="json").status_code, 200)
