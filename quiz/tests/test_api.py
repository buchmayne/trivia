"""
Tests for quiz/api.py - Django REST Framework ViewSets
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from quiz.models import Game, Question, QuestionType, QuestionRound, Category, Answer


class GameViewSetTest(TestCase):
    """Test the GameViewSet"""

    def setUp(self):
        self.client = APIClient()
        self.game1 = Game.objects.create(
            name="Trivia Night 1", description="First trivia game"
        )
        self.game2 = Game.objects.create(
            name="Trivia Night 2", description="Second trivia game"
        )
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.category = Category.objects.create(name="Geography")

    def test_list_games(self):
        """Test retrieving list of all games"""
        url = reverse("quiz:game-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_game_detail(self):
        """Test retrieving a specific game"""
        url = reverse("quiz:game-detail", args=[self.game1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Trivia Night 1")
        self.assertEqual(response.data["description"], "First trivia game")

    def test_game_questions_action(self):
        """Test the custom questions action on GameViewSet"""
        # Create some questions for the game
        question1 = Question.objects.create(
            game=self.game1,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 1",
            question_number=1,
        )
        question2 = Question.objects.create(
            game=self.game1,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 2",
            question_number=2,
        )

        url = reverse("quiz:game-questions", args=[self.game1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The get_game_questions endpoint returns {"game": {...}, "questions": [...]}
        self.assertIn("questions", response.data)
        self.assertEqual(len(response.data["questions"]), 2)
        self.assertEqual(response.data["questions"][0]["question_number"], 1)
        self.assertEqual(response.data["questions"][1]["question_number"], 2)

    def test_game_rounds_action(self):
        """Test the custom rounds action on GameViewSet"""
        # Create questions in different rounds
        round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

        Question.objects.create(
            game=self.game1,
            question_type=self.question_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
        )
        Question.objects.create(
            game=self.game1,
            question_type=self.question_type,
            game_round=round2,
            text="Q2",
            question_number=2,
        )

        url = reverse("quiz:game-rounds", args=[self.game1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ViewSet action returns a list directly
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["round_number"], 1)
        self.assertEqual(response.data[1]["round_number"], 2)

    def test_game_questions_empty(self):
        """Test questions action for game with no questions"""
        url = reverse("quiz:game-questions", args=[self.game2.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The get_game_questions endpoint returns {"game": {...}, "questions": [...]}
        self.assertIn("questions", response.data)
        self.assertEqual(len(response.data["questions"]), 0)

    def test_game_viewset_readonly(self):
        """Test that GameViewSet is read-only"""
        url = reverse("quiz:game-list")

        # Try to create a game (should fail)
        data = {"name": "New Game", "description": "Test"}
        response = self.client.post(url, data, format="json")

        # Should return 403 Forbidden or 405 Method Not Allowed
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
        )

    def test_retrieve_nonexistent_game(self):
        """Test retrieving a game that doesn't exist"""
        url = reverse("quiz:game-detail", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class QuestionViewSetTest(TestCase):
    """Test the QuestionViewSet"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)
        self.category = Category.objects.create(name="Science")

        # Create test questions
        self.question1 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round1,
            category=self.category,
            text="What is H2O?",
            question_number=1,
        )
        self.question2 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round2,
            category=self.category,
            text="What is CO2?",
            question_number=2,
        )

    def test_list_questions(self):
        """Test retrieving list of all questions"""
        url = reverse("quiz:question-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_question_detail(self):
        """Test retrieving a specific question"""
        url = reverse("quiz:question-detail", args=[self.question1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["text"], "What is H2O?")
        self.assertEqual(response.data["question_number"], 1)

    def test_filter_by_game_id(self):
        """Test filtering questions by game ID"""
        # Create another game with questions
        game2 = Game.objects.create(name="Another Game")
        Question.objects.create(
            game=game2,
            question_type=self.question_type,
            game_round=self.round1,
            text="Other game question",
            question_number=1,
        )

        url = reverse("quiz:question-list")
        response = self.client.get(url, {"game__id": self.game.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return questions from the specified game
        self.assertEqual(len(response.data["results"]), 2)
        question_ids = [q["id"] for q in response.data["results"]]
        self.assertIn(self.question1.id, question_ids)
        self.assertIn(self.question2.id, question_ids)

    def test_filter_by_game_name(self):
        """Test filtering questions by game name"""
        url = reverse("quiz:question-list")
        response = self.client.get(url, {"game__name": "Test Game"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["results"]), 0)

    def test_filter_by_round_id(self):
        """Test filtering questions by round ID"""
        url = reverse("quiz:question-list")
        response = self.client.get(url, {"game_round__id": self.round1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return questions from round 1
        for question in response.data["results"]:
            # Need to check if this is question1 which is in round1
            if question["id"] == self.question1.id:
                self.assertEqual(question["question_number"], 1)

    def test_filter_by_round_name(self):
        """Test filtering questions by round name"""
        url = reverse("quiz:question-list")
        response = self.client.get(url, {"game_round__name": "Round 1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["results"]), 0)

    def test_filter_by_category_name(self):
        """Test filtering questions by category name"""
        url = reverse("quiz:question-list")
        response = self.client.get(url, {"category__name": "Science"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_filter_by_question_number(self):
        """Test filtering questions by question number"""
        url = reverse("quiz:question-list")
        response = self.client.get(url, {"question_number": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["question_number"], 1)

    def test_question_includes_answers(self):
        """Test that question detail includes answers"""
        # Add some answers to the question
        Answer.objects.create(
            question=self.question1, text="Water", points=10, display_order=1
        )
        Answer.objects.create(
            question=self.question1, text="Hydrogen Dioxide", points=0, display_order=2
        )

        url = reverse("quiz:question-detail", args=[self.question1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("answers", response.data)
        self.assertEqual(len(response.data["answers"]), 2)

    def test_question_viewset_readonly(self):
        """Test that QuestionViewSet is read-only"""
        url = reverse("quiz:question-list")

        # Try to create a question (should fail)
        data = {"text": "New Question", "question_number": 99}
        response = self.client.post(url, data, format="json")

        # Should return 403 Forbidden or 405 Method Not Allowed
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
        )

    def test_multiple_filters_combined(self):
        """Test using multiple filters together"""
        url = reverse("quiz:question-list")
        response = self.client.get(
            url,
            {
                "game__id": self.game.id,
                "game_round__id": self.round1.id,
                "category__name": "Science",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only question1
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.question1.id)

    def test_retrieve_nonexistent_question(self):
        """Test retrieving a question that doesn't exist"""
        url = reverse("quiz:question-detail", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ViewSetPaginationTest(TestCase):
    """Test pagination in ViewSets"""

    def setUp(self):
        self.client = APIClient()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create many questions to test pagination
        for i in range(25):
            Question.objects.create(
                game=self.game,
                question_type=self.question_type,
                game_round=self.round,
                text=f"Question {i+1}",
                question_number=i + 1,
            )

    def test_question_list_pagination(self):
        """Test that questions are paginated"""
        url = reverse("quiz:question-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Default page size is 20 (from settings)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("next", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 25)

    def test_pagination_next_page(self):
        """Test retrieving the next page of results"""
        url = reverse("quiz:question-list")
        response = self.client.get(url)

        # Get the next page URL
        next_url = response.data["next"]
        self.assertIsNotNone(next_url)

        # Request the next page
        response2 = self.client.get(next_url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response2.data["results"]), 5)  # Remaining 5 questions
