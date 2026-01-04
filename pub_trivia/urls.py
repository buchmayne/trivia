from django.contrib import admin
from django.urls import path, include
from . import views
from quiz.views import landing_page_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", views.health_check, name="health_check"),
    path("quiz/", include("quiz.urls")),
    path("", landing_page_view, name="home"),
]
