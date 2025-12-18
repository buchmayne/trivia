"""
Tests for GameSession, SessionTeam, and TeamAnswer models
"""

from django.test import TestCase
from django.db import IntegrityError, transaction
from django.utils import timezone
from quiz.models import (
    Game,
    Question,
    QuestionType,
    QuestionRound,
    GameSession,
    SessionTeam,
    TeamAnswer,
)


class GameSessionModelTest(TestCase):
    """Test the GameSession model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")

    def test_create_session(self):
        """Test creating a game session"""
        session = GameSession.objects.create(
            game=self.game,
            host_name="Test Host",
            session_code="ABC123",
            status="waiting",
        )

        self.assertEqual(session.game, self.game)
        self.assertEqual(session.host_name, "Test Host")
        self.assertEqual(session.session_code, "ABC123")
        self.assertEqual(session.status, "waiting")
        self.assertEqual(session.current_question_number, 0)
        self.assertIsNotNone(session.created_at)

    def test_session_code_unique(self):
        """Test that session codes must be unique"""
        GameSession.objects.create(
            game=self.game, host_name="Host 1", session_code="ABC123"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GameSession.objects.create(
                    game=self.game, host_name="Host 2", session_code="ABC123"
                )

    def test_session_status_choices(self):
        """Test different session status values"""
        statuses = ["waiting", "active", "paused", "completed"]

        for i, status_value in enumerate(statuses):
            session = GameSession.objects.create(
                game=self.game,
                host_name="Test Host",
                session_code=f"CODE{i}",  # Keep session_code short (max 8 chars)
                status=status_value,
            )
            self.assertEqual(session.status, status_value)

    def test_session_default_max_teams(self):
        """Test that max_teams has a default value"""
        session = GameSession.objects.create(
            game=self.game, host_name="Test Host", session_code="ABC123"
        )

        self.assertEqual(session.max_teams, 16)

    def test_session_timestamps(self):
        """Test session timestamp fields"""
        session = GameSession.objects.create(
            game=self.game, host_name="Test Host", session_code="ABC123"
        )

        # Initially, only created_at should be set
        self.assertIsNotNone(session.created_at)
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.completed_at)

        # Manually set started_at and completed_at
        session.started_at = timezone.now()
        session.completed_at = timezone.now()
        session.save()

        self.assertIsNotNone(session.started_at)
        self.assertIsNotNone(session.completed_at)

    def test_session_current_question_number_default(self):
        """Test that current_question_number defaults to 0"""
        session = GameSession.objects.create(
            game=self.game, host_name="Test Host", session_code="ABC123"
        )

        self.assertEqual(session.current_question_number, 0)


class SessionTeamModelTest(TestCase):
    """Test the SessionTeam model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(
            game=self.game, host_name="Test Host", session_code="ABC123"
        )

    def test_create_team(self):
        """Test creating a team in a session"""
        team = SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

        self.assertEqual(team.session, self.session)
        self.assertEqual(team.team_name, "Team Alpha")
        self.assertEqual(team.total_score, 0)
        self.assertIsNotNone(team.joined_at)

    def test_team_default_total_score(self):
        """Test that total_score defaults to 0"""
        team = SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

        self.assertEqual(team.total_score, 0)

    def test_unique_team_name_per_session(self):
        """Test that team names must be unique within a session"""
        SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

    def test_same_team_name_different_sessions(self):
        """Test that same team name can exist in different sessions"""
        session2 = GameSession.objects.create(
            game=self.game, host_name="Another Host", session_code="XYZ789"
        )

        team1 = SessionTeam.objects.create(session=self.session, team_name="Team Alpha")
        team2 = SessionTeam.objects.create(session=session2, team_name="Team Alpha")

        self.assertEqual(team1.team_name, team2.team_name)
        self.assertNotEqual(team1.session, team2.session)

    def test_team_joined_at_auto_set(self):
        """Test that joined_at is automatically set"""
        team = SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

        self.assertIsNotNone(team.joined_at)
        self.assertIsInstance(team.joined_at, timezone.datetime)

    def test_update_team_score(self):
        """Test updating a team's total score"""
        team = SessionTeam.objects.create(session=self.session, team_name="Team Alpha")

        team.total_score = 100
        team.save()

        team.refresh_from_db()
        self.assertEqual(team.total_score, 100)


