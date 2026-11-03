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
    path(
        "challenges/<int:pk>/tasks/<int:task_pk>/options/new/",
        views.option_form,
        name="new_option",
    ),
    path(
        "challenges/<int:pk>/tasks/<int:task_pk>/options/<int:item_pk>/",
        views.option_form,
        name="edit_option",
    ),
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
    path("games/", views.games, name="games"),
    path("games/new/", views.new_game, name="new_game"),
    path("games/<int:pk>/", views.game_editor, name="game_editor"),
    path("games/<int:pk>/rounds/", views.game_add_round, name="game_add_round"),
    path(
        "games/<int:pk>/rounds/<int:round_pk>/placements/",
        views.game_add_placement,
        name="game_add_placement",
    ),
    path(
        "games/<int:pk>/<str:kind>/<int:item_pk>/<str:action>/",
        views.game_item_action,
        name="game_item_action",
    ),
    path(
        "games/<int:pk>/preview/<str:mode>/",
        views.game_preview_page,
        name="game_preview",
    ),
]
