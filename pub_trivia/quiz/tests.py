# tests/test_models.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Game, Category, QuestionType, QuestionRound, Question, Answer

class GameModelTest(TestCase):
    def setUp(self):
        self.game = Game.objects.create(
            name="Test Trivia Game",
            description="Test Game Model",
            is_password_protected=True,
            password="testpass123"
        )

    def test_game_creation(self):
        self.assertEqual(self.game.name, "Test Trivia Game")
        self.assertTrue(self.game.is_password_protected)
        self.assertTrue(isinstance(self.game.created_at, timezone.datetime))

    def test_game_str_representation(self):
        self.assertEqual(str(self.game), "Test Trivia Game")

class QuestionModelTest(TestCase):
    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.category = Category.objects.create(name="Test Category")
        self.question_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.game_round = QuestionRound.objects.create(
            name="Round 1",
            round_number=1
        )
        
        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="What is the capital of France?",
            question_type=self.question_type,
            question_number=1,
            total_points=2,
            game_round=self.game_round
        )

    def test_question_creation(self):
        self.assertEqual(self.question.text, "What is the capital of France?")
        self.assertEqual(self.question.total_points, 2)
        self.assertEqual(self.question.question_number, 1)

    def test_unique_question_number_constraint(self):
        # Test that we can't create two questions with same number in same game
        with self.assertRaises(IntegrityError):
            with transaction.atomic():  # We need this to properly catch the database error
                Question.objects.create(
                    game=self.game,
                    text="Another question",
                    question_type=self.question_type,
                    question_number=1  # Same number as existing question
                )

class AnswerModelTest(TestCase):
    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.question = Question.objects.create(
            game=self.game,
            text="What is the capital of France?",
            question_type=self.question_type,
            question_number=1
        )
        self.answer = Answer.objects.create(
            question=self.question,
            text="Paris",
            points=2
        )

    def test_answer_creation(self):
        self.assertEqual(self.answer.text, "Paris")
        self.assertEqual(self.answer.points, 2)

    def test_answer_str_representation(self):
        self.assertEqual(str(self.answer), "Paris")