from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User, UserRole
from .permissions import IsAdmin
from .serializers import (
    LoginSerializer,
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
