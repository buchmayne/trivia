"""
Tests for session API endpoints
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from quiz.models import (
    Answer,
    Game,
    Question,
    QuestionType,
    QuestionRound,
    GameSession,
    SessionTeam,
    SessionRound,
    TeamAnswer,
)


class CreateSessionAPITest(TestCase):
    """Test the create_session endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.url = reverse("quiz:session_create")

    def test_create_session_success(self):
        """Test successfully creating a session"""
        data = {"game_id": self.game.id, "admin_name": "John Doe", "max_teams": 10}

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        self.assertIn("code", response_data)
        self.assertIn("admin_token", response_data)
        self.assertEqual(response_data["game_name"], "Test Game")
        self.assertEqual(response_data["game_id"], self.game.id)

        # Verify session was created
        session = GameSession.objects.get(code=response_data["code"])
        self.assertEqual(session.admin_name, "John Doe")
        self.assertEqual(session.max_teams, 10)

    def test_create_session_missing_fields(self):
        """Test creating session with missing required fields"""
        data = {"admin_name": "John Doe"}

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_session_creates_session_rounds(self):
        """Test that SessionRounds are created for each game round"""
        round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

        q_type = QuestionType.objects.create(name="Multiple Choice")
        Question.objects.create(
            game=self.game,
            question_type=q_type,
            game_round=round1,
            text="Q1",
            question_number=1,
        )
        Question.objects.create(
            game=self.game,
            question_type=q_type,
            game_round=round2,
            text="Q2",
            question_number=2,
        )

        data = {"game_id": self.game.id, "admin_name": "Host"}

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        session = GameSession.objects.get(code=response.json()["code"])
        self.assertEqual(session.session_rounds.count(), 2)


