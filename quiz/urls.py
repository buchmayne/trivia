from django.urls import path, include
from . import views, session_api, session_views
from rest_framework.routers import DefaultRouter
from .api import GameViewSet, QuestionViewSet

app_name = "quiz"

router = DefaultRouter()
router.register(r"games", GameViewSet)
router.register(r"questions", QuestionViewSet)

urlpatterns = [
    # Gallery mode - browse games
    path("gallery/", views.game_list_view, name="gallery"),
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
    path(
        "api/game/<int:game_id>/questions/",
        views.get_game_questions,
        name="api_game_questions",
    ),
    path("game/<int:game_id>/overview/", views.game_overview, name="game_overview"),
    path(
        "game/<int:game_id>/verify-password/",
        views.verify_game_password,
        name="verify_password",
    ),
    # Analytics mode
    path("analytics/", views.analytics_view, name="analytics"),
    path(
        "next-question/<int:game_id>/",
        views.get_next_question_number,
        name="next_question_number",
    ),
    path(
        "next-game-order/",
        views.get_next_game_order,
        name="next_game_order",
    ),
    # Session Frontend Views
    path("play/", session_views.session_landing, name="session_landing"),
    path("play/host/", session_views.session_host, name="session_host"),
    path("play/join/", session_views.session_join, name="session_join"),
    path("play/<str:code>/", session_views.session_play, name="session_play"),
    # Session API - Public
    path("api/sessions/create/", session_api.create_session, name="session_create"),
    path(
        "api/sessions/<str:code>/join/", session_api.join_session, name="session_join"
    ),
    path(
        "api/sessions/<str:code>/state/",
        session_api.get_session_state,
        name="session_state",
    ),
    # Session API - Admin
    path(
        "api/sessions/<str:code>/admin/start/",
        session_api.admin_start_game,
        name="session_admin_start",
    ),
    path(
        "api/sessions/<str:code>/admin/question/",
        session_api.admin_set_question,
        name="session_admin_question",
    ),
    path(
        "api/sessions/<str:code>/admin/toggle-team-navigation/",
        session_api.admin_toggle_team_navigation,
        name="session_admin_toggle_nav",
    ),
    path(
        "api/sessions/<str:code>/admin/lock-round/",
        session_api.admin_lock_round,
        name="session_admin_lock",
    ),
    path(
        "api/sessions/<str:code>/admin/scoring-data/",
        session_api.admin_get_scoring_data,
        name="session_admin_scoring",
    ),
    path(
        "api/sessions/<str:code>/admin/score/",
        session_api.admin_score_answer,
        name="session_admin_score",
    ),
    path(
        "api/sessions/<str:code>/admin/complete-round/",
        session_api.admin_complete_round,
        name="session_admin_complete",
    ),
    path(
        "api/sessions/<str:code>/admin/start-next-round/",
        session_api.admin_start_next_round,
        name="session_admin_start_next",
    ),
    # Session API - Team
    path(
        "api/sessions/<str:code>/team/answer/",
        session_api.team_submit_answer,
        name="session_team_answer",
    ),
    path(
        "api/sessions/<str:code>/team/answers/",
        session_api.team_get_answers,
        name="session_team_answers",
    ),
    path(
        "api/sessions/<str:code>/team/question/",
        session_api.team_get_question_details,
        name="session_team_question",
    ),
    path(
        "api/sessions/<str:code>/team/results/",
        session_api.team_get_results,
        name="session_team_results",
    ),
    # DRF API
    path("api/", include(router.urls)),
]
