from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from .api import GameViewSet, QuestionViewSet

app_name = "quiz"

router = DefaultRouter()
router.register(r'games', GameViewSet)
router.register(r'questions', QuestionViewSet)

urlpatterns = [
    path("", views.game_list_view, name="game_list"),  # List available games
    path(
        "game/<int:game_id>/questions/round/<int:round_id>/questions/category/<int:category_id>/question/<int:question_id>/",
        views.question_view,
        name="question_view",
    ),
    path(
        "game/<int:game_id>/answers/round/<int:round_id>/answers/category/<int:category_id>/question/<int:question_id>/",
        views.answer_view,
        name="answer_view",
    ),
    path(
        "api/rounds/<int:round_id>/first-question/",
        views.get_first_question,
        name="first_question",
    ),
    path(
        "quiz/game/<int:game_id>/round/<int:round_id>/first-question-info/",
        views.get_first_question_info,
        name="first_question_info",
    ),
    path(
        "game/<int:game_id>/questions/round/<int:round_id>/questions-list/",
        views.get_round_questions,
        name="round_questions_list",
    ),
    path("game/<int:game_id>/overview/", views.game_overview, name="game_overview"),
    path(
        "game/<int:game_id>/verify-password/",
        views.verify_game_password,
        name="verify_password",
    ),
    path("analytics/", views.analytics_view, name="analytics"),
    path(
        "next-question/<int:game_id>/",
        views.get_next_question_number,
        name="next_question_number",
    ),
    path("api/", include(router.urls))
]
