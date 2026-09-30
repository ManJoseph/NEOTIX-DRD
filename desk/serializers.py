from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from .models import (
    Assignment,
    DatasetRequest,
    Episode,
    EpisodeQuality,
    RequestStatus,
    StatusChange,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    # Account output only. Passwords and Django permission flags are excluded.
    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "organisation", "role", "is_active"]
        read_only_fields = fields


class EpisodeSerializer(serializers.ModelSerializer):
    # Episodes will be created by the CSV importer, not this serializer.
    class Meta:
        model = Episode
        fields = [
            "id", "episode_id", "robot_id", "task_name", "recorded_at",
            "duration_seconds", "operator_name", "quality",
        ]
        read_only_fields = fields


class DatasetRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetRequest
        fields = [
            "id", "client", "task_name", "episodes_requested", "deadline",
            "notes", "status", "created_at", "updated_at", "delivered_at",
        ]
        # The view will choose the owner and manage the workflow fields.
        read_only_fields = [
            "id", "client", "status", "created_at", "updated_at", "delivered_at",
        ]

    def validate_task_name(self, value):
        # Treat "  Pick   Cup " and "pick cup" as the same task.
        return " ".join(value.split()).lower()


class AssignmentSerializer(serializers.ModelSerializer):
    # An operator submits the episode's internal numeric id.
    episode = serializers.PrimaryKeyRelatedField(queryset=Episode.objects.all())
    episode_id = serializers.CharField(source="episode.episode_id", read_only=True)

    class Meta:
        model = Assignment
        fields = ["id", "request", "episode", "episode_id", "assigned_by", "assigned_at"]
        read_only_fields = ["id", "request", "assigned_by", "assigned_at"]

    def validate_episode(self, episode):
        if episode.quality not in [EpisodeQuality.GOOD, EpisodeQuality.USABLE]:
            raise serializers.ValidationError("Only good or usable episodes can be assigned.")
        if Assignment.objects.filter(episode=episode).exists():
            raise serializers.ValidationError("This episode is already assigned to a request.")
        return episode


class StatusChangeSerializer(serializers.ModelSerializer):
    # History is written by the workflow endpoint, not submitted by clients.
    class Meta:
        model = StatusChange
        fields = ["id", "request", "from_status", "to_status", "changed_by", "changed_at"]
        read_only_fields = fields


class RequestStatusSerializer(serializers.Serializer):
    # This checks the status name; the view will check transition order and role.
    status = serializers.ChoiceField(choices=RequestStatus.choices)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "organisation", "role", "password"]
        read_only_fields = ["id"]

    def validate(self, data):
        # Give Django account details so it can reject a similar/weak password.
        user = User(
            username=data["username"], email=data["email"], name=data["name"]
        )
        try:
            validate_password(data["password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages})
        return data

    def create(self, validated_data):
        # create_user hashes the password; ordinary objects.create would not.
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    # Admin account updates are limited to the two required operations.
    class Meta:
        model = User
        fields = ["id", "role", "is_active"]
        read_only_fields = ["id"]

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
