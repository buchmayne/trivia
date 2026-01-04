"""
Tests for session frontend views.

Covers:
- session_landing view
- session_host view
- session_join view
- session_play view
"""

from django.test import TestCase, Client
from django.urls import reverse
from quiz.models import (
    Game,
    GameSession,
    SessionTeam,
    Question,
    QuestionRound,
    Category,
    QuestionType,
)


class SessionLandingViewTest(TestCase):
    """Tests for the session landing page view"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("quiz:session_landing")

    def test_landing_page_loads(self):
        """Test that the landing page loads successfully"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/sessions/landing.html")

    def test_landing_page_contains_navigation(self):
        """Test that landing page has host and join buttons"""
        response = self.client.get(self.url)
        self.assertContains(response, "Host a Game")
        self.assertContains(response, "Join a Game")

    def test_landing_page_has_correct_links(self):
        """Test that landing page links to host and join pages"""
        response = self.client.get(self.url)
        self.assertContains(response, reverse("quiz:session_host"))
        self.assertContains(response, reverse("quiz:session_join"))


class SessionHostViewTest(TestCase):
    """Tests for the host game session view"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("quiz:session_host")

        # Create test games
        self.game1 = Game.objects.create(
            name="Test Game 1", description="First test game"
        )
        self.game2 = Game.objects.create(
            name="Test Game 2", description="Second test game"
        )

    def test_host_page_loads(self):
        """Test that the host page loads successfully"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/sessions/host.html")

    def test_host_page_lists_games(self):
        """Test that host page displays available games"""
        response = self.client.get(self.url)
        self.assertContains(response, "Test Game 1")
        self.assertContains(response, "Test Game 2")

    def test_host_page_context_contains_games(self):
        """Test that context includes games queryset"""
        response = self.client.get(self.url)
        self.assertIn("games", response.context)
        self.assertEqual(len(response.context["games"]), 2)

    def test_host_page_has_form_fields(self):
        """Test that host page has required form fields"""
        response = self.client.get(self.url)
        self.assertContains(response, 'id="adminName"')
        self.assertContains(response, 'id="gameSelect"')
        self.assertContains(response, 'id="maxTeams"')

    def test_host_page_with_no_games(self):
        """Test host page when no games exist"""
        Game.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Game 1")


class SessionJoinViewTest(TestCase):
    """Tests for the join game session view"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("quiz:session_join")

    def test_join_page_loads(self):
        """Test that the join page loads successfully"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/sessions/join.html")

    def test_join_page_has_form_fields(self):
        """Test that join page has required form fields"""
        response = self.client.get(self.url)
        self.assertContains(response, 'id="sessionCode"')
        self.assertContains(response, 'id="teamName"')

    def test_join_page_has_submit_button(self):
        """Test that join page has submit button"""
        response = self.client.get(self.url)
        self.assertContains(response, "Join Game")

    def test_join_page_has_back_link(self):
        """Test that join page has back link to landing"""
        response = self.client.get(self.url)
        self.assertContains(response, reverse("quiz:session_landing"))


