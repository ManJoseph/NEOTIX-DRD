from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DatasetRequest, RequestStatus, StatusChange, User, UserRole
from .pagination import RequestPagination
from .permissions import IsAdmin
from .serializers import (
    DatasetRequestSerializer,
    LoginSerializer,
    RequestStatusSerializer,
    StatusChangeSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .throttles import LoginThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        # Django's default authentication backend also rejects inactive users.
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListCreateView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.order_by("id")
        return Response(UserSerializer(users, many=True).data)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            # Another admin may create the same account after validation.
            username = serializer.validated_data["username"]
            email = serializer.validated_data["email"]
            if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                raise ValidationError("A user with this username or email already exists.")
            raise
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response(UserSerializer(user).data)

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if user.pk == request.user.pk:
            new_role = serializer.validated_data.get("role", user.role)
            new_active = serializer.validated_data.get("is_active", user.is_active)
            if new_role != UserRole.ADMIN or not new_active:
                raise ValidationError("You cannot deactivate yourself or remove your own admin role.")
        with transaction.atomic():
            user = serializer.save()
            if not user.is_active:
                Token.objects.filter(user=user).delete()
        return Response(UserSerializer(user).data)


def requests_visible_to(user):
    # Reuse this filter for lists, details, history, and status changes.
    requests = DatasetRequest.objects.all()
    if user.role == UserRole.CLIENT:
        requests = requests.filter(client=user)
    return requests


class RequestListCreateView(APIView):
    def get(self, request):
        requests = requests_visible_to(request.user).order_by("-created_at", "-id")
        paginator = RequestPagination()
        page = paginator.paginate_queryset(requests, request)
        serializer = DatasetRequestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if request.user.role != UserRole.CLIENT:
            raise PermissionDenied("Only clients can create dataset requests.")
        serializer = DatasetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # A request and its initial history event must be saved together.
        with transaction.atomic():
            dataset_request = serializer.save(client=request.user)
            StatusChange.objects.create(
                request=dataset_request,
                from_status="",
                to_status=RequestStatus.SUBMITTED,
                changed_by=request.user,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RequestDetailView(APIView):
    def get(self, request, pk):
        dataset_request = get_object_or_404(requests_visible_to(request.user), pk=pk)
        return Response(DatasetRequestSerializer(dataset_request).data)


class RequestHistoryView(APIView):
    def get(self, request, pk):
        dataset_request = get_object_or_404(requests_visible_to(request.user), pk=pk)
        history = dataset_request.status_changes.order_by("changed_at", "id")
        return Response(StatusChangeSerializer(history, many=True).data)


class RequestStatusView(APIView):
    def post(self, request, pk):
        serializer = RequestStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        with transaction.atomic():
            # Lock this request so two people cannot change it simultaneously.
            requests = requests_visible_to(request.user).select_for_update()
            dataset_request = get_object_or_404(requests, pk=pk)
            old_status = dataset_request.status

            if request.user.role == UserRole.CLIENT:
                if new_status not in [RequestStatus.ACCEPTED, RequestStatus.REJECTED]:
                    raise PermissionDenied("Clients can only accept or reject a delivery.")
                allowed_transitions = [
                    (RequestStatus.DELIVERED, RequestStatus.ACCEPTED),
                    (RequestStatus.DELIVERED, RequestStatus.REJECTED),
                ]
            else:
                if new_status not in [RequestStatus.IN_PROGRESS, RequestStatus.DELIVERED]:
                    raise PermissionDenied("Only the owning client can accept or reject a delivery.")
                allowed_transitions = [
                    (RequestStatus.SUBMITTED, RequestStatus.IN_PROGRESS),
                    (RequestStatus.IN_PROGRESS, RequestStatus.DELIVERED),
                    (RequestStatus.REJECTED, RequestStatus.IN_PROGRESS),
                ]

            if (old_status, new_status) not in allowed_transitions:
                raise ValidationError({
                    "status": f"Cannot move a request from {old_status} to {new_status}."
                })

            if new_status == RequestStatus.DELIVERED:
                assigned_count = dataset_request.assignments.count()
                if assigned_count < dataset_request.episodes_requested:
                    raise ValidationError({
                        "status": "Assign enough episodes before delivering this request."
                    })
                if dataset_request.delivered_at is None:
                    dataset_request.delivered_at = timezone.now()

            dataset_request.status = new_status
            dataset_request.save(update_fields=["status", "delivered_at", "updated_at"])
            StatusChange.objects.create(
                request=dataset_request,
                from_status=old_status,
                to_status=new_status,
                changed_by=request.user,
            )
        return Response(DatasetRequestSerializer(dataset_request).data)
