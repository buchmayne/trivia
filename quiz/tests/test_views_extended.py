"""
Extended tests for quiz/views.py - Additional edge cases and scenarios
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.db.models import Sum
from quiz.models import (
    Game,
    Question,
    Answer,
    QuestionType,
    QuestionRound,
    Category,
    GameResult,
    PlayerStats,
)


class AnswerViewExtendedTest(TestCase):
    """Extended tests for answer_view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.category = Category.objects.create(name="Test Category")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round,
            text="Test Question",
            question_number=1,
        )

    def test_answer_view_with_multiple_answers(self):
        """Test answer view displays all answers correctly"""
        # Create multiple answers
        Answer.objects.create(
            question=self.question, text="Answer 1", points=5, display_order=1
        )
        Answer.objects.create(
            question=self.question, text="Answer 2", points=3, display_order=2
        )
        Answer.objects.create(
            question=self.question, text="Answer 3", points=2, display_order=3
        )

        url = reverse(
            "quiz:answer_view",
            args=[self.game.id, self.round.id, self.category.id, self.question.id],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["question"], self.question)
        # Answers should be accessible through the question
        self.assertEqual(response.context["question"].answers.count(), 3)

    def test_answer_view_with_ranking_question(self):
        """Test answer view with ranking-type answers"""
        ranking_type = QuestionType.objects.create(name="Ranking")
        ranking_question = Question.objects.create(
            game=self.game,
            category=self.category,
            question_type=ranking_type,
            game_round=self.round,
            text="Rank these items",
            question_number=2,
        )

        # Create ranking answers
        Answer.objects.create(
            question=ranking_question,
            text="First",
            display_order=1,
            correct_rank=1,
            points=3,
        )
        Answer.objects.create(
            question=ranking_question,
            text="Second",
            display_order=2,
            correct_rank=2,
            points=2,
        )

        url = reverse(
            "quiz:answer_view",
            args=[self.game.id, self.round.id, self.category.id, ranking_question.id],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        answers = list(response.context["question"].answers.all())
        self.assertEqual(len(answers), 2)
        # Answers should be ordered by display_order
        self.assertEqual(answers[0].correct_rank, 1)
        self.assertEqual(answers[1].correct_rank, 2)


class GameOverviewExtendedTest(TestCase):
    """Extended tests for game_overview view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")

    def test_game_overview_multiple_rounds_stats(self):
        """Test game overview calculates stats for multiple rounds correctly"""
        # Create multiple rounds with questions
        round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        round2 = QuestionRound.objects.create(name="Round 2", round_number=2)
        round3 = QuestionRound.objects.create(name="Final Round", round_number=3)
        category = Category.objects.create(name="Test Category")

        # Add questions to each round with varying points
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=round1,
            category=category,
            text="Q1",
            question_number=1,
            total_points=10,
        )
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=round1,
            category=category,
            text="Q2",
            question_number=2,
            total_points=15,
        )
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=round2,
            category=category,
            text="Q3",
            question_number=3,
            total_points=20,
        )
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=round3,
            category=category,
            text="Q4",
            question_number=4,
            total_points=25,
        )

        url = reverse("quiz:game_overview", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_questions"], 4)
        self.assertEqual(response.context["total_points"], 70)

        # Check round stats
        rounds_stats = response.context["rounds_stats"]
        self.assertEqual(len(rounds_stats), 3)

        # Round 1 should have 2 questions with 25 points total
        round1_stats = next(r for r in rounds_stats if r["round"].round_number == 1)
        self.assertEqual(round1_stats["question_count"], 2)
        self.assertEqual(round1_stats["total_points"], 25)

    def test_game_overview_empty_game(self):
        """Test game overview for game with no questions"""
        url = reverse("quiz:game_overview", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_questions"], 0)
        self.assertEqual(response.context["total_points"], 0)
        self.assertEqual(len(response.context["rounds_stats"]), 0)

    def test_game_overview_password_protection_session_persistence(self):
        """Test that password verification persists across requests"""
        protected_game = Game.objects.create(
            name="Protected Game", is_password_protected=True, password="secret"
        )

        # First request without verification - should show password page
        url = reverse("quiz:game_overview", args=[protected_game.id])
        response = self.client.get(url)
        self.assertTemplateUsed(response, "quiz/verify_password.html")

        # Verify password
        verify_url = reverse("quiz:verify_password", args=[protected_game.id])
        self.client.post(verify_url, {"password": "secret"})

        # Second request should show overview
        response = self.client.get(url)
        self.assertTemplateUsed(response, "quiz/game_overview.html")


class GetRoundQuestionsExtendedTest(TestCase):
    """Extended tests for get_round_questions view"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.category = Category.objects.create(name="Test Category")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

    def test_get_round_questions_ordered_correctly(self):
        """Test that questions are returned in correct order"""
        # Create questions out of order
        q3 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            category=self.category,
            text="Question 3",
            question_number=3,
        )
        q1 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            category=self.category,
            text="Question 1",
            question_number=1,
        )
        q2 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            category=self.category,
            text="Question 2",
            question_number=2,
        )

        url = reverse("quiz:round_questions_list", args=[self.game.id, self.round.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should be ordered by question_number
        self.assertEqual(data["questions"][0]["question_number"], 1)
        self.assertEqual(data["questions"][1]["question_number"], 2)
        self.assertEqual(data["questions"][2]["question_number"], 3)

    def test_get_round_questions_includes_category(self):
        """Test that response includes category IDs"""
        question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            category=self.category,
            text="Test Question",
            question_number=1,
        )

        url = reverse("quiz:round_questions_list", args=[self.game.id, self.round.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["questions"][0]["category_id"], self.category.id)


class AnalyticsViewExtendedTest(TestCase):
    """Extended tests for analytics_view"""

    def setUp(self):
        self.client = Client()

        # Create sample game results
        GameResult.objects.create(
            game_date="2024-01-01",
            players="Alice, Bob",
            place=1,
            winner=True,
            Round_1=30,
            Round_2=40,
            Final=20,
            Total=90,
            pct_rd1=0.85,
            pct_rd2=0.90,
            pct_final=0.95,
            pct_total=0.88,
            normalized_total=1.0,
            zscore_total=1.5,
        )
        GameResult.objects.create(
            game_date="2024-01-01",
            players="Charlie, Dave",
            place=2,
            winner=False,
            Round_1=25,
            Round_2=35,
            Final=15,
            Total=75,
            pct_rd1=0.70,
            pct_rd2=0.80,
            pct_final=0.75,
            pct_total=0.73,
            normalized_total=0.83,
            zscore_total=-0.5,
        )

        # Create player stats
        PlayerStats.objects.create(
            player="Alice",
            avg_final_place=1.5,
            total_wins=3,
            avg_zscore_total_points=0.8,
            avg_total_points=85.0,
            avg_pct_total_points=0.85,
            avg_normalized_total_points=0.90,
            avg_pct_rd1_points=0.82,
            avg_pct_rd2_points=0.88,
            avg_pct_final_rd_points=0.90,
            games_played=5,
        )
        PlayerStats.objects.create(
            player="Bob",
            avg_final_place=2.5,
            total_wins=1,
            avg_zscore_total_points=0.3,
            avg_total_points=75.0,
            avg_pct_total_points=0.75,
            avg_normalized_total_points=0.80,
            avg_pct_rd1_points=0.72,
            avg_pct_rd2_points=0.78,
            avg_pct_final_rd_points=0.80,
            games_played=3,
        )

    def test_analytics_view_loads(self):
        """Test that analytics view loads successfully"""
        url = reverse("analytics")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("game_results", response.context)
        self.assertIn("player_stats", response.context)

    def test_analytics_filter_by_player(self):
        """Test filtering analytics by player name"""
        url = reverse("analytics")
        response = self.client.get(url, {"player_search": "Alice"})

        self.assertEqual(response.status_code, 200)

        # Should filter both game results and player stats
        game_results = response.context["game_results"]
        player_stats = response.context["player_stats"]

        # All game results should contain "Alice"
        for result in game_results:
            self.assertIn("Alice", result.players)

        # Player stats should only have Alice
        self.assertTrue(all(stat.player == "Alice" for stat in player_stats))

    def test_analytics_filter_multiple_games_only(self):
        """Test filtering to show only players with multiple games"""
        url = reverse("analytics")
        response = self.client.get(url, {"multiple_games": "on"})

        self.assertEqual(response.status_code, 200)

        player_stats = response.context["player_stats"]
        # All players should have more than 1 game
        for stat in player_stats:
            self.assertGreater(stat.games_played, 1)

    def test_analytics_filter_by_game_date(self):
        """Test filtering analytics by specific game date"""
        url = reverse("analytics")
        response = self.client.get(url, {"game_date": "2024-01-01"})

        self.assertEqual(response.status_code, 200)

        game_results = response.context["game_results"]
        # All results should be from the specified date
        for result in game_results:
            self.assertEqual(str(result.game_date), "2024-01-01")

    def test_analytics_percentages_converted(self):
        """Test that percentages are converted to display format"""
        url = reverse("analytics")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        game_results = list(response.context["game_results"])
        player_stats = list(response.context["player_stats"])

        # Percentages should be multiplied by 100 for display
        if game_results:
            self.assertGreater(game_results[0].pct_total, 1.0)

        if player_stats:
            self.assertGreater(player_stats[0].avg_pct_total_points, 1.0)

    def test_analytics_game_dates_list(self):
        """Test that unique game dates are available in context"""
        url = reverse("analytics")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("game_dates", response.context)

        game_dates = list(response.context["game_dates"])
        self.assertGreater(len(game_dates), 0)


class GetNextQuestionNumberAPITest(TestCase):
    """Test the get_next_question_number admin API"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create a staff user for authentication
        from django.contrib.auth.models import User

        self.staff_user = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )

    def test_get_next_question_number_empty_game(self):
        """Test getting next question number for game with no questions"""
        self.client.force_login(self.staff_user)

        url = reverse("quiz:next_question_number", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["next_number"], 1)

    def test_get_next_question_number_sequential(self):
        """Test getting next sequential question number"""
        self.client.force_login(self.staff_user)

        # Create questions 1, 2, 3
        for i in range(1, 4):
            Question.objects.create(
                game=self.game,
                question_type=self.question_type,
                game_round=self.round,
                text=f"Question {i}",
                question_number=i,
            )

        url = reverse("quiz:next_question_number", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["next_number"], 4)

    def test_get_next_question_number_with_gaps(self):
        """Test finding first available number when there are gaps"""
        self.client.force_login(self.staff_user)

        # Create questions 1, 3, 5 (missing 2 and 4)
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 1",
            question_number=1,
        )
        Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="Question 3",
            question_number=3,
        )

        url = reverse("quiz:next_question_number", args=[self.game.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should return 2 (first gap)
        self.assertEqual(data["next_number"], 2)

    def test_get_next_question_number_requires_staff(self):
        """Test that endpoint requires staff authentication"""
        # Create regular (non-staff) user
        from django.contrib.auth.models import User

        regular_user = User.objects.create_user(
            username="regular", password="password", is_staff=False
        )
        self.client.force_login(regular_user)

        url = reverse("quiz:next_question_number", args=[self.game.id])
        response = self.client.get(url)

        # Should redirect to login or return forbidden
        self.assertIn(response.status_code, [302, 403])
