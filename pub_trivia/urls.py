from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from . import views
from quiz.views import landing_page_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("health/", views.health_check, name="health_check"),
    path("quiz/", include("quiz.urls")),
    path("", landing_page_view, name="home"),
]

# Offline mode (pub_trivia.settings_offline) serves game media locally from
# MEDIA_ROOT instead of CloudFront/S3. No-op for normal dev/prod settings.
if getattr(settings, "OFFLINE_MODE", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
