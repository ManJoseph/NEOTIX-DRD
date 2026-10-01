from django.urls import path

from .views import (
    AssignmentRemoveView,
    CurrentUserView,
    EpisodeListView,
    RequestAssignmentView,
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
    path("episodes/", EpisodeListView.as_view(), name="episode-list"),
    path("requests/<int:pk>/assignments/", RequestAssignmentView.as_view(), name="request-assignments"),
    path("requests/<int:pk>/assignments/<int:assignment_pk>/", AssignmentRemoveView.as_view(), name="assignment-remove"),
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
