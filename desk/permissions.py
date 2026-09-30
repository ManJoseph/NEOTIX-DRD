from rest_framework.permissions import BasePermission

from .models import UserRole


class IsAdmin(BasePermission):
    message = "Only admins can manage users."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.ADMIN
