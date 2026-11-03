"""The sandbox has no legacy application routes."""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="studio:library", permanent=False)),
    path(
        "accounts/login/",
        LoginView.as_view(template_name="studio_sandbox/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(next_page="/accounts/login/"),
        name="logout",
    ),
    path("studio/", include("studio.urls")),
]
