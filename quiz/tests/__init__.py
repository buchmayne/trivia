"""
Test suite for the quiz application.

This package contains all tests for the trivia quiz application, organized by component:

Models:
    - test_models.py: Core models (Game, Question, Answer, QuestionRound)
    - test_session_models.py: Session models (GameSession, SessionTeam, TeamAnswer)
    - test_analytics.py: Analytics models (GameResult, PlayerStats)

Views:
    - test_views.py: Core views (game_list, game_overview, question_view)
    - test_views_extended.py: Extended view tests with edge cases
    - test_session_views.py: Session views (host_dashboard, team_join, live_session)

API:
    - test_api.py: DRF ViewSets (GameViewSet, QuestionViewSet)
    - test_api_views.py: REST API endpoints for sessions

Serializers:
    - test_serializers.py: DRF serializers

Fields:
    - test_fields.py: Custom model fields (CloudFrontURLField, S3ImageField, S3VideoField)

Integration:
    - test_integration.py: End-to-end workflow tests

Run all tests:
    uv run manage.py test quiz

Run specific test module:
    uv run manage.py test quiz.tests.test_models
    uv run manage.py test quiz.tests.test_api_views

Run specific test class:
    uv run manage.py test quiz.tests.test_models.GameModelTest

Run specific test method:
    uv run manage.py test quiz.tests.test_models.GameModelTest.test_game_creation
"""
