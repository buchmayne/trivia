from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from . import views
from quiz.views import game_list_view, analytics_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", views.health_check, name="health_check"),
    path("quiz/", include("quiz.urls")),
    path("new/", TemplateView.as_view(template_name='index.html')),
    path("", game_list_view, name="home"),
    path("analytics/", analytics_view, name="analytics"),
    re_path(r'^new/.*$', TemplateView.as_view(template_name='index.html')),    
]
