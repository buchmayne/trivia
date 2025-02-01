from django.test import TestCase, RequestFactory, Client
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.urls import reverse
from .models import Game, Category, QuestionType, QuestionRound, Question, Answer
from .views import get_next_question


######################################
######################################
######################################
########### TEST models.py ###########
######################################
######################################
######################################

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
    
    def test_password_protected_game(self):
        # Test password protected game creation and validation
        protected_game = Game.objects.create(
            name="Protected Game",
            is_password_protected=True,
            password="secret123"
        )
        self.assertTrue(protected_game.is_password_protected)
        self.assertEqual(protected_game.password, "secret123")
    
    def test_game_with_categories(self):
        # Test many-to-many relationship with categories
        category1 = Category.objects.create(name="Sports")
        category2 = Category.objects.create(name="History")
        
        self.game.categories.add(category1, category2)
        self.assertEqual(self.game.categories.count(), 2)
        self.assertIn(category1, self.game.categories.all())

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
    
    def test_question_points_default(self):
        # Test the default value for total_points
        question = Question.objects.create(
            game=self.game,
            text="Test points?",
            question_type=self.question_type,
            question_number=3
        )
        self.assertEqual(question.total_points, 1)

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
        self.question_type = QuestionType.objects.create(name="Ranking")
        self.question = Question.objects.create(
            game=self.game,
            text="Rank these items",
            question_type=self.question_type,
            question_number=2
        )

    def test_answer_creation(self):
        self.assertEqual(self.answer.text, "Paris")
        self.assertEqual(self.answer.points, 2)

    def test_answer_str_representation(self):
        self.assertEqual(str(self.answer), "Paris")
    
    def test_ranking_answer(self):
        answer = Answer.objects.create(
            question=self.question,
            text="First item",
            display_order=1,
            correct_rank=1,
            points=3
        )
        self.assertEqual(answer.display_order, 1)
        self.assertEqual(answer.correct_rank, 1)
        self.assertEqual(answer.points, 3)

    def test_answer_with_explanation(self):
        answer = Answer.objects.create(
            question=self.question,
            text="Test answer",
            explanation="This is why this answer is correct",
            points=2
        )
        self.assertEqual(answer.explanation, "This is why this answer is correct")

class QuestionRoundTest(TestCase):
    def setUp(self):
        self.round1 = QuestionRound.objects.create(
            name="First Round",
            round_number=1
        )
        self.round2 = QuestionRound.objects.create(
            name="Second Round",
            round_number=2
        )
        self.round3 = QuestionRound.objects.create(
            name="Final Round",
            round_number=3
        )

    def test_round_ordering(self):
        rounds = QuestionRound.objects.all()
        self.assertEqual(list(rounds), [self.round1, self.round2, self.round3])


######################################
######################################
######################################
########### TEST views.py ############
######################################
######################################
######################################

class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        
        # Create base test data
        self.game = Game.objects.create(
            name="Test Game",
            description="Test Description",
            is_password_protected=True,
            password="testpass123"
        )
        
        self.category = Category.objects.create(name="Test Category")
        self.game_round = QuestionRound.objects.create(
            name="Round 1",
            round_number=1
        )
        
        # Add this line to create a QuestionType
        self.question_type = QuestionType.objects.create(
            name="Multiple Open Ended",
            description="Test question type"
        )
        
        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="Test question?",
            question_number=1,
            game_round=self.game_round,
            total_points=2,
            question_type=self.question_type
        )

    def test_game_list_view(self):
        response = self.client.get(reverse('quiz:game_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/game_list.html')
        self.assertIn('games', response.context)
        self.assertEqual(list(response.context['games']), [self.game])

    def test_game_overview_with_password_protection(self):
        # Test without password verification
        response = self.client.get(reverse('quiz:game_overview', args=[self.game.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/verify_password.html')

        # Test with password verification
        session = self.client.session
        session[f'game_password_verified_{self.game.id}'] = True
        session.save()
        
        response = self.client.get(reverse('quiz:game_overview', args=[self.game.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/game_overview.html')
        self.assertIn('total_questions', response.context)
        self.assertEqual(response.context['total_questions'], 1)

    def test_verify_game_password(self):
        # Test correct password
        response = self.client.post(
            reverse('quiz:verify_password', args=[self.game.id]),
            {'password': 'testpass123'}
        )
        self.assertRedirects(response, reverse('quiz:game_overview', args=[self.game.id]))
        
        # Test incorrect password
        response = self.client.post(
            reverse('quiz:verify_password', args=[self.game.id]),
            {'password': 'wrongpass'}
        )
        self.assertRedirects(response, reverse('quiz:game_overview', args=[self.game.id]))

    def test_get_first_question(self):
        response = self.client.get(
            reverse('quiz:first_question', args=[self.game_round.id]),
            {'game_id': self.game.id}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.question.id)
        self.assertEqual(data['category_id'], self.category.id)

    def test_question_view(self):
        response = self.client.get(
            reverse('quiz:question_view', args=[
                self.game.id,
                self.game_round.id,
                self.category.id,
                self.question.id
            ])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/question_view.html')
        self.assertEqual(response.context['question'], self.question)
        self.assertEqual(response.context['game'], self.game)
    
    def test_get_first_question_no_questions(self):
        # Create a new empty game and round
        empty_game = Game.objects.create(name="Empty Game")
        empty_round = QuestionRound.objects.create(name="Empty Round", round_number=1)
        
        response = self.client.get(
            reverse('quiz:first_question', args=[empty_round.id]),
            {'game_id': empty_game.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'No questions found')

    def test_get_next_question_last_question(self):
        # Test when there is no next question
        last_question = Question.objects.create(
            game=self.game,
            category=self.category,
            text="Last question",
            question_number=2,
            game_round=self.game_round,
            question_type=self.question_type
        )
        
        next_question = get_next_question(last_question)
        self.assertIsNone(next_question)
    
    def test_first_question_correct_game(self):
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
            category=self.category
        )
        
        # Create first question for game2
        question2 = Question.objects.create(
            game=game2,
            text="First question for game 2",
            question_number=1,
            game_round=round1,
            question_type=self.question_type,
            category=self.category
        )
        
        # Test game1's overview
        response1 = self.client.get(reverse('quiz:first_question', args=[round1.id]), {'game_id': game1.id})
        self.assertEqual(response1.status_code, 200)
        
        # Test game2's overview
        response2 = self.client.get(reverse('quiz:first_question', args=[round1.id]), {'game_id': game2.id})
        self.assertEqual(response2.status_code, 200)