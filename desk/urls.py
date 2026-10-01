from django.urls import path

from .views import (
    CurrentUserView,
    LoginView,
    LogoutView,
    RequestDetailView,
    RequestHistoryView,
    RequestListCreateView,
    RequestStatusView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("requests/", RequestListCreateView.as_view(), name="request-list-create"),
    path("requests/<int:pk>/", RequestDetailView.as_view(), name="request-detail"),
    path("requests/<int:pk>/history/", RequestHistoryView.as_view(), name="request-history"),
    path("requests/<int:pk>/status/", RequestStatusView.as_view(), name="request-status"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
]
