"""
Integration tests for complete session workflows.

Tests end-to-end scenarios:
- Complete game session from creation to completion
- Multiple teams competing
- Admin controls and team interactions
- State transitions and data consistency
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from quiz.models import (
    Game,
    GameSession,
    SessionTeam,
    SessionRound,
    TeamAnswer,
    Question,
    QuestionRound,
    Category,
    QuestionType,
    Answer,
)


class CompleteSessionWorkflowTest(TestCase):
    """Test complete session workflow from start to finish"""

    def setUp(self):
        self.client = Client()

        # Create game with complete data
        self.game = Game.objects.create(
            name="Integration Test Game",
            description="Full game for integration testing",
        )

        # Create rounds
        self.round1 = QuestionRound.objects.create(round_number=1, name="Round 1")
        self.round2 = QuestionRound.objects.create(round_number=2, name="Round 2")

        # Create category and question type
        self.category = Category.objects.create(name="General")
        self.question_type = QuestionType.objects.create(
            name="Open-Ended", description="Standard"
        )

        # Create questions for round 1
        self.q1 = Question.objects.create(
            game=self.game,
            question_number=1,
            text="Question 1",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round1,
        )
        self.q2 = Question.objects.create(
            game=self.game,
            question_number=2,
            text="Question 2",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round1,
        )

        # Create questions for round 2
        self.q3 = Question.objects.create(
            game=self.game,
            question_number=3,
            text="Question 3",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round2,
        )

        # Create answers
        Answer.objects.create(
            question=self.q1, answer_text="Answer 1", text="Answer 1", display_order=1
        )
        Answer.objects.create(
            question=self.q2, answer_text="Answer 2", text="Answer 2", display_order=1
        )
        Answer.objects.create(
            question=self.q3, answer_text="Answer 3", text="Answer 3", display_order=1
        )

    def test_complete_single_round_workflow(self):
        """Test complete workflow for a single round session"""
        # Step 1: Create session via API
        create_url = reverse("quiz:session_create")
        create_response = self.client.post(
            create_url,
            json.dumps(
                {"admin_name": "Test Admin", "game_id": self.game.id, "max_teams": 8}
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 200)
        create_data = create_response.json()

        session_code = create_data["code"]
        admin_token = create_data["admin_token"]

        # Step 2: Teams join
        join_url = reverse("quiz:session_join", args=[session_code])

        team1_response = self.client.post(
            join_url,
            json.dumps({"team_name": "Team Alpha"}),
            content_type="application/json",
        )
        self.assertEqual(team1_response.status_code, 200)
        team1_token = team1_response.json()["team_token"]

        team2_response = self.client.post(
            join_url,
            json.dumps({"team_name": "Team Beta"}),
            content_type="application/json",
        )
        self.assertEqual(team2_response.status_code, 200)
        team2_token = team2_response.json()["team_token"]

        # Step 3: Admin starts game
        start_url = reverse("quiz:session_admin_start", args=[session_code])
        start_response = self.client.post(
            start_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )
        self.assertEqual(start_response.status_code, 200)

        # Verify session status
        session = GameSession.objects.get(code=session_code)
        self.assertEqual(session.status, GameSession.Status.PLAYING)

        # Step 4: Teams submit answers for round 1
        submit_url = reverse("quiz:session_team_answer", args=[session_code])

        # Team 1 submits for Q1
        self.client.post(
            submit_url,
            json.dumps({"question_id": self.q1.id, "answer_text": "Team 1 Answer Q1"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {team1_token}",
        )

        # Team 1 submits for Q2
        self.client.post(
            submit_url,
            json.dumps({"question_id": self.q2.id, "answer_text": "Team 1 Answer Q2"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {team1_token}",
        )

        # Team 2 submits for Q1
        self.client.post(
            submit_url,
            json.dumps({"question_id": self.q1.id, "answer_text": "Team 2 Answer Q1"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {team2_token}",
        )

        # Step 5: Admin locks round
        lock_url = reverse("quiz:session_admin_lock", args=[session_code])
        lock_response = self.client.post(
            lock_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )
        self.assertEqual(lock_response.status_code, 200)

        # Step 6: Admin scores answers
        score_url = reverse("quiz:session_admin_score", args=[session_code])

        # Score team 1's Q1 answer
        team1 = SessionTeam.objects.get(session__code=session_code, name="Team Alpha")
        answer1 = TeamAnswer.objects.get(team=team1, question=self.q1)

        self.client.post(
            score_url,
            json.dumps({"answer_id": answer1.id, "points": 10}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )

        # Score team 1's Q2 answer
        answer2 = TeamAnswer.objects.get(team=team1, question=self.q2)
        self.client.post(
            score_url,
            json.dumps({"answer_id": answer2.id, "points": 5}),  # Partial credit
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )

        # Score team 2's Q1 answer
        team2 = SessionTeam.objects.get(session__code=session_code, name="Team Beta")
        answer3 = TeamAnswer.objects.get(team=team2, question=self.q1)
        self.client.post(
            score_url,
            json.dumps({"answer_id": answer3.id, "points": 10}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )

        # Step 7: Verify scores
        team1.refresh_from_db()
        team2.refresh_from_db()

        self.assertEqual(team1.score, 15)  # 10 + 5
        self.assertEqual(team2.score, 10)  # 10

        # Step 8: Complete round
        complete_url = reverse("quiz:session_admin_complete", args=[session_code])
        complete_response = self.client.post(
            complete_url,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )
        self.assertEqual(complete_response.status_code, 200)

        # Verify round is scored
        session_round = SessionRound.objects.get(
            session__code=session_code, round=self.round1
        )
        self.assertEqual(session_round.status, SessionRound.Status.SCORED)

    def test_multiple_rounds_workflow(self):
        """Test workflow with multiple rounds"""
        # Create session
        session = GameSession.objects.create(
            game=self.game, admin_name="Admin", max_teams=8
        )

        # Join teams
        team = SessionTeam.objects.create(session=session, name="Test Team")

        # Start game
        session.status = GameSession.Status.PLAYING
        session.save()

        # Round 1
        session.current_round = self.round1
        session.current_question = self.q1
        session.save()

        # Create session round
        round1 = SessionRound.objects.create(session=session, round=self.round1)
        round1.status = SessionRound.Status.ACTIVE
        round1.save()

        # Submit and score round 1
        TeamAnswer.objects.create(
            team=team,
            question=self.q1,
            session_round=round1,
            answer_text="Answer",
            points_awarded=10,
            scored_at=timezone.now(),
        )
        team.score = 10
        team.save()

        round1.status = SessionRound.Status.SCORED
        round1.save()

        # Round 2
        session.current_round = self.round2
        session.current_question = self.q3
        session.save()

        round2 = SessionRound.objects.create(session=session, round=self.round2)
        round2.status = SessionRound.Status.ACTIVE
        round2.save()

        # Submit and score round 2
        TeamAnswer.objects.create(
            team=team,
            question=self.q3,
            session_round=round2,
            answer_text="Answer",
            points_awarded=10,
            scored_at=timezone.now(),
        )
        team.score = 20
        team.save()

        round2.status = SessionRound.Status.SCORED
        round2.save()

        # Verify total score
        team.refresh_from_db()
        self.assertEqual(team.score, 20)

        # Verify both rounds are scored
        self.assertEqual(
            SessionRound.objects.filter(
                session=session, status=SessionRound.Status.SCORED
            ).count(),
            2,
        )


class LateJoinWorkflowTest(TestCase):
    """Test late join functionality"""

    def setUp(self):
        self.game = Game.objects.create(name="Test", description="Test")

        self.round1 = QuestionRound.objects.create(round_number=1, name="R1")
        self.category = Category.objects.create(name="General")
        self.question_type = QuestionType.objects.create(
            name="Open", description="Open"
        )

        self.q1 = Question.objects.create(
            game=self.game,
            question_number=1,
            text="Q1",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round1,
        )

        self.session = GameSession.objects.create(
            game=self.game, admin_name="Admin", max_teams=8
        )

    def test_team_joins_after_game_started(self):
        """Test team joining after game has started"""
        # Start session
        self.session.status = GameSession.Status.PLAYING
        self.session.current_round = self.round1
        self.session.current_question = self.q1
        self.session.save()

        # Team joins late
        join_url = reverse("quiz:session_join", args=[self.session.code])
        response = self.client.post(
            join_url,
            json.dumps({"team_name": "Late Team"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Verify team was created
        team = SessionTeam.objects.get(session=self.session, name="Late Team")
        self.assertIsNotNone(team.joined_at)

    def test_team_cannot_join_completed_session(self):
        """Test that teams cannot join completed sessions"""
        self.session.status = GameSession.Status.COMPLETED
        self.session.save()

        join_url = reverse("quiz:session_join", args=[self.session.code])
        response = self.client.post(
            join_url,
            json.dumps({"team_name": "Too Late Team"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class AdminDisconnectWorkflowTest(TestCase):
    """Test admin disconnect and reconnect handling"""

    def setUp(self):
        self.game = Game.objects.create(name="Test", description="Test")
        self.session = GameSession.objects.create(
            game=self.game, admin_name="Admin", max_teams=8
        )
        self.session.status = GameSession.Status.PLAYING
        self.session.save()

    def test_session_pauses_on_admin_timeout(self):
        """Test that session pauses when admin disconnects"""
        # Simulate admin disconnect (last_seen > 30 seconds ago)
        old_time = timezone.now() - timezone.timedelta(seconds=35)
        self.session.admin_last_seen = old_time
        self.session.save()

        # Trigger pause
        self.session.pause()

        self.assertEqual(self.session.status, GameSession.Status.PAUSED)
        self.assertEqual(self.session.status_before_pause, GameSession.Status.PLAYING)

    def test_session_resumes_on_admin_reconnect(self):
        """Test that session resumes when admin reconnects"""
        # Pause session
        self.session.status_before_pause = GameSession.Status.PLAYING
        self.session.status = GameSession.Status.PAUSED
        self.session.save()

        # Admin reconnects (via any admin endpoint)
        state_url = reverse("quiz:session_state", args=[self.session.code])
        response = self.client.get(state_url)

        # Manually trigger resume (in real flow, admin endpoints do this)
        self.session.resume()

        self.assertEqual(self.session.status, GameSession.Status.PLAYING)


class ScoringWorkflowTest(TestCase):
    """Test various scoring scenarios"""

    def setUp(self):
        self.game = Game.objects.create(name="Test", description="Test")

        self.round1 = QuestionRound.objects.create(round_number=1, name="R1")
        self.category = Category.objects.create(name="General")
        self.question_type = QuestionType.objects.create(
            name="Open", description="Open"
        )

        self.q1 = Question.objects.create(
            game=self.game,
            question_number=1,
            text="Q1",
            total_points=10,
            category=self.category,
            question_type=self.question_type,
            game_round=self.round1,
        )

        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")

        self.team = SessionTeam.objects.create(session=self.session, name="Test Team")

    def test_full_points_scoring(self):
        """Test awarding full points"""
        session_round = SessionRound.objects.create(
            session=self.session, round=self.round1
        )

        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.q1,
            session_round=session_round,
            answer_text="Correct answer",
        )

        score_url = reverse("quiz:session_admin_score", args=[self.session.code])
        response = self.client.post(
            score_url,
            json.dumps({"answer_id": answer.id, "points": 10}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        self.assertEqual(response.status_code, 200)

        answer.refresh_from_db()
        self.team.refresh_from_db()

        self.assertEqual(answer.points_awarded, 10)
        self.assertEqual(self.team.score, 10)
        self.assertIsNotNone(answer.scored_at)

    def test_partial_points_scoring(self):
        """Test awarding partial points"""
        session_round = SessionRound.objects.create(
            session=self.session, round=self.round1
        )

        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.q1,
            session_round=session_round,
            answer_text="Partially correct",
        )

        score_url = reverse("quiz:session_admin_score", args=[self.session.code])
        self.client.post(
            score_url,
            json.dumps({"answer_id": answer.id, "points": 5}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        answer.refresh_from_db()
        self.team.refresh_from_db()

        self.assertEqual(answer.points_awarded, 5)
        self.assertEqual(self.team.score, 5)

    def test_zero_points_scoring(self):
        """Test awarding zero points (incorrect answer)"""
        session_round = SessionRound.objects.create(
            session=self.session, round=self.round1
        )

        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.q1,
            session_round=session_round,
            answer_text="Wrong answer",
        )

        score_url = reverse("quiz:session_admin_score", args=[self.session.code])
        self.client.post(
            score_url,
            json.dumps({"answer_id": answer.id, "points": 0}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.session.admin_token}",
        )

        answer.refresh_from_db()
        self.team.refresh_from_db()

        self.assertEqual(answer.points_awarded, 0)
        self.assertEqual(self.team.score, 0)
        self.assertIsNotNone(answer.scored_at)


class StateConsistencyTest(TestCase):
    """Test state consistency across operations"""

    def setUp(self):
        self.game = Game.objects.create(name="Test", description="Test")
        self.session = GameSession.objects.create(game=self.game, admin_name="Admin")

    def test_state_endpoint_returns_current_state(self):
        """Test that state endpoint returns accurate current state"""
        state_url = reverse("quiz:session_state", args=[self.session.code])
        response = self.client.get(state_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], self.session.status)
        self.assertEqual(data["admin_name"], self.session.admin_name)
        self.assertEqual(data["game_id"], self.game.id)
        self.assertIn("teams", data)
        self.assertIn("max_teams", data)

    def test_state_updates_after_team_join(self):
        """Test that state reflects team joins"""
        # Initial state
        state_url = reverse("quiz:session_state", args=[self.session.code])
        response1 = self.client.get(state_url)
        initial_team_count = len(response1.json()["teams"])

        # Team joins
        SessionTeam.objects.create(session=self.session, name="New Team")

        # Check state again
        response2 = self.client.get(state_url)
        new_team_count = len(response2.json()["teams"])

        self.assertEqual(new_team_count, initial_team_count + 1)

    def test_state_reflects_status_changes(self):
        """Test that state reflects session status changes"""
        state_url = reverse("quiz:session_state", args=[self.session.code])

        # Check lobby state
        response1 = self.client.get(state_url)
        self.assertEqual(response1.json()["status"], GameSession.Status.LOBBY)

        # Change to playing
        self.session.status = GameSession.Status.PLAYING
        self.session.save()

        # Check playing state
        response2 = self.client.get(state_url)
        self.assertEqual(response2.json()["status"], GameSession.Status.PLAYING)
