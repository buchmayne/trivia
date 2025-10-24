"""
Tests for quiz/api_views.py - REST API endpoints for game sessions
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from quiz.models import (
    Game,
    Question,
    QuestionType,
    QuestionRound,
    Category,
    GameSession,
    SessionTeam,
    TeamAnswer,
)


class CreateSessionAPITest(TestCase):
    """Test the create_session API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.url = reverse("quiz:api_create_session")

    def test_create_session_success(self):
        """Test successfully creating a new game session"""
        data = {"game": self.game.id, "host_name": "Test Host"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.data)
        self.assertIn("session_code", response.data)
        self.assertEqual(response.data["game_id"], self.game.id)
        self.assertEqual(response.data["game_name"], self.game.name)
        self.assertEqual(len(response.data["session_code"]), 6)

        # Verify session was created in database
        self.assertTrue(
            GameSession.objects.filter(id=response.data["session_id"]).exists()
        )

    def test_create_session_missing_game(self):
        """Test creating session without game_id"""
        data = {"host_name": "Test Host"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("game", response.data)

    def test_create_session_missing_host_name(self):
        """Test creating session without host_name"""
        data = {"game": self.game.id}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("host_name", response.data)

    def test_create_session_invalid_game_id(self):
        """Test creating session with non-existent game"""
        data = {"game": 99999, "host_name": "Test Host"}

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, 400)


class GetGameQuestionsAPITest(TestCase):
    """Test the get_game_questions API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.category = Category.objects.create(name="Test Category")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create test questions
        self.question1 = Question.objects.create(
            game=self.game,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 1",
            question_number=1,
            total_points=10,
        )
        self.question2 = Question.objects.create(
            game=self.game,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 2",
            question_number=2,
            total_points=5,
        )

    def test_get_game_questions_success(self):
        """Test retrieving questions for a game"""
        url = reverse("quiz:api_game_questions", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("game", response.data)
        self.assertIn("questions", response.data)
        self.assertEqual(len(response.data["questions"]), 2)
        self.assertEqual(response.data["game"]["id"], self.game.id)

        # Verify questions are ordered by question_number
        self.assertEqual(response.data["questions"][0]["question_number"], 1)
        self.assertEqual(response.data["questions"][1]["question_number"], 2)

    def test_get_game_questions_nonexistent_game(self):
        """Test retrieving questions for non-existent game"""
        url = reverse("quiz:api_game_questions", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_get_game_questions_empty_game(self):
        """Test retrieving questions for game with no questions"""
        empty_game = Game.objects.create(name="Empty Game")
        url = reverse("quiz:api_game_questions", args=[empty_game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["questions"]), 0)


class AddTeamToSessionAPITest(TestCase):
    """Test the add_team_to_session API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            max_teams=4,
        )

    def test_add_team_success(self):
        """Test successfully adding a team to a session"""
        url = reverse("quiz:api_add_team", args=[self.session.id])
        data = {"team_name": "Team A"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("team_id", response.data)
        self.assertEqual(response.data["team_name"], "Team A")
        self.assertTrue(SessionTeam.objects.filter(team_name="Team A").exists())

    def test_add_team_duplicate_name(self):
        """Test adding team with duplicate name in same session"""
        SessionTeam.objects.create(session=self.session, team_name="Team A")

        url = reverse("quiz:api_add_team", args=[self.session.id])
        data = {"team_name": "Team A"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertIn("already taken", response.data["error"])

    def test_add_team_session_full(self):
        """Test adding team when session is at max capacity"""
        # Fill the session
        for i in range(self.session.max_teams):
            SessionTeam.objects.create(
                session=self.session, team_name=f"Team {i + 1}"
            )

        url = reverse("quiz:api_add_team", args=[self.session.id])
        data = {"team_name": "Extra Team"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("full", response.data["error"])

    def test_add_team_missing_name(self):
        """Test adding team without team_name"""
        url = reverse("quiz:api_add_team", args=[self.session.id])
        data = {}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.data["error"])


class UpdateSessionStatusAPITest(TestCase):
    """Test the update_session_status API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            status="waiting",
        )

    def test_update_status_to_active(self):
        """Test updating session status to active"""
        url = reverse("quiz:api_update_session_status", args=[self.session.id])
        data = {"status": "active"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "active")
        self.assertIsNotNone(self.session.started_at)

    def test_update_status_to_completed(self):
        """Test updating session status to completed"""
        url = reverse("quiz:api_update_session_status", args=[self.session.id])
        data = {"status": "completed"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "completed")
        self.assertIsNotNone(self.session.completed_at)

    def test_update_current_question_number(self):
        """Test updating current question number"""
        url = reverse("quiz:api_update_session_status", args=[self.session.id])
        data = {"current_question_number": 5}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_question_number, 5)

    def test_update_both_status_and_question(self):
        """Test updating both status and question number"""
        url = reverse("quiz:api_update_session_status", args=[self.session.id])
        data = {"status": "active", "current_question_number": 3}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "active")
        self.assertEqual(self.session.current_question_number, 3)


class SubmitTeamAnswerAPITest(TestCase):
    """Test the submit_team_answer API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
        )
        self.session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123"
        )
        self.team = SessionTeam.objects.create(
            session=self.session, team_name="Team A"
        )

    def test_submit_answer_success(self):
        """Test successfully submitting a team answer"""
        url = reverse("quiz:api_submit_answer")
        data = {
            "team_id": self.team.id,
            "question_id": self.question.id,
            "submitted_answer": "Paris",
            "points_awarded": 10,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("answer_id", response.data)
        self.assertEqual(response.data["points_awarded"], 10)
        self.assertTrue(
            TeamAnswer.objects.filter(
                team=self.team, question=self.question
            ).exists()
        )

    def test_submit_answer_missing_fields(self):
        """Test submitting answer with missing required fields"""
        url = reverse("quiz:api_submit_answer")
        data = {"team_id": self.team.id}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)