class TeamAnswerModelTest(TestCase):
    """Test the TeamAnswer model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.question = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round,
            text="What is the capital of France?",
            question_number=1,
        )
        self.session = GameSession.objects.create(
            game=self.game, host_name="Test Host", session_code="ABC123"
        )
        self.team = SessionTeam.objects.create(
            session=self.session, team_name="Team Alpha"
        )

    def test_create_team_answer(self):
        """Test creating a team answer"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            submitted_answer="Paris",
            points_awarded=10,
        )

        self.assertEqual(answer.team, self.team)
        self.assertEqual(answer.question, self.question)
        self.assertEqual(answer.submitted_answer, "Paris")
        self.assertEqual(answer.points_awarded, 10)
        self.assertIsNotNone(answer.submitted_at)

    def test_team_answer_default_points(self):
        """Test that points_awarded defaults to 0"""
        answer = TeamAnswer.objects.create(
            team=self.team, question=self.question, submitted_answer="London"
        )

        self.assertEqual(answer.points_awarded, 0)

    def test_unique_team_question_constraint(self):
        """Test that a team can only submit one answer per question"""
        TeamAnswer.objects.create(
            team=self.team, question=self.question, submitted_answer="Paris"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TeamAnswer.objects.create(
                    team=self.team, question=self.question, submitted_answer="London"
                )

    def test_different_teams_same_question(self):
        """Test that different teams can answer the same question"""
        team2 = SessionTeam.objects.create(session=self.session, team_name="Team Beta")

        answer1 = TeamAnswer.objects.create(
            team=self.team, question=self.question, submitted_answer="Paris"
        )
        answer2 = TeamAnswer.objects.create(
            team=team2, question=self.question, submitted_answer="London"
        )

        self.assertNotEqual(answer1.team, answer2.team)
        self.assertEqual(answer1.question, answer2.question)

    def test_submitted_at_auto_set(self):
        """Test that submitted_at is automatically set"""
        answer = TeamAnswer.objects.create(
            team=self.team, question=self.question, submitted_answer="Paris"
        )

        self.assertIsNotNone(answer.submitted_at)
        self.assertIsInstance(answer.submitted_at, timezone.datetime)

    def test_team_answer_with_zero_points(self):
        """Test creating an answer with zero points (incorrect answer)"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            submitted_answer="Wrong Answer",
            points_awarded=0,
        )

        self.assertEqual(answer.points_awarded, 0)


class SessionWorkflowTest(TestCase):
    """Test complete session workflows"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

        # Create multiple questions
        self.questions = []
        for i in range(3):
            q = Question.objects.create(
                game=self.game,
                question_type=self.question_type,
                game_round=self.round,
                text=f"Question {i+1}",
                question_number=i + 1,
                total_points=10,
            )
            self.questions.append(q)

    def test_complete_session_workflow(self):
        """Test a complete session from creation to completion"""
        # Create session
        session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123", status="waiting"
        )

        # Add teams
        team1 = SessionTeam.objects.create(session=session, team_name="Team A")
        team2 = SessionTeam.objects.create(session=session, team_name="Team B")

        # Start session
        session.status = "active"
        session.started_at = timezone.now()
        session.save()

        # Teams answer questions
        TeamAnswer.objects.create(
            team=team1,
            question=self.questions[0],
            submitted_answer="A",
            points_awarded=10,
        )
        TeamAnswer.objects.create(
            team=team2,
            question=self.questions[0],
            submitted_answer="B",
            points_awarded=5,
        )

        # Update team scores
        team1.total_score = 10
        team1.save()
        team2.total_score = 5
        team2.save()

        # Complete session
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save()

        # Verify final state
        self.assertEqual(session.status, "completed")
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(team1.total_score, 10)
        self.assertEqual(team2.total_score, 5)
        self.assertEqual(TeamAnswer.objects.filter(team=team1).count(), 1)

    def test_session_team_capacity(self):
        """Test that sessions respect max_teams limit"""
        session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123", max_teams=2
        )

        # Add teams up to the limit
        team1 = SessionTeam.objects.create(session=session, team_name="Team A")
        team2 = SessionTeam.objects.create(session=session, team_name="Team B")

        # Verify we can add exactly max_teams
        self.assertEqual(session.teams.count(), 2)

        # Add one more (this should work at the model level, but API should prevent it)
        team3 = SessionTeam.objects.create(session=session, team_name="Team C")
        self.assertEqual(session.teams.count(), 3)

    def test_session_progression_through_questions(self):
        """Test session progressing through questions"""
        session = GameSession.objects.create(
            game=self.game,
            host_name="Host",
            session_code="ABC123",
            status="active",
            current_question_number=0,
        )

        # Progress through questions
        for i, question in enumerate(self.questions):
            session.current_question_number = question.question_number
            session.save()

            session.refresh_from_db()
            self.assertEqual(session.current_question_number, i + 1)

    def test_multiple_rounds_answers(self):
        """Test teams answering multiple questions across rounds"""
        session = GameSession.objects.create(
            game=self.game, host_name="Host", session_code="ABC123"
        )
        team = SessionTeam.objects.create(session=session, team_name="Team A")

        # Answer all questions
        total_points = 0
        for question in self.questions:
            answer = TeamAnswer.objects.create(
                team=team,
                question=question,
                submitted_answer="Answer",
                points_awarded=10,
            )
            total_points += answer.points_awarded

        # Verify all answers were recorded
        self.assertEqual(TeamAnswer.objects.filter(team=team).count(), 3)
        self.assertEqual(total_points, 30)
