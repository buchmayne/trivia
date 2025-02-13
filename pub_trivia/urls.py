from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("quiz/", include("quiz.urls")),
    path("health/", views.health_check, name="health_check"),
    path("", include("quiz.urls")),
]
