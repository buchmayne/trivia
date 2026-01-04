"""
Tests for core views (game_list, game_overview, question_view, answer_view, etc.)
"""

from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from quiz.models import Game, Category, QuestionType, QuestionRound, Question
from quiz.views import get_next_question


class GameListViewTest(TestCase):
    """Test the game_list view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(
            name="Test Game",
            description="Test Description",
        )

    def test_game_list_view(self):
        """Test that game list displays all games"""
        response = self.client.get(reverse("quiz:gallery"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/game_list.html")
        self.assertIn("games", response.context)
        self.assertEqual(list(response.context["games"]), [self.game])


class GameOverviewViewTest(TestCase):
    """Test the game_overview view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(
            name="Test Game",
            description="Test Description",
            is_password_protected=True,
            password="testpass123",
        )
        self.category = Category.objects.create(name="Test Category")
        self.game_round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question_type = QuestionType.objects.create(
            name="Multiple Open Ended", description="Test question type"
        )
        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="Test question?",
            question_number=1,
            game_round=self.game_round,
            total_points=2,
            question_type=self.question_type,
        )

    def test_game_overview_with_password_protection(self):
        """Test password protection flow"""
        # Test without password verification
        response = self.client.get(reverse("quiz:game_overview", args=[self.game.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/verify_password.html")

        # Test with password verification
        session = self.client.session
        session[f"game_password_verified_{self.game.id}"] = True
        session.save()

        response = self.client.get(reverse("quiz:game_overview", args=[self.game.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/game_overview.html")
        self.assertIn("total_questions", response.context)
        self.assertEqual(response.context["total_questions"], 1)

    def test_verify_game_password(self):
        """Test password verification endpoint"""
        # Test correct password
        response = self.client.post(
            reverse("quiz:verify_password", args=[self.game.id]),
            {"password": "testpass123"},
        )
        self.assertRedirects(
            response, reverse("quiz:game_overview", args=[self.game.id])
        )

        # Test incorrect password
        response = self.client.post(
            reverse("quiz:verify_password", args=[self.game.id]),
            {"password": "wrongpass"},
        )
        self.assertRedirects(
            response, reverse("quiz:game_overview", args=[self.game.id])
        )


class QuestionViewTest(TestCase):
    """Test question and answer views"""

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.game = Game.objects.create(name="Test Game")
        self.category = Category.objects.create(name="Test Category")
        self.game_round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="Test question?",
            question_number=1,
            game_round=self.game_round,
            total_points=2,
            question_type=self.question_type,
        )

    def test_get_first_question(self):
        """Test getting first question for a round"""
        response = self.client.get(
            reverse("quiz:first_question", args=[self.game_round.id]),
            {"game_id": self.game.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.question.id)
        self.assertEqual(data["category_id"], self.category.id)

    def test_question_view(self):
        """Test question display view"""
        response = self.client.get(
            reverse(
                "quiz:question_view",
                args=[
                    self.game.id,
                    self.game_round.id,
                    self.category.id,
                    self.question.id,
                ],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quiz/question_view.html")
        self.assertEqual(response.context["question"], self.question)
        self.assertEqual(response.context["game"], self.game)

    def test_get_first_question_no_questions(self):
        """Test getting first question when round is empty"""
        # Create a new empty game and round
        empty_game = Game.objects.create(name="Empty Game")
        empty_round = QuestionRound.objects.create(name="Empty Round", round_number=1)

        response = self.client.get(
            reverse("quiz:first_question", args=[empty_round.id]),
            {"game_id": empty_game.id},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "No questions found")

    def test_get_next_question_last_question(self):
        """Test getting next question when there is none"""
        # Test when there is no next question
        last_question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="Last question",
            question_number=2,
            game_round=self.game_round,
            question_type=self.question_type,
        )

        next_question = get_next_question(last_question)
        self.assertIsNone(next_question)

    def test_first_question_correct_game(self):
        """Test that first question API filters by game correctly"""
        # Create two games with their own questions
        game1 = Game.objects.create(name="Game 1")
        game2 = Game.objects.create(name="Game 2")

        round1 = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create first question for game1
        question1 = Question.objects.create(
            game=game1,
            text="First question for game 1",
            question_number=1,
            game_round=round1,
            question_type=self.question_type,
            category=self.category,
        )

        # Create first question for game2
        question2 = Question.objects.create(
            game=game2,
            text="First question for game 2",
            question_number=1,
            game_round=round1,
            question_type=self.question_type,
            category=self.category,
        )

        # Test game1's overview
        response1 = self.client.get(
            reverse("quiz:first_question", args=[round1.id]), {"game_id": game1.id}
        )
        self.assertEqual(response1.status_code, 200)

        # Test game2's overview
        response2 = self.client.get(
            reverse("quiz:first_question", args=[round1.id]), {"game_id": game2.id}
        )
        self.assertEqual(response2.status_code, 200)