class JoinSessionAPITest(TestCase):
    """Test the join_session endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")

    def test_join_session_success(self):
        """Test successfully joining a session"""
        url = reverse("quiz:session_join", args=[self.session.code])
        data = {"team_name": "Team Alpha"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        self.assertIn("team_token", response_data)
        self.assertEqual(response_data["team_name"], "Team Alpha")
        self.assertFalse(response_data["joined_late"])

        # Verify team was created
        team = SessionTeam.objects.get(session=self.session, name="Team Alpha")
        self.assertIsNotNone(team)

    def test_join_session_duplicate_name(self):
        """Test joining with duplicate team name"""
        SessionTeam.objects.create(session=self.session, name="Team Alpha")

        url = reverse("quiz:session_join", args=[self.session.code])
        data = {"team_name": "Team Alpha"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Team name taken", response.json()["error"])

    def test_join_session_full(self):
        """Test joining when session is full"""
        self.session.max_teams = 2
        self.session.save()

        SessionTeam.objects.create(session=self.session, name="Team 1")
        SessionTeam.objects.create(session=self.session, name="Team 2")

        url = reverse("quiz:session_join", args=[self.session.code])
        data = {"team_name": "Team 3"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Session full", response.json()["error"])

    def test_join_late(self):
        """Test late joining during active game"""
        self.session.status = GameSession.Status.PLAYING
        self.session.save()

        url = reverse("quiz:session_join", args=[self.session.code])
        data = {"team_name": "Late Team"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["joined_late"])

    def test_join_completed_game(self):
        """Test cannot join completed game"""
        self.session.status = GameSession.Status.COMPLETED
        self.session.save()

        url = reverse("quiz:session_join", args=[self.session.code])
        data = {"team_name": "Team"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)


class GetSessionStateAPITest(TestCase):
    """Test the get_session_state endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")

    def test_get_session_state(self):
        """Test getting session state"""
        team1 = SessionTeam.objects.create(
            session=self.session, name="Team A", score=50
        )
        team2 = SessionTeam.objects.create(
            session=self.session, name="Team B", score=30
        )

        url = reverse("quiz:session_state", args=[self.session.code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "lobby")
        self.assertEqual(data["game_name"], "Test Game")
        self.assertEqual(data["admin_name"], "Host")
        self.assertEqual(data["team_count"], 2)
        self.assertEqual(len(data["teams"]), 2)

    def test_get_session_state_with_full_question_data(self):
        """Test that session state includes full question data with answer bank, videos, and sub-questions"""
        from quiz.models import Category, Answer

        # Create question with all components
        round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        q_type = QuestionType.objects.create(name="Ranking")
        category = Category.objects.create(name="Test Category")

        question = Question.objects.create(
            game=self.game,
            question_type=q_type,
            game_round=round1,
            text="Test Question",
            question_number=1,
            total_points=10,
            answer_bank="<p>These are the answer bank items</p>",
            question_image_url="https://example.com/image.jpg",
            question_video_url="https://example.com/video.mp4",
            category=category,
        )

        # Create sub-questions (answers)
        answer1 = Answer.objects.create(
            question=question,
            text="Sub-question 1",
            answer_text="Correct answer 1",
            display_order=1,
            points=5,
            question_image_url="https://example.com/sub1.jpg",
        )
        answer2 = Answer.objects.create(
            question=question,
            text="Sub-question 2",
            answer_text="Correct answer 2",
            display_order=2,
            points=5,
            question_video_url="https://example.com/sub2.mp4",
        )

        # Set session to playing with this question
        self.session.status = GameSession.Status.PLAYING
        self.session.current_question = question
        self.session.current_round = round1
        self.session.save()

        SessionRound.objects.create(
            session=self.session, round=round1, status=SessionRound.Status.ACTIVE
        )

        # Get session state
        url = reverse("quiz:session_state", args=[self.session.code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify current_question has all required fields
        current_q = data["current_question"]
        self.assertEqual(current_q["id"], question.id)
        self.assertEqual(current_q["number"], 1)
        self.assertEqual(current_q["text"], "Test Question")
        self.assertEqual(current_q["total_points"], 10)
        # CloudFrontURLField prepends CloudFront domain to URLs
        self.assertIn("https://example.com/image.jpg", current_q["image_url"])
        self.assertIn("https://example.com/video.mp4", current_q["video_url"])
        self.assertEqual(
            current_q["answer_bank"], "<p>These are the answer bank items</p>"
        )
        self.assertEqual(current_q["question_type"], "Ranking")

        # Verify answers (sub-questions) are included
        self.assertEqual(len(current_q["answers"]), 2)

        # Check first answer
        ans1 = current_q["answers"][0]
        self.assertEqual(ans1["id"], answer1.id)
        self.assertEqual(ans1["text"], "Sub-question 1")
        self.assertEqual(ans1["answer_text"], "Correct answer 1")
        self.assertEqual(ans1["display_order"], 1)
        self.assertEqual(ans1["points"], 5)
        # CloudFrontURLField prepends CloudFront domain to URLs
        self.assertIn("https://example.com/sub1.jpg", ans1["image_url"])
        self.assertIsNone(ans1["video_url"])

        # Check second answer
        ans2 = current_q["answers"][1]
        self.assertEqual(ans2["id"], answer2.id)
        self.assertEqual(ans2["text"], "Sub-question 2")
        self.assertEqual(ans2["display_order"], 2)
        # CloudFrontURLField prepends CloudFront domain to URLs
        self.assertIn("https://example.com/sub2.mp4", ans2["video_url"])
        self.assertIsNone(ans2["image_url"])


class AdminStartGameAPITest(TestCase):
    """Test the admin_start_game endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.q_type = QuestionType.objects.create(name="Multiple Choice")
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
        )
        SessionRound.objects.create(session=self.session, round=self.round)
        SessionTeam.objects.create(session=self.session, name="Team A")

    def test_start_game_success(self):
        """Test successfully starting a game"""
        url = reverse("quiz:session_admin_start", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.PLAYING)
        self.assertIsNotNone(self.session.started_at)
        self.assertIsNotNone(self.session.current_question)

    def test_start_game_no_token(self):
        """Test starting game without admin token"""
        url = reverse("quiz:session_admin_start", args=[self.session.code])

        response = self.client.post(url, content_type="application/json")

        self.assertEqual(response.status_code, 403)

    def test_start_game_invalid_token(self):
        """Test starting game with invalid token"""
        url = reverse("quiz:session_admin_start", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(response.status_code, 403)

    def test_start_game_no_teams(self):
        """Test starting game with no teams"""
        SessionTeam.objects.all().delete()

        url = reverse("quiz:session_admin_start", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 400)


class AdminLockRoundAPITest(TestCase):
    """Test the admin_lock_round endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.PLAYING
        )
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.q_type = QuestionType.objects.create(name="Multiple Choice")
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
        )
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round, status=SessionRound.Status.ACTIVE
        )
        self.session.current_round = self.round
        self.session.save()

        self.team = SessionTeam.objects.create(session=self.session, name="Team A")
        self.answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="Answer",
        )

    def test_lock_round_success(self):
        """Test successfully locking a round"""
        url = reverse("quiz:session_admin_lock", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        self.session_round.refresh_from_db()
        self.assertEqual(self.session_round.status, SessionRound.Status.LOCKED)

        self.answer.refresh_from_db()
        self.assertTrue(self.answer.is_locked)

    def test_lock_round_auto_scores_unanswered_questions(self):
        """Test that locking a round auto-creates TeamAnswer objects with 0 points for unanswered questions"""
        # Create a second question that the team hasn't answered
        question2 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q2",
            question_number=2,
        )

        # Create a second team that hasn't answered any questions
        team2 = SessionTeam.objects.create(session=self.session, name="Team B")

        url = reverse("quiz:session_admin_lock", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        # Verify that Team A's unanswered question (Q2) was auto-scored as 0
        team_a_q2_answer = TeamAnswer.objects.get(team=self.team, question=question2)
        self.assertEqual(team_a_q2_answer.answer_text, "")
        self.assertEqual(team_a_q2_answer.points_awarded, 0)
        self.assertTrue(team_a_q2_answer.is_locked)
        self.assertIsNotNone(team_a_q2_answer.scored_at)

        # Verify that Team B's unanswered questions (Q1 and Q2) were auto-scored as 0
        team_b_q1_answer = TeamAnswer.objects.get(team=team2, question=self.question)
        self.assertEqual(team_b_q1_answer.answer_text, "")
        self.assertEqual(team_b_q1_answer.points_awarded, 0)
        self.assertTrue(team_b_q1_answer.is_locked)
        self.assertIsNotNone(team_b_q1_answer.scored_at)

        team_b_q2_answer = TeamAnswer.objects.get(team=team2, question=question2)
        self.assertEqual(team_b_q2_answer.answer_text, "")
        self.assertEqual(team_b_q2_answer.points_awarded, 0)
        self.assertTrue(team_b_q2_answer.is_locked)
        self.assertIsNotNone(team_b_q2_answer.scored_at)


class AdminCompleteRoundAPITest(TestCase):
    """Test the admin_complete_round endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.SCORING
        )
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.q_type = QuestionType.objects.create(name="Multiple Choice")
        self.question1 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
            total_points=10,
        )
        self.question2 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q2",
            question_number=2,
            total_points=5,
        )
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round, status=SessionRound.Status.LOCKED
        )
        self.session.current_round = self.round
        self.session.save()

        self.team = SessionTeam.objects.create(session=self.session, name="Team A")

    def test_complete_round_success_with_auto_scored_answers(self):
        """Test completing a round where some answers were auto-scored as 0"""
        # Team answered Q1 and got points
        answer1 = TeamAnswer.objects.create(
            team=self.team,
            question=self.question1,
            session_round=self.session_round,
            answer_text="My answer",
            is_locked=True,
            points_awarded=10,
            scored_at=timezone.now(),
        )

        # Q2 was auto-scored as 0 (team didn't answer)
        answer2 = TeamAnswer.objects.create(
            team=self.team,
            question=self.question2,
            session_round=self.session_round,
            answer_text="",
            is_locked=True,
            points_awarded=0,
            scored_at=timezone.now(),
        )

        url = reverse("quiz:session_admin_complete", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        self.session_round.refresh_from_db()
        self.assertEqual(self.session_round.status, SessionRound.Status.SCORED)
        self.assertIsNotNone(self.session_round.scored_at)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.REVIEWING)

    def test_complete_round_fails_if_answers_not_scored(self):
        """Test that completing a round fails if not all answers are scored"""
        # Create an answer that hasn't been scored yet
        TeamAnswer.objects.create(
            team=self.team,
            question=self.question1,
            session_round=self.session_round,
            answer_text="My answer",
            is_locked=True,
            # points_awarded is None (not scored)
        )

        url = reverse("quiz:session_admin_complete", args=[self.session.code])

        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("answers still need scoring", response.json()["error"])


class AdminScoreAnswerAPITest(TestCase):
    """Test the admin_score_answer endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.SCORING
        )
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.q_type = QuestionType.objects.create(name="Multiple Choice")
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
            total_points=10,
        )
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round, status=SessionRound.Status.LOCKED
        )
        self.team = SessionTeam.objects.create(session=self.session, name="Team A")
        self.answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="Answer",
            is_locked=True,
        )

    def test_score_answer_success(self):
        """Test successfully scoring an answer"""
        url = reverse("quiz:session_admin_score", args=[self.session.code])
        data = {"answer_id": self.answer.id, "points": 10}

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        self.answer.refresh_from_db()
        self.assertEqual(self.answer.points_awarded, 10)
        self.assertIsNotNone(self.answer.scored_at)

        self.team.refresh_from_db()
        self.assertEqual(self.team.score, 10)

    def test_score_answer_partial_credit(self):
        """Test awarding partial credit"""
        url = reverse("quiz:session_admin_score", args=[self.session.code])
        data = {"answer_id": self.answer.id, "points": 5}  # Half credit

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        self.answer.refresh_from_db()
        self.assertEqual(self.answer.points_awarded, 5)

    def test_score_answer_exceeds_max(self):
        """Test cannot award more than max points"""
        url = reverse("quiz:session_admin_score", args=[self.session.code])
        data = {
            "answer_id": self.answer.id,
            "points": 15,  # More than total_points (10)
        }

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 400)


