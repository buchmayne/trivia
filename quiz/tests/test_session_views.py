"""
Tests for quiz/session_views.py - Frontend views for game sessions
"""

from django.test import TestCase, Client
from django.urls import reverse
from quiz.models import Game, GameSession


class HostDashboardViewTest(TestCase):
    """Test the host_dashboard view"""

    def setUp(self):
        self.client = Client()
        self.game1 = Game.objects.create(name="Trivia Game 1")
        self.game2 = Game.objects.create(name="Another Game")
        self.url = reverse("quiz:host_dashboard")

    def test_host_dashboard_loads(self):
        """Test that host dashboard page loads successfully"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/host_dashboard.html")

    def test_host_dashboard_shows_games(self):
        """Test that all games are displayed in the dashboard"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("games", response.context)
        self.assertEqual(len(response.context["games"]), 2)

    def test_host_dashboard_games_ordered_by_name(self):
        """Test that games are ordered alphabetically by name"""
        response = self.client.get(self.url)

        games = list(response.context["games"])
        self.assertEqual(games[0].name, "Another Game")
        self.assertEqual(games[1].name, "Trivia Game 1")

    def test_host_dashboard_empty_games(self):
        """Test host dashboard with no games available"""
        Game.objects.all().delete()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["games"]), 0)


class TeamJoinViewTest(TestCase):
    """Test the team_join view"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("quiz:team_join")

    def test_team_join_loads(self):
        """Test that team join page loads successfully"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/team_join.html")

    def test_team_join_no_context_required(self):
        """Test that team join page doesn't require special context"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # This is a simple page, verify it renders without errors


class LiveSessionViewTest(TestCase):
    """Test the live_session view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            status="waiting",
        )

    def test_live_session_team_view(self):
        """Test team view of live session"""
        url = reverse("quiz:live_session", args=[self.session.session_code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/team_live_session.html")
        self.assertEqual(response.context["session_code"], "ABC123")
        self.assertEqual(response.context["session"], self.session)
        self.assertFalse(response.context["is_host"])

    def test_live_session_host_view(self):
        """Test host view of live session"""
        url = reverse("quiz:live_session", args=[self.session.session_code])
        response = self.client.get(url, {"host": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/host_live_session.html")
        self.assertEqual(response.context["session_code"], "ABC123")
        self.assertTrue(response.context["is_host"])

    def test_live_session_includes_game_context(self):
        """Test that live session includes game in context"""
        url = reverse("quiz:live_session", args=[self.session.session_code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["game"], self.game)

    def test_live_session_nonexistent_code(self):
        """Test accessing live session with invalid session code"""
        url = reverse("quiz:live_session", args=["INVALID"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_live_session_different_statuses(self):
        """Test live session view works with different session statuses"""
        statuses = ["waiting", "active", "paused", "completed"]

        for session_status in statuses:
            self.session.status = session_status
            self.session.save()

            url = reverse("quiz:live_session", args=[self.session.session_code])
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["session"].status, session_status)
