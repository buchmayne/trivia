from django.contrib import admin
from django.urls import path, include  # Import include to link app URLs

urlpatterns = [
    path("admin/", admin.site.urls),
    path('quiz/', include('quiz.urls')),  # Include the URLs from the quiz app
]