class TeamSubmitAnswerAPITest(TestCase):
    """Test the team_submit_answer endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.PLAYING
        )
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.q_type = QuestionType.objects.create(name="Multiple Choice")
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round,
            text="Q1",
            question_number=1,
        )
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round, status=SessionRound.Status.ACTIVE
        )
        self.team = SessionTeam.objects.create(session=self.session, name="Team A")

    def test_submit_answer_success(self):
        """Test successfully submitting an answer"""
        url = reverse("quiz:session_team_answer", args=[self.session.code])
        data = {"question_id": self.question.id, "answer_text": "My answer"}

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.team.token}",
        )

        self.assertEqual(response.status_code, 200)

        answer = TeamAnswer.objects.get(team=self.team, question=self.question)
        self.assertEqual(answer.answer_text, "My answer")

    def test_update_answer(self):
        """Test updating an existing answer"""
        TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="First answer",
        )

        url = reverse("quiz:session_team_answer", args=[self.session.code])
        data = {"question_id": self.question.id, "answer_text": "Updated answer"}

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.team.token}",
        )

        self.assertEqual(response.status_code, 200)

        answer = TeamAnswer.objects.get(team=self.team, question=self.question)
        self.assertEqual(answer.answer_text, "Updated answer")

    def test_submit_locked_answer(self):
        """Test cannot update locked answer"""
        TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="Answer",
            is_locked=True,
        )

        url = reverse("quiz:session_team_answer", args=[self.session.code])
        data = {"question_id": self.question.id, "answer_text": "New answer"}

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.team.token}",
        )

        self.assertEqual(response.status_code, 400)

    def test_submit_answer_no_token(self):
        """Test submitting answer without team token"""
        url = reverse("quiz:session_team_answer", args=[self.session.code])
        data = {"question_id": self.question.id, "answer_text": "Answer"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)


class TeamGetResultsAPITest(TestCase):
    """Test the team_get_results endpoint"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.team1 = SessionTeam.objects.create(
            session=self.session, name="Team A", score=100
        )
        self.team2 = SessionTeam.objects.create(
            session=self.session, name="Team B", score=80
        )

    def test_get_results(self):
        """Test getting team results"""
        url = reverse("quiz:session_team_results", args=[self.session.code])

        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {self.team1.token}")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["team_name"], "Team A")
        self.assertEqual(data["total_score"], 100)
        self.assertEqual(data["rank"], 1)
        self.assertEqual(data["total_teams"], 2)
        self.assertEqual(len(data["standings"]), 2)


