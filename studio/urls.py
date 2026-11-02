from django.urls import path

from . import views

app_name = "studio"

urlpatterns = [
    path("", views.library, name="library"),
    path("capture/", views.capture, name="capture"),
    path("categories/new/", views.add_category, name="add_category"),
    path("challenges/<int:pk>/", views.edit, name="edit"),
    path("challenges/<int:pk>/status/", views.change_status, name="change_status"),
    path("challenges/<int:pk>/tasks/new/", views.task_form, name="new_task"),
    path("challenges/<int:pk>/tasks/<int:task_pk>/", views.task_form, name="edit_task"),
    path("challenges/<int:pk>/blocks/new/", views.block_form, name="new_block"),
    path(
        "challenges/<int:pk>/blocks/<int:block_pk>/",
        views.block_form,
        name="edit_block",
    ),
    path(
        "challenges/<int:pk>/<str:kind>/<int:item_pk>/<str:action>/",
        views.item_action,
        name="item_action",
    ),
    path("challenges/<int:pk>/preview/<str:mode>/", views.preview, name="preview"),
]
