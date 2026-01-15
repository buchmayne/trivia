"""
Tests for session API endpoints
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from quiz.models import (
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
