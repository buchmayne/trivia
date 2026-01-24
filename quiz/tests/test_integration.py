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
        response = self.client.get(reverse("quiz:gallery"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Integration Test Trivia")

        # 2. View game overview
        response = self.client.get(reverse("quiz:game_overview", args=[self.game.id]))
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
        import json

        # 1. Create a game session
        create_url = reverse("quiz:session_create")
        response = self.client.post(
            create_url,
            json.dumps({"game_id": self.game.id, "admin_name": "Test Host"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        session_code = data["code"]
        admin_token = data["admin_token"]

        # 2. Add teams to session
        team1_url = reverse("quiz:session_join", args=[session_code])
        response = self.client.post(
            team1_url,
            json.dumps({"team_name": "Team Alpha"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        team1_data = response.json()
        team1_id = team1_data["team_id"]
        team1_token = team1_data["team_token"]

        team2_url = reverse("quiz:session_join", args=[session_code])
        response = self.client.post(
            team2_url,
            json.dumps({"team_name": "Team Beta"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        team2_data = response.json()
        team2_id = team2_data["team_id"]
        team2_token = team2_data["team_token"]

        # 3. Start the session (as admin)
        start_url = reverse("quiz:session_admin_start", args=[session_code])
        response = self.client.post(
            start_url,
            json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )
        self.assertEqual(response.status_code, 200)

        # 4. Teams submit answers for question 1
        submit_url = reverse("quiz:session_team_answer", args=[session_code])
        response = self.client.post(
            submit_url,
            json.dumps({"question_id": self.q1.id, "answer_text": "Paris"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {team1_token}",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            submit_url,
            json.dumps({"question_id": self.q1.id, "answer_text": "London"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {team2_token}",
        )
        self.assertEqual(response.status_code, 200)

        # 5. Verify session state
        state_url = reverse("quiz:session_state", args=[session_code])
        response = self.client.get(state_url)
        self.assertEqual(response.status_code, 200)
        state_data = response.json()
        self.assertEqual(state_data["status"], "playing")
        self.assertEqual(state_data["team_count"], 2)

    def test_api_game_questions_retrieval(self):
        """Test retrieving all game questions through API"""
        url = reverse("quiz:api_game_questions", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["questions"]), 3)
        self.assertEqual(data["game"]["id"], self.game.id)

        # Verify questions are ordered
        questions = data["questions"]
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
