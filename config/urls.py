from django.urls import include, path

from desk.views import HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("api/", include("desk.urls")),
]
