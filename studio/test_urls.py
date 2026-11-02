"""URLconf for studio route tests, independent of the startup-only URL mount."""

from django.urls import include, path

urlpatterns = [path("studio/", include("studio.urls"))]