class PerPartScoringTest(TestCase):
    """Tests for per-part scoring of multi-part questions"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.PLAYING
        )
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create different question types
        self.ranking_type = QuestionType.objects.create(name="Ranking")
        self.matching_type = QuestionType.objects.create(name="Matching")
        self.open_ended_type = QuestionType.objects.create(name="Multiple Open Ended")
        self.single_type = QuestionType.objects.create(name="Multiple Choice")

        # Create a Ranking question with 3 parts
        self.ranking_question = Question.objects.create(
            game=self.game,
            question_type=self.ranking_type,
            game_round=self.round,
            text="Rank these in order",
            question_number=1,
            total_points=6,
        )
        # Create answers (parts) for ranking question
        # display_order represents the shuffled/displayed order
        # correct_rank represents the correct ranking position
        self.ranking_answers = [
            Answer.objects.create(
                question=self.ranking_question,
                text="Item A",
                display_order=0,
                correct_rank=1,
                points=2,
            ),
            Answer.objects.create(
                question=self.ranking_question,
                text="Item B",
                display_order=1,
                correct_rank=2,
                points=2,
            ),
            Answer.objects.create(
                question=self.ranking_question,
                text="Item C",
                display_order=2,
                correct_rank=3,
                points=2,
            ),
        ]

        # Create a Matching question with 2 parts
        self.matching_question = Question.objects.create(
            game=self.game,
            question_type=self.matching_type,
            game_round=self.round,
            text="Match the items",
            question_number=2,
            total_points=4,
        )
        self.matching_answers = [
            Answer.objects.create(
                question=self.matching_question,
                text="Country A",
                answer_text="Capital A",
                display_order=1,
                points=2,
            ),
            Answer.objects.create(
                question=self.matching_question,
                text="Country B",
                answer_text="Capital B",
                display_order=2,
                points=2,
            ),
        ]

        # Create a Multiple Open Ended question with 2 parts
        self.open_ended_question = Question.objects.create(
            game=self.game,
            question_type=self.open_ended_type,
            game_round=self.round,
            text="Answer these questions",
            question_number=3,
            total_points=5,
        )
        self.open_ended_answers = [
            Answer.objects.create(
                question=self.open_ended_question,
                text="Part A question",
                answer_text="Part A answer",
                display_order=1,
                points=2,
            ),
            Answer.objects.create(
                question=self.open_ended_question,
                text="Part B question",
                answer_text="Part B answer",
                display_order=2,
                points=3,
            ),
        ]

        # Create a single-answer question
        self.single_question = Question.objects.create(
            game=self.game,
            question_type=self.single_type,
            game_round=self.round,
            text="Single answer question",
            question_number=4,
            total_points=5,
        )

        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round, status=SessionRound.Status.ACTIVE
        )
        self.session.current_round = self.round
        self.session.save()

        self.team = SessionTeam.objects.create(session=self.session, name="Team A")

    def test_lock_round_splits_ranking_answers_into_parts(self):
        """Test that locking splits ranking question answers into per-part records"""
        # Team submits ranking answer as JSON array [0, 1, 2] (correct order)
        TeamAnswer.objects.create(
            team=self.team,
            question=self.ranking_question,
            session_round=self.session_round,
            answer_text="[0, 1, 2]",
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        # Check that per-part TeamAnswer records were created
        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.ranking_question,
            answer_part__isnull=False,
        )
        self.assertEqual(part_answers.count(), 3)

        # Check original combined answer was deleted
        original = TeamAnswer.objects.filter(
            team=self.team,
            question=self.ranking_question,
            answer_part__isnull=True,
        )
        self.assertEqual(original.count(), 0)

    def test_lock_round_auto_scores_ranking_question(self):
        """Test that ranking questions are auto-scored on lock"""
        # Team submits correct ranking [0, 1, 2]
        TeamAnswer.objects.create(
            team=self.team,
            question=self.ranking_question,
            session_round=self.session_round,
            answer_text="[0, 1, 2]",
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Check each part was scored correctly (all correct = full points)
        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.ranking_question,
            answer_part__isnull=False,
        ).order_by("answer_part__display_order")

        total_points = sum(a.points_awarded for a in part_answers)
        self.assertEqual(total_points, 6)  # All correct

        for part_answer in part_answers:
            self.assertIsNotNone(part_answer.scored_at)
            self.assertEqual(part_answer.points_awarded, 2)  # Each part is worth 2

    def test_lock_round_auto_scores_ranking_partial_credit(self):
        """Test ranking question with some wrong answers gets partial credit"""
        # Team submits [1, 0, 2] - first two swapped, only position 2 correct
        TeamAnswer.objects.create(
            team=self.team,
            question=self.ranking_question,
            session_round=self.session_round,
            answer_text="[1, 0, 2]",
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.ranking_question,
            answer_part__isnull=False,
        ).order_by("answer_part__display_order")

        # Only position 2 is correct (item 2 at position 2)
        scores = [a.points_awarded for a in part_answers]
        self.assertEqual(scores[2], 2)  # Position 2 correct
        # Positions 0 and 1 are wrong
        self.assertEqual(scores[0], 0)
        self.assertEqual(scores[1], 0)

    def test_lock_round_auto_scores_matching_question(self):
        """Test that matching questions are auto-scored on lock"""
        # Team submits correct matches
        TeamAnswer.objects.create(
            team=self.team,
            question=self.matching_question,
            session_round=self.session_round,
            answer_text='["Capital A", "Capital B"]',
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.matching_question,
            answer_part__isnull=False,
        )

        total_points = sum(a.points_awarded for a in part_answers)
        self.assertEqual(total_points, 4)  # All correct

    def test_lock_round_does_not_auto_score_open_ended(self):
        """Test that Multiple Open Ended questions are NOT auto-scored"""
        TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            session_round=self.session_round,
            answer_text='["Answer A", "Answer B"]',
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.open_ended_question,
            answer_part__isnull=False,
        )

        # Open ended questions should not be auto-scored
        for part_answer in part_answers:
            self.assertIsNone(part_answer.points_awarded)

    def test_lock_round_keeps_single_answer_questions_intact(self):
        """Test that single-answer questions are not split"""
        TeamAnswer.objects.create(
            team=self.team,
            question=self.single_question,
            session_round=self.session_round,
            answer_text="My single answer",
        )

        url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Single question should have one answer with no answer_part
        answers = TeamAnswer.objects.filter(
            team=self.team, question=self.single_question
        )
        self.assertEqual(answers.count(), 1)
        self.assertIsNone(answers.first().answer_part)

    def test_get_scoring_data_returns_per_part_structure(self):
        """Test that scoring data includes per-part structure for multi-part questions"""
        # Submit and lock round
        TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            session_round=self.session_round,
            answer_text='["Answer A", "Answer B"]',
        )

        # Lock round first
        lock_url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            lock_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Get scoring data
        url = reverse("quiz:session_admin_scoring", args=[self.session.code])
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Find the open ended question
        open_ended_q = next(
            q for q in data["questions"] if q["id"] == self.open_ended_question.id
        )

        self.assertTrue(open_ended_q["is_multi_part"])
        self.assertEqual(len(open_ended_q["team_answers"]), 1)

        team_answer = open_ended_q["team_answers"][0]
        self.assertIn("parts", team_answer)
        self.assertEqual(len(team_answer["parts"]), 2)

        # Check parts have correct structure
        part1 = team_answer["parts"][0]
        self.assertIn("answer_part_id", part1)
        self.assertIn("team_answer_id", part1)
        self.assertIn("answer_text", part1)
        self.assertIn("points_awarded", part1)
        self.assertIn("max_points", part1)

    def test_score_per_part_answer(self):
        """Test scoring an individual part of a multi-part question"""
        # Submit and lock round
        TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            session_round=self.session_round,
            answer_text='["Answer A", "Answer B"]',
        )

        lock_url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            lock_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Get the per-part TeamAnswer record
        part_answer = TeamAnswer.objects.filter(
            team=self.team,
            question=self.open_ended_question,
            answer_part=self.open_ended_answers[0],
        ).first()

        # Score the part
        score_url = reverse("quiz:session_admin_score", args=[self.session.code])
        response = self.client.post(
            score_url,
            data=json.dumps({"team_answer_id": part_answer.id, "points": 2}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["points_awarded"], 2)
        self.assertEqual(data["max_points"], 2)  # Part max points

        part_answer.refresh_from_db()
        self.assertEqual(part_answer.points_awarded, 2)

    def test_score_per_part_validates_max_points(self):
        """Test that per-part scoring validates against part's max points, not question total"""
        # Submit and lock round
        TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            session_round=self.session_round,
            answer_text='["Answer A", "Answer B"]',
        )

        lock_url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            lock_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Get the per-part TeamAnswer record (part A is worth 2 points)
        part_answer = TeamAnswer.objects.filter(
            team=self.team,
            question=self.open_ended_question,
            answer_part=self.open_ended_answers[0],
        ).first()

        # Try to score more than part max (2 points)
        score_url = reverse("quiz:session_admin_score", args=[self.session.code])
        response = self.client.post(
            score_url,
            data=json.dumps({"team_answer_id": part_answer.id, "points": 3}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot exceed", response.json()["error"])

    def test_score_per_part_returns_question_total(self):
        """Test that scoring a part returns the question total across all parts"""
        # Submit and lock round
        TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            session_round=self.session_round,
            answer_text='["Answer A", "Answer B"]',
        )

        lock_url = reverse("quiz:session_admin_lock", args=[self.session.code])
        self.client.post(
            lock_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Score both parts
        part_answers = TeamAnswer.objects.filter(
            team=self.team,
            question=self.open_ended_question,
            answer_part__isnull=False,
        ).order_by("answer_part__display_order")

        score_url = reverse("quiz:session_admin_score", args=[self.session.code])

        # Score part A (2 points)
        self.client.post(
            score_url,
            data=json.dumps({"team_answer_id": part_answers[0].id, "points": 2}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        # Score part B (3 points)
        response = self.client.post(
            score_url,
            data=json.dumps({"team_answer_id": part_answers[1].id, "points": 3}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        data = response.json()
        self.assertEqual(data["question_total"], 5)  # 2 + 3 = 5

    def test_team_answer_unique_constraint_with_answer_part(self):
        """Test that unique constraint allows multiple answers per question when answer_part differs"""
        # Create two TeamAnswers for same team/question but different answer_parts
        ta1 = TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            answer_part=self.open_ended_answers[0],
            session_round=self.session_round,
            answer_text="Part A answer",
        )
        ta2 = TeamAnswer.objects.create(
            team=self.team,
            question=self.open_ended_question,
            answer_part=self.open_ended_answers[1],
            session_round=self.session_round,
            answer_text="Part B answer",
        )

        # Both should exist
        self.assertEqual(
            TeamAnswer.objects.filter(
                team=self.team, question=self.open_ended_question
            ).count(),
            2,
        )


class LeaderboardAPITest(TestCase):
    """Tests for leaderboard API endpoints"""

    def setUp(self):
        self.client = Client()
        self.game = Game.objects.create(name="Test Game")

        # Create rounds
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

        # Create question types
        self.q_type = QuestionType.objects.create(name="Open Ended")

        # Create questions for round 1 (10 total points)
        self.q1 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round1,
            text="Q1",
            question_number=1,
            total_points=5,
        )
        self.q2 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round1,
            text="Q2",
            question_number=2,
            total_points=5,
        )

        # Create questions for round 2 (15 total points)
        self.q3 = Question.objects.create(
            game=self.game,
            question_type=self.q_type,
            game_round=self.round2,
            text="Q3",
            question_number=3,
            total_points=15,
        )

        # Create session
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")

        # Create session rounds
        self.session_round1 = SessionRound.objects.create(
            session=self.session, round=self.round1
        )
        self.session_round2 = SessionRound.objects.create(
            session=self.session, round=self.round2
        )

        # Create teams
        self.team1 = SessionTeam.objects.create(
            session=self.session, name="Team Alpha", score=8
        )
        self.team2 = SessionTeam.objects.create(
            session=self.session, name="Team Beta", score=6
        )

    def test_admin_show_leaderboard_success(self):
        """Test transitioning from REVIEWING to LEADERBOARD state"""
        self.session.status = GameSession.Status.REVIEWING
        self.session.current_round = self.round1
        self.session.save()

        url = reverse("quiz:session_admin_show_leaderboard", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "leaderboard")

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.LEADERBOARD)

    def test_admin_show_leaderboard_wrong_state(self):
        """Test that show_leaderboard fails when not in REVIEWING state"""
        self.session.status = GameSession.Status.PLAYING
        self.session.save()

        url = reverse("quiz:session_admin_show_leaderboard", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_admin_start_next_round_from_leaderboard(self):
        """Test that start_next_round works from LEADERBOARD state"""
        # Set up session in leaderboard state
        self.session.status = GameSession.Status.LEADERBOARD
        self.session.current_round = self.round1
        self.session.save()

        self.session_round1.status = SessionRound.Status.SCORED
        self.session_round1.save()

        url = reverse("quiz:session_admin_start_next", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "next_round")
        self.assertEqual(data["round_number"], 2)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.PLAYING)
        self.assertEqual(self.session.current_round, self.round2)

    def test_get_leaderboard_data(self):
        """Test getting leaderboard data with team rankings and round scores"""
        # Score round 1
        self.session_round1.status = SessionRound.Status.SCORED
        self.session_round1.save()

        # Create team answers with scores
        TeamAnswer.objects.create(
            team=self.team1,
            question=self.q1,
            session_round=self.session_round1,
            answer_text="Answer 1",
            points_awarded=5,
        )
        TeamAnswer.objects.create(
            team=self.team1,
            question=self.q2,
            session_round=self.session_round1,
            answer_text="Answer 2",
            points_awarded=3,
        )
        TeamAnswer.objects.create(
            team=self.team2,
            question=self.q1,
            session_round=self.session_round1,
            answer_text="Answer 1",
            points_awarded=4,
        )
        TeamAnswer.objects.create(
            team=self.team2,
            question=self.q2,
            session_round=self.session_round1,
            answer_text="Answer 2",
            points_awarded=2,
        )

        self.session.status = GameSession.Status.LEADERBOARD
        self.session.current_round = self.round1
        self.session.save()

        url = reverse("quiz:session_leaderboard", args=[self.session.code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check structure
        self.assertIn("leaderboard", data)
        self.assertIn("completed_rounds", data)
        self.assertIn("upcoming_rounds", data)
        self.assertIn("total_game_points", data)
        self.assertIn("points_played", data)
        self.assertIn("points_remaining", data)
        self.assertIn("is_final_round", data)

        # Check leaderboard order (Team Alpha has more points)
        self.assertEqual(len(data["leaderboard"]), 2)
        self.assertEqual(data["leaderboard"][0]["team_name"], "Team Alpha")
        self.assertEqual(data["leaderboard"][0]["rank"], 1)
        self.assertEqual(data["leaderboard"][1]["team_name"], "Team Beta")
        self.assertEqual(data["leaderboard"][1]["rank"], 2)

        # Check round scores
        self.assertEqual(len(data["leaderboard"][0]["round_scores"]), 1)
        team1_r1_score = data["leaderboard"][0]["round_scores"][0]
        self.assertEqual(team1_r1_score["round_number"], 1)
        self.assertEqual(team1_r1_score["points_scored"], 8)  # 5 + 3
        self.assertEqual(team1_r1_score["max_points"], 10)

        # Check completed rounds
        self.assertEqual(len(data["completed_rounds"]), 1)
        self.assertEqual(data["completed_rounds"][0]["round_number"], 1)

        # Check upcoming rounds
        self.assertEqual(len(data["upcoming_rounds"]), 1)
        self.assertEqual(data["upcoming_rounds"][0]["round_number"], 2)
        self.assertEqual(data["upcoming_rounds"][0]["available_points"], 15)

        # Check totals
        self.assertEqual(data["total_game_points"], 25)  # 10 + 15
        self.assertEqual(data["points_played"], 10)
        self.assertEqual(data["points_remaining"], 15)
        self.assertFalse(data["is_final_round"])

    def test_get_leaderboard_data_final_round(self):
        """Test leaderboard data when all rounds are complete"""
        # Score both rounds
        self.session_round1.status = SessionRound.Status.SCORED
        self.session_round1.save()
        self.session_round2.status = SessionRound.Status.SCORED
        self.session_round2.save()

        self.session.status = GameSession.Status.LEADERBOARD
        self.session.current_round = self.round2
        self.session.save()

        url = reverse("quiz:session_leaderboard", args=[self.session.code])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should have no upcoming rounds
        self.assertEqual(len(data["upcoming_rounds"]), 0)
        self.assertTrue(data["is_final_round"])
        self.assertEqual(data["points_remaining"], 0)

    def test_admin_show_leaderboard_requires_auth(self):
        """Test that show_leaderboard requires admin authentication"""
        self.session.status = GameSession.Status.REVIEWING
        self.session.save()

        url = reverse("quiz:session_admin_show_leaderboard", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_show_leaderboard_invalid_token(self):
        """Test that show_leaderboard rejects invalid admin token"""
        self.session.status = GameSession.Status.REVIEWING
        self.session.save()

        url = reverse("quiz:session_admin_show_leaderboard", args=[self.session.code])
        response = self.client.post(
            url,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )

        self.assertEqual(response.status_code, 403)
