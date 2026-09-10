"""
Tests for session frontend views.

Covers:
- session_landing view
- session_host view
- session_join view
- session_play view
"""

import json
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escapejs
from quiz.session_cookies import COOKIE_NAME
from quiz.models import (
    Game,
    GameSession,
    SessionTeam,
    Question,
    QuestionRound,
    Category,
    QuestionType,
)
from quiz.tests.test_utils import create_verified_user


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

    def test_landing_page_hides_my_games_button_when_anonymous(self):
        """Anonymous visitors shouldn't see a My Games button they can't use"""
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("quiz:session_my_games"))

    def test_landing_page_shows_my_games_button_when_authenticated(self):
        """Logged-in visitors see a button into their My Games portal"""
        create_verified_user(username="landinguser", email="landing@example.com")
        self.client.login(username="landinguser", password="testpass123")

        response = self.client.get(self.url)

        self.assertContains(response, reverse("quiz:session_my_games"))

    def test_landing_page_has_correct_links(self):
        """Test that landing page links to host and join pages"""
        response = self.client.get(self.url)
        self.assertContains(response, reverse("quiz:session_host"))
        self.assertContains(response, reverse("quiz:session_join"))

    def test_landing_page_offers_rejoin(self):
        """A player who lost their seat needs a route back from this page"""
        response = self.client.get(self.url)
        self.assertContains(response, "Rejoin a Game")
        self.assertContains(response, reverse("quiz:session_rejoin_page"))


class SessionHostViewTest(TestCase):
    """Tests for the host game session view"""

    def setUp(self):
        self.client = Client()
        self.user = create_verified_user()
        self.client.login(username="testuser", password="testpass123")
        self.url = reverse("quiz:session_host")

        # Create test games (public so regular user can see them)
        self.game1 = Game.objects.create(
            subtitle="Test Game 1", description="First test game", is_public=True
        )
        self.game2 = Game.objects.create(
            subtitle="Test Game 2", description="Second test game", is_public=True
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


class SessionRejoinViewTest(TestCase):
    """Tests for the rejoin (session recovery) view"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("quiz:session_rejoin_page")

    def test_rejoin_page_loads(self):
        """Test that the rejoin page loads successfully"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/sessions/rejoin.html")

    def test_rejoin_page_has_form_fields(self):
        """Rejoin needs both the code and the team name to identify a team"""
        response = self.client.get(self.url)
        self.assertContains(response, 'id="sessionCode"')
        self.assertContains(response, 'id="teamName"')
        self.assertContains(response, "Rejoin Game")

    def test_rejoin_page_has_resume_section(self):
        """The one-tap resume list is present for tokens still in localStorage"""
        response = self.client.get(self.url)
        self.assertContains(response, 'id="resumeSection"')

    def test_rejoin_page_links_to_join_and_landing(self):
        """A player on the wrong page needs a way over to a fresh join"""
        response = self.client.get(self.url)
        self.assertContains(response, reverse("quiz:session_join"))
        self.assertContains(response, reverse("quiz:session_landing"))

    def test_rejoin_page_is_not_shadowed_by_play_route(self):
        """`play/rejoin/` must resolve to the page, not play/<code>/"""
        self.assertEqual(self.url, "/quiz/play/rejoin/")
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "quiz/sessions/rejoin.html")

    def test_rejoin_page_lists_remembered_sessions(self):
        """Sessions from the HttpOnly cookie are rendered as one-tap resumes"""
        game = Game.objects.create(subtitle="Cookie Game")
        session = GameSession.objects.create(game=game, admin_name="Host")
        team = SessionTeam.objects.create(session=session, name="Cookie Team")
        self.client.cookies[COOKIE_NAME] = json.dumps({session.code: team.token})

        response = self.client.get(self.url)

        self.assertEqual(len(response.context["resumable_sessions"]), 1)
        self.assertContains(response, "Resume as Cookie Team")
        self.assertContains(response, reverse("quiz:session_play", args=[session.code]))
        # Section is visible rather than hidden when there is something to show
        self.assertContains(response, 'id="resumeSection" class=""')

    def test_rejoin_page_hides_resume_section_without_cookie(self):
        response = self.client.get(self.url)

        self.assertEqual(response.context["resumable_sessions"], [])
        self.assertContains(response, 'id="resumeSection" class="hidden"')

    def test_rejoin_page_omits_completed_sessions(self):
        """A finished game is not something to resume"""
        game = Game.objects.create(subtitle="Cookie Game")
        session = GameSession.objects.create(
            game=game, admin_name="Host", status=GameSession.Status.COMPLETED
        )
        team = SessionTeam.objects.create(session=session, name="Cookie Team")
        self.client.cookies[COOKIE_NAME] = json.dumps({session.code: team.token})

        response = self.client.get(self.url)

        self.assertEqual(response.context["resumable_sessions"], [])


