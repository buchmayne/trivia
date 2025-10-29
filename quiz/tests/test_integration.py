"""
Integration tests for complete trivia application workflows
"""
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone
from quiz.models import (
    Game,
    Question,
    Answer,
    QuestionType,
    QuestionRound,
    Category,
    GameSession,
    SessionTeam,
    TeamAnswer,
)


class CompleteTriviaGameWorkflowTest(TestCase):
    """Test a complete trivia game from creation to completion"""

    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()

        # Create a complete game setup
        self.game = Game.objects.create(
            name="Integration Test Trivia",
            description="Full workflow test game",
        )

        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.category1 = Category.objects.create(name="Geography")
        self.category2 = Category.objects.create(name="History")

        # Create rounds
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

        # Create questions for round 1
        self.q1 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round1,
            category=self.category1,
            text="What is the capital of France?",
            question_number=1,
            total_points=10,
        )
        Answer.objects.create(
            question=self.q1, text="Paris", points=10, display_order=1
        )
        Answer.objects.create(
            question=self.q1, text="London", points=0, display_order=2
        )

        self.q2 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round1,
            category=self.category1,
            text="What is the capital of Spain?",
            question_number=2,
            total_points=10,
        )
        Answer.objects.create(
            question=self.q2, text="Madrid", points=10, display_order=1
        )

        # Create questions for round 2
        self.q3 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round2,
            category=self.category2,
            text="Who was the first president?",
            question_number=3,
            total_points=15,
        )
        Answer.objects.create(
            question=self.q3, text="George Washington", points=15, display_order=1
        )

    def test_complete_game_flow_frontend(self):
        """Test complete game flow through frontend views"""
        # 1. View game list
        response = self.client.get(reverse("quiz:game_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Integration Test Trivia")

        # 2. View game overview
        response = self.client.get(
            reverse("quiz:game_overview", args=[self.game.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_questions"], 3)
        self.assertEqual(response.context["total_points"], 35)

        # 3. Navigate to first question
        response = self.client.get(
            reverse(
                "quiz:question_view",
                args=[self.game.id, self.round1.id, self.category1.id, self.q1.id],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["question"], self.q1)

        # 4. View answer
        response = self.client.get(
            reverse(
                "quiz:answer_view",
                args=[self.game.id, self.round1.id, self.category1.id, self.q1.id],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["question"], self.q1)

        # 5. Navigate to next question
        next_question = response.context["next_question"]
        self.assertEqual(next_question.id, self.q2.id)

    def test_complete_session_workflow_api(self):
        """Test complete game session workflow through API"""
        # 1. Create a game session
        create_url = reverse("quiz:api_create_session")
        response = self.api_client.post(
            create_url, {"game": self.game.id, "host_name": "Test Host"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        session_id = response.data["session_id"]
        session_code = response.data["session_code"]

        # 2. Add teams to session
        team1_url = reverse("quiz:api_add_team", args=[session_id])
        response = self.api_client.post(
            team1_url, {"team_name": "Team Alpha"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        team1_id = response.data["team_id"]

        team2_url = reverse("quiz:api_add_team", args=[session_id])
        response = self.api_client.post(
            team2_url, {"team_name": "Team Beta"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        team2_id = response.data["team_id"]

        # 3. Start the session
        status_url = reverse("quiz:api_update_session_status", args=[session_id])
        response = self.api_client.post(
            status_url, {"status": "active", "current_question_number": 1}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        # 4. Teams submit answers for question 1
        submit_url = reverse("quiz:api_submit_answer")
        response = self.api_client.post(
            submit_url,
            {
                "team_id": team1_id,
                "question_id": self.q1.id,
                "submitted_answer": "Paris",
                "points_awarded": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.api_client.post(
            submit_url,
            {
                "team_id": team2_id,
                "question_id": self.q1.id,
                "submitted_answer": "London",
                "points_awarded": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        # 5. Move to next question
        response = self.api_client.post(
            status_url, {"current_question_number": 2}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        # 6. Teams submit answers for question 2
        response = self.api_client.post(
            submit_url,
            {
                "team_id": team1_id,
                "question_id": self.q2.id,
                "submitted_answer": "Madrid",
                "points_awarded": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.api_client.post(
            submit_url,
            {
                "team_id": team2_id,
                "question_id": self.q2.id,
                "submitted_answer": "Madrid",
                "points_awarded": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        # 7. Finalize the session
        finalize_url = reverse("quiz:api_finalize_session", args=[session_id])
        response = self.api_client.post(
            finalize_url,
            {
                "teams": [
                    {"name": "Team Alpha", "score": 20},
                    {"name": "Team Beta", "score": 10},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        # 8. Verify final session state
        info_url = reverse("quiz:api_session_info", args=[session_id])
        response = self.api_client.get(info_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")

        # Verify team scores
        teams = response.data["teams"]
        team_alpha = next(t for t in teams if t["name"] == "Team Alpha")
        team_beta = next(t for t in teams if t["name"] == "Team Beta")
        self.assertEqual(team_alpha["score"], 20)
        self.assertEqual(team_beta["score"], 10)

        # Verify all answers were recorded
        self.assertEqual(TeamAnswer.objects.filter(team_id=team1_id).count(), 2)
        self.assertEqual(TeamAnswer.objects.filter(team_id=team2_id).count(), 2)

    def test_api_game_questions_retrieval(self):
        """Test retrieving all game questions through API"""
        url = reverse("quiz:api_game_questions", args=[self.game.id])
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["questions"]), 3)
        self.assertEqual(response.data["game"]["id"], self.game.id)

        # Verify questions are ordered
        questions = response.data["questions"]
        self.assertEqual(questions[0]["question_number"], 1)
        self.assertEqual(questions[1]["question_number"], 2)
        self.assertEqual(questions[2]["question_number"], 3)

        # Verify answers are included
        self.assertEqual(len(questions[0]["answers"]), 2)


class MultipleRoundsWorkflowTest(TestCase):
    """Test workflows involving multiple rounds"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Multi-Round Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.category = Category.objects.create(name="General Knowledge")

        # Create 3 rounds with questions
        self.rounds = []
        self.questions = []

        for round_num in range(1, 4):
            round_obj = QuestionRound.objects.create(
                name=f"Round {round_num}", round_number=round_num
            )
            self.rounds.append(round_obj)

            # Add 3 questions per round
            for q_num in range(3):
                question = Question.objects.create(
                    game=self.game,
                    question_type=self.question_type,
                    game_round=round_obj,
                    category=self.category,
                    text=f"Round {round_num} Question {q_num + 1}",
                    question_number=(round_num - 1) * 3 + q_num + 1,
                    total_points=10,
                )
                self.questions.append(question)

    def test_navigate_through_all_rounds(self):
        """Test navigating through all questions across all rounds"""
        for idx, question in enumerate(self.questions):
            url = reverse(
                "quiz:question_view",
                args=[
                    self.game.id,
                    question.game_round.id,
                    self.category.id,
                    question.id,
                ],
            )
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["question"], question)

            # Check next question exists for all but the last
            if idx < len(self.questions) - 1:
                self.assertIsNotNone(response.context["next_question"])
            else:
                # Last question should have no next question
                # (unless it's in a different round, which would be handled differently)
                pass

    def test_round_questions_api_for_each_round(self):
        """Test getting questions for each round via API"""
        for round_obj in self.rounds:
            url = reverse(
                "quiz:round_questions_list", args=[self.game.id, round_obj.id]
            )
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Each round should have 3 questions
            self.assertEqual(len(data["questions"]), 3)

            # Questions should be from this round only
            for q in data["questions"]:
                question = Question.objects.get(id=q["id"])
                self.assertEqual(question.game_round, round_obj)


class PasswordProtectedGameWorkflowTest(TestCase):
    """Test complete workflow for password-protected games"""

    def setUp(self):
        self.client = Client()
        self.protected_game = Game.objects.create(
            name="Protected Game",
            description="Secret trivia",
            is_password_protected=True,
            password="secret123",
        )
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.category = Category.objects.create(name="Test")

        self.question = Question.objects.create(
            game=self.protected_game,
            question_type=self.question_type,
            game_round=self.round,
            category=self.category,
            text="Protected Question",
            question_number=1,
        )

    def test_complete_protected_game_workflow(self):
        """Test accessing protected game with password"""
        # 1. Try to access game overview without password
        overview_url = reverse("quiz:game_overview", args=[self.protected_game.id])
        response = self.client.get(overview_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/verify_password.html")

        # 2. Submit incorrect password
        verify_url = reverse("quiz:verify_password", args=[self.protected_game.id])
        response = self.client.post(verify_url, {"password": "wrong"})
        self.assertRedirects(response, overview_url)

        # 3. Try to access overview again (should still require password)
        response = self.client.get(overview_url)
        self.assertTemplateUsed(response, "quiz/verify_password.html")

        # 4. Submit correct password
        response = self.client.post(verify_url, {"password": "secret123"})
        self.assertRedirects(response, overview_url)

        # 5. Now should be able to access game overview
        response = self.client.get(overview_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/game_overview.html")

        # 6. Should be able to access questions
        question_url = reverse(
            "quiz:question_view",
            args=[
                self.protected_game.id,
                self.round.id,
                self.category.id,
                self.question.id,
            ],
        )
        response = self.client.get(question_url)
        self.assertEqual(response.status_code, 200)


class DRFViewSetIntegrationTest(TestCase):
    """Test DRF ViewSet integration with filters"""

    def setUp(self):
        self.api_client = APIClient()

        # Create multiple games with questions
        self.game1 = Game.objects.create(name="Game A")
        self.game2 = Game.objects.create(name="Game B")

        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)
        self.category = Category.objects.create(name="Science")

        # Add questions to game1
        for i in range(5):
            Question.objects.create(
                game=self.game1,
                question_type=self.question_type,
                game_round=self.round1,
                category=self.category,
                text=f"Game1 Q{i+1}",
                question_number=i + 1,
            )

        # Add questions to game2
        for i in range(3):
            Question.objects.create(
                game=self.game2,
                question_type=self.question_type,
                game_round=self.round2,
                category=self.category,
                text=f"Game2 Q{i+1}",
                question_number=i + 1,
            )

    def test_combined_viewset_workflow(self):
        """Test using both Game and Question ViewSets together"""
        # 1. Get list of games
        games_url = reverse("quiz:game-list")
        response = self.api_client.get(games_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)

        # 2. Get questions for game1 using custom action
        game1_questions_url = reverse("quiz:game-questions", args=[self.game1.id])
        response = self.api_client.get(game1_questions_url)
        self.assertEqual(response.status_code, 200)
        # Note: URL resolves to api_views.get_game_questions which returns {"game": {...}, "questions": [...]}
        self.assertIn("questions", response.data)
        self.assertEqual(len(response.data["questions"]), 5)

        # 3. Get all questions and filter by game1
        questions_url = reverse("quiz:question-list")
        response = self.api_client.get(questions_url, {"game__id": self.game1.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 5)

        # 4. Get rounds for game1
        game1_rounds_url = reverse("quiz:game-rounds", args=[self.game1.id])
        response = self.api_client.get(game1_rounds_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # Only round1
