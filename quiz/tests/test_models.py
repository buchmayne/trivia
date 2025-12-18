"""
Tests for core models (Game, Question, Answer, QuestionRound, Category, QuestionType)
"""

from django.test import TestCase
from django.db import IntegrityError, transaction
from django.utils import timezone
from quiz.models import Game, Category, QuestionType, QuestionRound, Question, Answer


class GameModelTest(TestCase):
    """Test the Game model"""

    def setUp(self):
        self.game = Game.objects.create(
            name="Test Trivia Game",
            description="Test Game Model",
            is_password_protected=True,
            password="testpass123",
        )

    def test_game_creation(self):
        """Test creating a game with all fields"""
        self.assertEqual(self.game.name, "Test Trivia Game")
        self.assertTrue(self.game.is_password_protected)
        self.assertTrue(isinstance(self.game.created_at, timezone.datetime))

    def test_game_str_representation(self):
        """Test string representation of game"""
        self.assertEqual(str(self.game), "Test Trivia Game")

    def test_password_protected_game(self):
        """Test password protected game creation and validation"""
        protected_game = Game.objects.create(
            name="Protected Game", is_password_protected=True, password="secret123"
        )
        self.assertTrue(protected_game.is_password_protected)
        self.assertEqual(protected_game.password, "secret123")

    def test_game_with_categories(self):
        """Test many-to-many relationship with categories"""
        category1 = Category.objects.create(name="Sports")
        category2 = Category.objects.create(name="History")

        self.game.categories.add(category1, category2)
        self.assertEqual(self.game.categories.count(), 2)
        self.assertIn(category1, self.game.categories.all())


class QuestionModelTest(TestCase):
    """Test the Question model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.category = Category.objects.create(name="Test Category")
        self.question_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.game_round = QuestionRound.objects.create(name="Round 1", round_number=1)

        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="What is the capital of France?",
            question_type=self.question_type,
            question_number=1,
            total_points=2,
            game_round=self.game_round,
        )

    def test_question_creation(self):
        """Test creating a question"""
        self.assertEqual(self.question.text, "What is the capital of France?")
        self.assertEqual(self.question.total_points, 2)
        self.assertEqual(self.question.question_number, 1)

    def test_unique_question_number_constraint(self):
        """Test that we can't create two questions with same number in same game"""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Question.objects.create(
                    game=self.game,
                    text="Another question",
                    question_type=self.question_type,
                    question_number=1,  # Same number as existing question
                )

    def test_question_points_default(self):
        """Test the default value for total_points"""
        question = Question.objects.create(
            game=self.game,
            text="Test points?",
            question_type=self.question_type,
            question_number=3,
        )
        self.assertEqual(question.total_points, 1)


class AnswerModelTest(TestCase):
    """Test the Answer model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.question = Question.objects.create(
            game=self.game,
            text="What is the capital of France?",
            question_type=self.question_type,
            question_number=1,
        )
        self.answer = Answer.objects.create(
            question=self.question, text="Paris", points=2
        )
        self.ranking_type = QuestionType.objects.create(name="Ranking")
        self.ranking_question = Question.objects.create(
            game=self.game,
            text="Rank these items",
            question_type=self.ranking_type,
            question_number=2,
        )

    def test_answer_creation(self):
        """Test creating an answer"""
        self.assertEqual(self.answer.text, "Paris")
        self.assertEqual(self.answer.points, 2)

    def test_answer_str_representation(self):
        """Test string representation of answer"""
        self.assertEqual(str(self.answer), "Paris")

    def test_ranking_answer(self):
        """Test creating a ranking-type answer"""
        answer = Answer.objects.create(
            question=self.ranking_question,
            text="First item",
            display_order=1,
            correct_rank=1,
            points=3,
        )
        self.assertEqual(answer.display_order, 1)
        self.assertEqual(answer.correct_rank, 1)
        self.assertEqual(answer.points, 3)


class QuestionRoundTest(TestCase):
    """Test the QuestionRound model"""

    def setUp(self):
        self.round1 = QuestionRound.objects.create(name="First Round", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Second Round", round_number=2)
        self.round3 = QuestionRound.objects.create(name="Final Round", round_number=3)

    def test_round_ordering(self):
        """Test that rounds are ordered by round_number"""
        rounds = QuestionRound.objects.all()
        self.assertEqual(list(rounds), [self.round1, self.round2, self.round3])
