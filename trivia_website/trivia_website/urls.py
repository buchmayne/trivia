from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("trivia_app/", include("trivia_app.urls")),
    path("admin/", admin.site.urls),
]