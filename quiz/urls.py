from django.urls import path, include
from . import views, api_views, session_views
from rest_framework.routers import DefaultRouter
from .api import GameViewSet, QuestionViewSet

app_name = "quiz"

router = DefaultRouter()
router.register(r"games", GameViewSet)
router.register(r"questions", QuestionViewSet)

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
    
    # New Session Frontend URLs (for humans)
    path('sessions/host/', session_views.host_dashboard, name='host_dashboard'),
    path('sessions/join/', session_views.team_join, name='team_join'),
    path('sessions/live/<str:session_code>/', session_views.live_session, name='live_session'),
    
    # New API URLs (for Go service)
    path('api/sessions/create/', api_views.create_session, name='api_create_session'),
    path('api/sessions/<int:session_id>/info/', api_views.get_session_info, name='api_session_info'),
    path('api/sessions/<int:session_id>/status/', api_views.update_session_status, name='api_update_session_status'),
    path('api/sessions/<int:session_id>/teams/add/', api_views.add_team_to_session, name='api_add_team'),
    path('api/sessions/<int:session_id>/finalize/', api_views.finalize_session, name='api_finalize_session'),
    path('api/games/<int:game_id>/questions/', api_views.get_game_questions, name='api_game_questions'),
    path('api/answers/submit/', api_views.submit_team_answer, name='api_submit_answer'),
    
    # Existing DRF API
    path("api/", include(router.urls)),
]
