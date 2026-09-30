from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinValueValidator
from django.db import models


class UserRole(models.TextChoices):
    CLIENT = "client", "Client"
    OPERATOR = "operator", "Operator"
    ADMIN = "admin", "Admin"


class EpisodeQuality(models.TextChoices):
    GOOD = "good", "Good"
    USABLE = "usable", "Usable"
    BAD = "bad", "Bad"


class RequestStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    IN_PROGRESS = "in_progress", "In progress"
    DELIVERED = "delivered", "Delivered"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


ROBOT_CHOICES = [
    ("arm-01", "arm-01"),
    ("arm-02", "arm-02"),
    ("arm-03", "arm-03"),
    ("mobile-01", "mobile-01"),
    ("humanoid-01", "humanoid-01"),
]


class DeskUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # The management command must also set our application's admin role.
        extra_fields["role"] = UserRole.ADMIN
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    organisation = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=10, choices=UserRole.choices, default=UserRole.CLIENT
    )

    objects = DeskUserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=UserRole.values),
                name="user_valid_role",
            ),
        ]

    def __str__(self):
        return self.email


class Episode(models.Model):
    episode_id = models.CharField(max_length=50, unique=True)
    robot_id = models.CharField(max_length=20, choices=ROBOT_CHOICES)
    task_name = models.CharField(max_length=200)
    recorded_at = models.DateTimeField()
    duration_seconds = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    operator_name = models.CharField(max_length=150)
    quality = models.CharField(max_length=10, choices=EpisodeQuality.choices)

    class Meta:
        indexes = [
            models.Index(fields=["recorded_at", "robot_id"], name="episode_recorded_robot_idx"),
            models.Index(fields=["task_name", "quality"], name="episode_task_quality_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_seconds__gt=0),
                name="episode_positive_duration",
            ),
            models.CheckConstraint(
                condition=models.Q(quality__in=EpisodeQuality.values),
                name="episode_valid_quality",
            ),
            models.CheckConstraint(
                condition=models.Q(robot_id__in=[robot[0] for robot in ROBOT_CHOICES]),
                name="episode_known_robot",
            ),
        ]

    def __str__(self):
        return self.episode_id


class DatasetRequest(models.Model):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dataset_requests"
    )
    task_name = models.CharField(max_length=200)
    episodes_requested = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    deadline = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=RequestStatus.choices, default=RequestStatus.SUBMITTED
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    # First delivery time is retained even if the client requests rework.
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(episodes_requested__gte=1),
                name="request_positive_count",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=RequestStatus.values),
                name="request_valid_status",
            ),
        ]

    def __str__(self):
        return f"Request {self.pk}: {self.task_name}"


class Assignment(models.Model):
    request = models.ForeignKey(
        DatasetRequest, on_delete=models.PROTECT, related_name="assignments"
    )
    # The unique episode link prevents two requests from claiming the same episode.
    episode = models.OneToOneField(
        Episode, on_delete=models.PROTECT, related_name="assignment"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="episode_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)


class StatusChange(models.Model):
    request = models.ForeignKey(
        DatasetRequest, on_delete=models.PROTECT, related_name="status_changes"
    )
    # Empty previous status represents the initial submission event.
    from_status = models.CharField(max_length=20, choices=RequestStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=RequestStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="request_status_changes"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