class SessionPlayViewTest(TestCase):
    """Tests for the live session play view"""

    def setUp(self):
        self.client = Client()

        # Create test game with questions
        self.game = Game.objects.create(
            name="Test Game", description="Test game for session"
        )

        # Create question round
        self.round = QuestionRound.objects.create(round_number=1, name="Round 1")

        # Create category and question type
        self.category = Category.objects.create(name="General Knowledge")
        self.question_type = QuestionType.objects.create(
            name="Open-Ended", description="Standard question"
        )

        # Create questions
        self.question1 = Question.objects.create(
            game=self.game,
            question_number=1,
            text="What is 2+2?",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
        )
        self.question2 = Question.objects.create(
            game=self.game,
            question_number=2,
            text="What is the capital of France?",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
        )

        # Create session
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Test Admin", max_teams=16
        )

        self.url = reverse("quiz:session_play", args=[self.session.code])

    def test_play_page_loads(self):
        """Test that the play page loads successfully"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/sessions/play.html")

    def test_play_page_with_invalid_code(self):
        """Test that invalid session code returns 404"""
        url = reverse("quiz:session_play", args=["INVALID"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_play_page_context_has_session(self):
        """Test that context includes session object"""
        response = self.client.get(self.url)
        self.assertIn("session", response.context)
        self.assertEqual(response.context["session"].code, self.session.code)

    def test_play_page_context_has_game(self):
        """Test that context includes game object"""
        response = self.client.get(self.url)
        self.assertIn("game", response.context)
        self.assertEqual(response.context["game"].id, self.game.id)

    def test_play_page_context_has_rounds_data(self):
        """Test that context includes rounds data"""
        response = self.client.get(self.url)
        self.assertIn("rounds_data", response.context)
        self.assertIsInstance(response.context["rounds_data"], dict)

    def test_play_page_displays_session_code(self):
        """Test that play page displays the session code"""
        response = self.client.get(self.url)
        self.assertContains(response, self.session.code)

    def test_play_page_displays_game_name(self):
        """Test that play page displays the game name"""
        response = self.client.get(self.url)
        self.assertContains(response, "Test Game")

    def test_play_page_has_javascript_constants(self):
        """Test that play page includes required JavaScript constants"""
        response = self.client.get(self.url)
        self.assertContains(response, f"const CODE = '{self.session.code}'")
        self.assertContains(response, "const ADMIN_TOKEN")
        self.assertContains(response, "const TEAM_TOKEN")

    def test_play_page_has_state_polling_logic(self):
        """Test that play page includes state polling functionality"""
        response = self.client.get(self.url)
        self.assertContains(response, "pollState")
        self.assertContains(response, "POLL_INTERVAL")

    def test_play_page_with_multiple_rounds(self):
        """Test play page when game has multiple rounds"""
        # Create second round
        round2 = QuestionRound.objects.create(round_number=2, name="Round 2")

        Question.objects.create(
            game=self.game,
            question_number=3,
            text="What is 3+3?",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=round2,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Check that rounds_data includes both rounds
        rounds_data = response.context["rounds_data"]
        self.assertEqual(len(rounds_data), 2)

    def test_play_page_with_teams_joined(self):
        """Test play page when teams have joined"""
        # Create teams
        team1 = SessionTeam.objects.create(session=self.session, name="Team Alpha")
        team2 = SessionTeam.objects.create(session=self.session, name="Team Beta")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Verify teams count is accessible
        self.assertEqual(response.context["session"].teams.count(), 2)

    def test_play_page_session_in_different_states(self):
        """Test play page with session in different states"""
        states = [
            GameSession.Status.LOBBY,
            GameSession.Status.PLAYING,
            GameSession.Status.PAUSED,
            GameSession.Status.SCORING,
            GameSession.Status.COMPLETED,
        ]

        for status in states:
            self.session.status = status
            self.session.save()

            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["session"].status, status)


class SessionViewURLRoutingTest(TestCase):
    """Tests for URL routing of session views"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")

    def test_landing_url_resolves(self):
        """Test that landing URL resolves correctly"""
        url = reverse("quiz:session_landing")
        self.assertEqual(url, "/quiz/play/")

    def test_host_url_resolves(self):
        """Test that host URL resolves correctly"""
        url = reverse("quiz:session_host")
        self.assertEqual(url, "/quiz/play/host/")

    def test_join_url_resolves(self):
        """Test that join URL resolves correctly"""
        url = reverse("quiz:session_join")
        self.assertEqual(url, "/quiz/play/join/")

    def test_play_url_resolves(self):
        """Test that play URL resolves correctly with session code"""
        url = reverse("quiz:session_play", args=[self.session.code])
        self.assertEqual(url, f"/quiz/play/{self.session.code}/")

    def test_play_url_with_different_codes(self):
        """Test that play URL works with different session codes"""
        session2 = GameSession.objects.create(game=self.game, admin_name="Admin2")

        url1 = reverse("quiz:session_play", args=[self.session.code])
        url2 = reverse("quiz:session_play", args=[session2.code])

        self.assertNotEqual(url1, url2)
        self.assertIn(self.session.code, url1)
        self.assertIn(session2.code, url2)