class GetSessionInfoAPITest(TestCase):
    """Test the get_session_info API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            status="active",
            current_question_number=2,
        )
        self.team1 = SessionTeam.objects.create(
            session=self.session, team_name="Team A", total_score=50
        )
        self.team2 = SessionTeam.objects.create(
            session=self.session, team_name="Team B", total_score=45
        )

    def test_get_session_info_success(self):
        """Test retrieving session information"""
        url = reverse("quiz:api_session_info", args=[self.session.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_code"], "ABC123")
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(response.data["current_question_number"], 2)
        self.assertEqual(len(response.data["teams"]), 2)

    def test_get_session_info_nonexistent(self):
        """Test retrieving info for non-existent session"""
        url = reverse("quiz:api_session_info", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class FinalizeSessionAPITest(TestCase):
    """Test the finalize_session API endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            status="active",
        )
        self.team1 = SessionTeam.objects.create(
            session=self.session, team_name="Team A"
        )
        self.team2 = SessionTeam.objects.create(
            session=self.session, team_name="Team B"
        )

    def test_finalize_session_success(self):
        """Test successfully finalizing a session"""
        url = reverse("quiz:api_finalize_session", args=[self.session.id])
        data = {
            "teams": [
                {"name": "Team A", "score": 100},
                {"name": "Team B", "score": 95},
            ]
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "completed")
        self.assertIsNotNone(self.session.completed_at)

        # Verify team scores were updated
        self.team1.refresh_from_db()
        self.team2.refresh_from_db()
        self.assertEqual(self.team1.total_score, 100)
        self.assertEqual(self.team2.total_score, 95)

    def test_finalize_session_empty_teams(self):
        """Test finalizing session with empty teams data"""
        url = reverse("quiz:api_finalize_session", args=[self.session.id])
        data = {"teams": []}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "completed")
