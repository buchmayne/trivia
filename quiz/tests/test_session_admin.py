"""
Tests for session admin interface.

Verifies admin registrations and custom admin features.
"""

from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils import timezone
from unittest.mock import MagicMock

from quiz.models import (
    Game,
    GameSession,
    SessionTeam,
    SessionRound,
    TeamAnswer,
    Question,
    QuestionRound,
    Category,
    QuestionType,
)
from quiz.admin import (
    GameSessionAdmin,
    SessionTeamAdmin,
    SessionRoundAdmin,
    TeamAnswerAdmin,
)


def get_mock_request():
    """Create a mock request for testing admin actions"""
    request = HttpRequest()
    request.META = {"SERVER_NAME": "testserver", "SERVER_PORT": 80}
    request.method = "GET"
    return request


class GameSessionAdminTest(TestCase):
    """Test GameSession admin interface"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = GameSessionAdmin(GameSession, self.site)

        # Create test data
        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Test Admin", max_teams=16
        )
        self.team = SessionTeam.objects.create(session=self.session, name="Test Team")

    def test_admin_registered(self):
        """Test that GameSession is registered in admin"""
        from django.contrib import admin

        self.assertIn(GameSession, admin.site._registry)

    def test_list_display(self):
        """Test list display fields"""
        self.assertEqual(
            self.admin.list_display,
            (
                "code",
                "game",
                "admin_name",
                "status",
                "team_count",
                "created_at",
                "started_at",
            ),
        )

    def test_team_count_method(self):
        """Test team_count display method"""
        count = self.admin.team_count(self.session)
        self.assertEqual(count, 1)

    def test_display_admin_token(self):
        """Test admin token display method"""
        result = self.admin.display_admin_token(self.session)
        self.assertIn(self.session.admin_token, result)
        self.assertIn('type="text"', result)

    def test_end_session_action(self):
        """Test end session custom action"""
        self.assertEqual(self.session.status, GameSession.Status.LOBBY)

        request = get_mock_request()
        # Mock the message_user method to avoid messaging middleware requirement
        self.admin.message_user = MagicMock()
        queryset = GameSession.objects.filter(id=self.session.id)

        self.admin.end_session(request, queryset)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.COMPLETED)
        self.assertIsNotNone(self.session.completed_at)
        # Verify message_user was called
        self.admin.message_user.assert_called_once()

    def test_recalculate_scores_action(self):
        """Test recalculate scores custom action"""
        # Create question and answer
        round1 = QuestionRound.objects.create(round_number=1, name="Round 1")
        category = Category.objects.create(name="General")
        question_type = QuestionType.objects.create(name="Open", description="Open")

        question = Question.objects.create(
            game=self.game,
            question_number=1,
            text="Test Q",
            total_points=10,
            category=category,
            question_type=question_type,
            game_round=round1,
        )

        session_round = SessionRound.objects.create(session=self.session, round=round1)

        # Create answer with points
        TeamAnswer.objects.create(
            team=self.team,
            question=question,
            session_round=session_round,
            answer_text="Test",
            points_awarded=10,
        )

        # Manually set wrong score
        self.team.score = 0
        self.team.save()

        request = get_mock_request()
        # Mock the message_user method
        self.admin.message_user = MagicMock()
        queryset = GameSession.objects.filter(id=self.session.id)

        self.admin.recalculate_team_scores(request, queryset)

        self.team.refresh_from_db()
        self.assertEqual(self.team.score, 10)
        # Verify message_user was called
        self.admin.message_user.assert_called_once()

    def test_readonly_fields(self):
        """Test that security fields are read-only"""
        self.assertIn("admin_token", self.admin.readonly_fields)
        self.assertIn("code", self.admin.readonly_fields)


class SessionTeamAdminTest(TestCase):
    """Test SessionTeam admin interface"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = SessionTeamAdmin(SessionTeam, self.site)

        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")
        self.team = SessionTeam.objects.create(
            session=self.session, name="Test Team", score=50
        )

    def test_admin_registered(self):
        """Test that SessionTeam is registered in admin"""
        from django.contrib import admin

        self.assertIn(SessionTeam, admin.site._registry)

    def test_session_code_method(self):
        """Test session_code display method"""
        result = self.admin.session_code(self.team)
        self.assertEqual(result, self.session.code)

    def test_answer_count_method(self):
        """Test answer_count display method"""
        count = self.admin.answer_count(self.team)
        self.assertEqual(count, 0)

    def test_display_token(self):
        """Test team token display method"""
        result = self.admin.display_token(self.team)
        self.assertIn(self.team.token, result)
        self.assertIn('type="text"', result)