class SessionPlayViewTest(TestCase):
    """Tests for the live session play view"""

    def setUp(self):
        self.client = Client()

        # Create test game with questions
        self.game = Game.objects.create(
            subtitle="Test Game", description="Test game for session"
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

    def test_play_page_recovers_team_token_from_cookie(self):
        """A remembered team is handed its token back with nothing to type"""
        team = SessionTeam.objects.create(session=self.session, name="Cookie Team")
        self.client.cookies[COOKIE_NAME] = json.dumps({self.session.code: team.token})

        response = self.client.get(self.url)

        self.assertEqual(response.context["cookie_team_token"], team.token)
        # Tokens are base64url and escapejs escapes hyphens, so the rendered
        # literal is not byte-identical to the token - JS decodes it back.
        self.assertContains(
            response, f"const COOKIE_TEAM_TOKEN = '{escapejs(team.token)}'"
        )

    def test_play_page_without_cookie_has_no_recovered_token(self):
        """No cookie means the page falls back to localStorage and rejoin"""
        response = self.client.get(self.url)

        self.assertEqual(response.context["cookie_team_token"], "")
        self.assertContains(response, "const COOKIE_TEAM_TOKEN = ''")

    def test_play_page_ignores_cookie_token_from_another_session(self):
        """A token remembered elsewhere can't recover a seat here"""
        other_session = GameSession.objects.create(
            game=self.game, admin_name="Other Host"
        )
        other_team = SessionTeam.objects.create(
            session=other_session, name="Other Team"
        )
        self.client.cookies[COOKIE_NAME] = json.dumps(
            {self.session.code: other_team.token}
        )

        response = self.client.get(self.url)

        self.assertEqual(response.context["cookie_team_token"], "")

    def test_play_page_ignores_stale_cookie_token(self):
        """A token whose team is gone recovers nothing"""
        team = SessionTeam.objects.create(session=self.session, name="Cookie Team")
        token = team.token
        team.delete()
        self.client.cookies[COOKIE_NAME] = json.dumps({self.session.code: token})

        response = self.client.get(self.url)

        self.assertEqual(response.context["cookie_team_token"], "")

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
        self.game = Game.objects.create(subtitle="Test Game", description="Test")
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


class MyGamesViewTest(TestCase):
    """Tests for the my_games (portal) view"""

    def setUp(self):
        self.client = Client()
        self.owner = create_verified_user(username="owner", email="owner@example.com")
        self.other_user = create_verified_user(
            username="otheruser", email="other@example.com"
        )
        self.game = Game.objects.create(subtitle="Test Game", is_public=True)
        self.url = reverse("quiz:session_my_games")

    def test_requires_login(self):
        """Anonymous requests are redirected to login"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_only_lists_own_sessions(self):
        """Only sessions hosted by request.user appear"""
        own_session = GameSession.objects.create(
            game=self.game, admin_name="Owner", host_user=self.owner
        )
        GameSession.objects.create(
            game=self.game, admin_name="Other", host_user=self.other_user
        )

        self.client.login(username="owner", password="testpass123")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        codes_shown = [s.code for s in response.context["active_sessions"]]
        self.assertIn(own_session.code, codes_shown)
        self.assertEqual(len(codes_shown), 1)

    def test_active_sessions_never_paginated_out(self):
        """All non-completed sessions appear regardless of count"""
        for i in range(25):
            GameSession.objects.create(
                game=self.game, admin_name=f"Host {i}", host_user=self.owner
            )

        self.client.login(username="owner", password="testpass123")
        response = self.client.get(self.url)

        self.assertEqual(len(response.context["active_sessions"]), 25)

    def test_completed_sessions_paginate_at_twenty(self):
        """Completed sessions paginate 20 per page"""
        for i in range(25):
            GameSession.objects.create(
                game=self.game,
                admin_name=f"Host {i}",
                host_user=self.owner,
                status=GameSession.Status.COMPLETED,
                completed_at=timezone.now(),
            )

        self.client.login(username="owner", password="testpass123")
        response = self.client.get(self.url)

        history_page = response.context["history_page"]
        self.assertEqual(len(history_page.object_list), 20)
        self.assertEqual(history_page.paginator.num_pages, 2)

        response_page2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(response_page2.context["history_page"].object_list), 5)

    def test_presence_badge_reflects_recent_team_activity(self):
        """Teams seen recently count as active; stale teams don't"""
        session = GameSession.objects.create(
            game=self.game, admin_name="Owner", host_user=self.owner
        )
        SessionTeam.objects.create(session=session, name="Recent")
        stale_team = SessionTeam.objects.create(session=session, name="Stale")
        SessionTeam.objects.filter(pk=stale_team.pk).update(
            last_seen=timezone.now() - timedelta(hours=2)
        )

        self.client.login(username="owner", password="testpass123")
        response = self.client.get(self.url)

        presence = response.context["active_sessions"][0].presence
        self.assertEqual(presence["team_count"], 2)
        self.assertEqual(presence["active_team_count"], 1)