class SessionRoundAdminTest(TestCase):
    """Test SessionRound admin interface"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = SessionRoundAdmin(SessionRound, self.site)

        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")
        self.round = QuestionRound.objects.create(round_number=1, name="Round 1")
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )

    def test_admin_registered(self):
        """Test that SessionRound is registered in admin"""
        from django.contrib import admin

        self.assertIn(SessionRound, admin.site._registry)

    def test_session_code_method(self):
        """Test session_code display method"""
        result = self.admin.session_code(self.session_round)
        self.assertEqual(result, self.session.code)

    def test_round_name_method(self):
        """Test round_name display method"""
        result = self.admin.round_name(self.session_round)
        self.assertEqual(result, "Round 1")

    def test_round_number_method(self):
        """Test round_number display method"""
        result = self.admin.round_number(self.session_round)
        self.assertEqual(result, 1)


class TeamAnswerAdminTest(TestCase):
    """Test TeamAnswer admin interface"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = TeamAnswerAdmin(TeamAnswer, self.site)

        # Create test data
        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")
        self.team = SessionTeam.objects.create(session=self.session, name="Test Team")

        self.round = QuestionRound.objects.create(round_number=1, name="Round 1")
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )

        self.category = Category.objects.create(name="General")
        self.question_type = QuestionType.objects.create(
            name="Open", description="Open"
        )
        self.question = Question.objects.create(
            game=self.game,
            question_number=1,
            text="Test Question",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
        )

        self.answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="This is a test answer",
            points_awarded=8,
        )

    def test_admin_registered(self):
        """Test that TeamAnswer is registered in admin"""
        from django.contrib import admin

        self.assertIn(TeamAnswer, admin.site._registry)

    def test_team_name_method(self):
        """Test team_name display method"""
        result = self.admin.team_name(self.answer)
        self.assertEqual(result, "Test Team")

    def test_session_code_method(self):
        """Test session_code display method"""
        result = self.admin.session_code(self.answer)
        self.assertEqual(result, self.session.code)

    def test_question_number_method(self):
        """Test question_number display method"""
        result = self.admin.question_number(self.answer)
        self.assertEqual(result, "Q1")

    def test_answer_preview_short(self):
        """Test answer_preview with short text"""
        result = self.admin.answer_preview(self.answer)
        self.assertEqual(result, "This is a test answer")

    def test_answer_preview_long(self):
        """Test answer_preview with long text"""
        self.answer.answer_text = "A" * 100
        self.answer.save()

        result = self.admin.answer_preview(self.answer)
        self.assertEqual(len(result), 53)  # 50 chars + "..."
        self.assertTrue(result.endswith("..."))

    def test_answer_preview_empty(self):
        """Test answer_preview with empty text"""
        self.answer.answer_text = ""
        self.answer.save()

        result = self.admin.answer_preview(self.answer)
        self.assertEqual(result, "(empty)")


class AdminInlinesTest(TestCase):
    """Test inline admin configurations"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")

    def test_session_has_team_inline(self):
        """Test that GameSession admin has team inline"""
        from quiz.admin import SessionTeamInline

        admin = GameSessionAdmin(GameSession, AdminSite())
        inline_classes = [
            inline.__class__ for inline in admin.get_inline_instances(None)
        ]
        self.assertIn(SessionTeamInline, inline_classes)

    def test_session_has_round_inline(self):
        """Test that GameSession admin has round inline"""
        from quiz.admin import SessionRoundInline

        admin = GameSessionAdmin(GameSession, AdminSite())
        inline_classes = [
            inline.__class__ for inline in admin.get_inline_instances(None)
        ]
        self.assertIn(SessionRoundInline, inline_classes)

    def test_team_has_answer_inline(self):
        """Test that SessionTeam admin has answer inline"""
        from quiz.admin import TeamAnswerInline

        admin = SessionTeamAdmin(SessionTeam, AdminSite())
        inline_classes = [
            inline.__class__ for inline in admin.get_inline_instances(None)
        ]
        self.assertIn(TeamAnswerInline, inline_classes)


class AdminFiltersTest(TestCase):
    """Test custom admin filters"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session1 = GameSession.objects.create(
            game=self.game,
            admin_name="Admin 1",
            status=GameSession.Status.LOBBY,
        )
        self.session2 = GameSession.objects.create(
            game=self.game,
            admin_name="Admin 2",
            status=GameSession.Status.PLAYING,
        )

    def test_session_status_filter_lookups(self):
        """Test SessionStatusFilter provides correct choices"""
        from quiz.admin import SessionStatusFilter

        filter_instance = SessionStatusFilter(
            None, {}, GameSession, GameSessionAdmin(GameSession, AdminSite())
        )
        lookups = filter_instance.lookups(None, None)

        # Should match all GameSession.Status choices
        self.assertEqual(len(lookups), len(GameSession.Status.choices))

    def test_round_status_filter_lookups(self):
        """Test RoundStatusFilter provides correct choices"""
        from quiz.admin import RoundStatusFilter

        filter_instance = RoundStatusFilter(
            None, {}, SessionRound, SessionRoundAdmin(SessionRound, AdminSite())
        )
        lookups = filter_instance.lookups(None, None)

        # Should match all SessionRound.Status choices
        self.assertEqual(len(lookups), len(SessionRound.Status.choices))
