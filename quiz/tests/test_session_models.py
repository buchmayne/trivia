"""
Tests for session models: GameSession, SessionTeam, SessionRound, TeamAnswer
"""

from django.test import TestCase
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta

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


class GameSessionModelTest(TestCase):
    """Test the GameSession model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")

    def test_create_session(self):
        """Test creating a game session"""
        session = GameSession.objects.create(game=self.game, admin_name="Test Host")

        self.assertEqual(session.game, self.game)
        self.assertEqual(session.admin_name, "Test Host")
        self.assertEqual(session.status, GameSession.Status.LOBBY)
        self.assertEqual(session.max_teams, 16)
        self.assertIsNotNone(session.created_at)
        self.assertIsNotNone(session.code)
        self.assertIsNotNone(session.admin_token)

    def test_code_auto_generated(self):
        """Test that session code is automatically generated"""
        session = GameSession.objects.create(game=self.game, admin_name="Test Host")

        self.assertEqual(len(session.code), 6)
        self.assertTrue(session.code.isalnum())
        self.assertTrue(session.code.isupper())

    def test_code_unique(self):
        """Test that session codes are unique"""
        session1 = GameSession.objects.create(game=self.game, admin_name="Host 1")
        session2 = GameSession.objects.create(game=self.game, admin_name="Host 2")

        self.assertNotEqual(session1.code, session2.code)

    def test_admin_token_unique(self):
        """Test that admin tokens are unique"""
        session1 = GameSession.objects.create(game=self.game, admin_name="Host 1")
        session2 = GameSession.objects.create(game=self.game, admin_name="Host 2")

        self.assertNotEqual(session1.admin_token, session2.admin_token)

    def test_pause_session(self):
        """Test pausing a session"""
        session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.PLAYING
        )

        session.pause()

        self.assertEqual(session.status, GameSession.Status.PAUSED)
        self.assertEqual(session.status_before_pause, GameSession.Status.PLAYING)

    def test_resume_session(self):
        """Test resuming a paused session"""
        session = GameSession.objects.create(
            game=self.game,
            admin_name="Host",
            status=GameSession.Status.PAUSED,
            status_before_pause=GameSession.Status.PLAYING,
        )

        session.resume()

        self.assertEqual(session.status, GameSession.Status.PLAYING)
        self.assertIsNone(session.status_before_pause)

    def test_pause_completed_session_no_op(self):
        """Test that pausing a completed session does nothing"""
        session = GameSession.objects.create(
            game=self.game, admin_name="Host", status=GameSession.Status.COMPLETED
        )

        session.pause()

        self.assertEqual(session.status, GameSession.Status.COMPLETED)
        self.assertIsNone(session.status_before_pause)

    def test_session_ordering(self):
        """Test that sessions are ordered by creation date descending"""
        session1 = GameSession.objects.create(game=self.game, admin_name="Host 1")
        session2 = GameSession.objects.create(game=self.game, admin_name="Host 2")

        sessions = list(GameSession.objects.all())
        self.assertEqual(sessions[0], session2)
        self.assertEqual(sessions[1], session1)


class SessionTeamModelTest(TestCase):
    """Test the SessionTeam model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")

    def test_create_team(self):
        """Test creating a team"""
        team = SessionTeam.objects.create(session=self.session, name="Team Alpha")

        self.assertEqual(team.session, self.session)
        self.assertEqual(team.name, "Team Alpha")
        self.assertEqual(team.score, 0)
        self.assertFalse(team.joined_late)
        self.assertIsNotNone(team.joined_at)
        self.assertIsNotNone(team.token)

    def test_team_token_unique(self):
        """Test that team tokens are unique"""
        team1 = SessionTeam.objects.create(session=self.session, name="Team 1")
        team2 = SessionTeam.objects.create(session=self.session, name="Team 2")

        self.assertNotEqual(team1.token, team2.token)

    def test_unique_team_name_per_session(self):
        """Test that team names must be unique within a session"""
        SessionTeam.objects.create(session=self.session, name="Team Alpha")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionTeam.objects.create(session=self.session, name="Team Alpha")

    def test_same_name_different_sessions(self):
        """Test that same team name can exist in different sessions"""
        session2 = GameSession.objects.create(game=self.game, admin_name="Another Host")

        team1 = SessionTeam.objects.create(session=self.session, name="Team Alpha")
        team2 = SessionTeam.objects.create(session=session2, name="Team Alpha")

        self.assertEqual(team1.name, team2.name)
        self.assertNotEqual(team1.session, team2.session)

    def test_team_ordering(self):
        """Test that teams are ordered by score descending, then joined_at"""
        team1 = SessionTeam.objects.create(
            session=self.session, name="Team A", score=50
        )
        team2 = SessionTeam.objects.create(
            session=self.session, name="Team B", score=100
        )
        team3 = SessionTeam.objects.create(
            session=self.session, name="Team C", score=50
        )

        teams = list(self.session.teams.all())
        self.assertEqual(teams[0], team2)  # Highest score
        self.assertEqual(teams[1], team1)  # Earlier join time
        self.assertEqual(teams[2], team3)

    def test_late_join_flag(self):
        """Test setting joined_late flag"""
        team = SessionTeam.objects.create(
            session=self.session, name="Late Team", joined_late=True
        )

        self.assertTrue(team.joined_late)


class SessionRoundModelTest(TestCase):
    """Test the SessionRound model"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.round = QuestionRound.objects.create(name="Round 1", round_number=1)

    def test_create_session_round(self):
        """Test creating a session round"""
        session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )

        self.assertEqual(session_round.session, self.session)
        self.assertEqual(session_round.round, self.round)
        self.assertEqual(session_round.status, SessionRound.Status.PENDING)
        self.assertIsNone(session_round.started_at)
        self.assertIsNone(session_round.locked_at)
        self.assertIsNone(session_round.scored_at)

    def test_unique_session_round(self):
        """Test that session+round combination is unique"""
        SessionRound.objects.create(session=self.session, round=self.round)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionRound.objects.create(session=self.session, round=self.round)

    def test_session_round_ordering(self):
        """Test that session rounds are ordered by round number"""
        round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        round2 = QuestionRound.objects.create(name="Round 2", round_number=2)
        round3 = QuestionRound.objects.create(name="Round 3", round_number=3)

        SessionRound.objects.create(session=self.session, round=round3)
        SessionRound.objects.create(session=self.session, round=round1)
        SessionRound.objects.create(session=self.session, round=round2)

        rounds = list(self.session.session_rounds.all())
        self.assertEqual(rounds[0].round, round1)
        self.assertEqual(rounds[1].round, round2)
        self.assertEqual(rounds[2].round, round3)

    def test_status_progression(self):
        """Test typical status progression"""
        session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )

        # Start round
        session_round.status = SessionRound.Status.ACTIVE
        session_round.started_at = timezone.now()
        session_round.save()
        self.assertEqual(session_round.status, SessionRound.Status.ACTIVE)

        # Lock round
        session_round.status = SessionRound.Status.LOCKED
        session_round.locked_at = timezone.now()
        session_round.save()
        self.assertEqual(session_round.status, SessionRound.Status.LOCKED)

        # Complete scoring
        session_round.status = SessionRound.Status.SCORED
        session_round.scored_at = timezone.now()
        session_round.save()
        self.assertEqual(session_round.status, SessionRound.Status.SCORED)


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
            text="What is 2+2?",
            question_number=1,
            total_points=10,
        )
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.session_round = SessionRound.objects.create(
            session=self.session, round=self.round
        )
        self.team = SessionTeam.objects.create(session=self.session, name="Team A")

    def test_create_team_answer(self):
        """Test creating a team answer"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="4",
        )

        self.assertEqual(answer.team, self.team)
        self.assertEqual(answer.question, self.question)
        self.assertEqual(answer.answer_text, "4")
        self.assertFalse(answer.is_locked)
        self.assertIsNone(answer.points_awarded)
        self.assertIsNotNone(answer.submitted_at)

    def test_unique_team_question_per_part(self):
        """Test unique constraint on team+question+answer_part combination.
        Multiple answers per team per question are allowed if answer_part differs.
        Note: When answer_part is NULL, SQL allows multiple rows (NULL != NULL)."""
        from quiz.models import Answer

        # Create an answer (part) for the question
        answer_part = Answer.objects.create(
            question=self.question,
            text="Part A",
            display_order=1,
            points=1,
        )

        # Create first TeamAnswer with specific answer_part
        TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            answer_part=answer_part,
            session_round=self.session_round,
            answer_text="4",
        )

        # Creating duplicate with same team+question+answer_part should fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TeamAnswer.objects.create(
                    team=self.team,
                    question=self.question,
                    answer_part=answer_part,
                    session_round=self.session_round,
                    answer_text="5",
                )

    def test_different_teams_same_question(self):
        """Test that different teams can answer the same question"""
        team2 = SessionTeam.objects.create(session=self.session, name="Team B")

        answer1 = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="4",
        )
        answer2 = TeamAnswer.objects.create(
            team=team2,
            question=self.question,
            session_round=self.session_round,
            answer_text="5",
        )

        self.assertNotEqual(answer1.team, answer2.team)
        self.assertEqual(answer1.question, answer2.question)

    def test_lock_answer(self):
        """Test locking an answer"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="4",
        )

        answer.is_locked = True
        answer.save()

        answer.refresh_from_db()
        self.assertTrue(answer.is_locked)

    def test_score_answer(self):
        """Test scoring an answer"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="4",
        )

        answer.points_awarded = 10
        answer.scored_at = timezone.now()
        answer.save()

        answer.refresh_from_db()
        self.assertEqual(answer.points_awarded, 10)
        self.assertIsNotNone(answer.scored_at)

    def test_partial_credit(self):
        """Test awarding partial credit"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="Almost correct",
        )

        answer.points_awarded = 7  # Partial credit
        answer.save()

        self.assertEqual(answer.points_awarded, 7)

    def test_empty_answer(self):
        """Test creating an empty answer"""
        answer = TeamAnswer.objects.create(
            team=self.team,
            question=self.question,
            session_round=self.session_round,
            answer_text="",
        )

        self.assertEqual(answer.answer_text, "")


class SessionWorkflowTest(TestCase):
    """Test complete session workflows"""

    def setUp(self):
        self.game = Game.objects.create(name="Test Game")
        self.question_type = QuestionType.objects.create(name="Multiple Choice")
        self.round1 = QuestionRound.objects.create(name="Round 1", round_number=1)
        self.round2 = QuestionRound.objects.create(name="Round 2", round_number=2)

        # Create questions
        self.q1 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round1,
            text="Question 1",
            question_number=1,
            total_points=10,
        )
        self.q2 = Question.objects.create(
            game=self.game,
            question_type=self.question_type,
            game_round=self.round2,
            text="Question 2",
            question_number=2,
            total_points=10,
        )

    def test_full_game_workflow(self):
        """Test a complete game from creation to completion"""
        # Create session
        session = GameSession.objects.create(game=self.game, admin_name="Host")

        # Create session rounds
        sr1 = SessionRound.objects.create(session=session, round=self.round1)
        sr2 = SessionRound.objects.create(session=session, round=self.round2)

        # Teams join
        team1 = SessionTeam.objects.create(session=session, name="Team A")
        team2 = SessionTeam.objects.create(session=session, name="Team B")

        # Start game
        session.status = GameSession.Status.PLAYING
        session.started_at = timezone.now()
        session.current_round = self.round1
        session.current_question = self.q1
        session.save()

        sr1.status = SessionRound.Status.ACTIVE
        sr1.started_at = timezone.now()
        sr1.save()

        # Teams answer
        a1 = TeamAnswer.objects.create(
            team=team1, question=self.q1, session_round=sr1, answer_text="Answer 1"
        )
        a2 = TeamAnswer.objects.create(
            team=team2, question=self.q1, session_round=sr1, answer_text="Answer 2"
        )

        # Lock round
        sr1.status = SessionRound.Status.LOCKED
        sr1.locked_at = timezone.now()
        sr1.save()

        a1.is_locked = True
        a2.is_locked = True
        a1.save()
        a2.save()

        # Score answers
        session.status = GameSession.Status.SCORING
        session.save()

        a1.points_awarded = 10
        a1.scored_at = timezone.now()
        a1.save()

        a2.points_awarded = 5
        a2.scored_at = timezone.now()
        a2.save()

        # Update team scores
        team1.score = 10
        team2.score = 5
        team1.save()
        team2.save()

        # Complete round
        sr1.status = SessionRound.Status.SCORED
        sr1.scored_at = timezone.now()
        sr1.save()

        # Verify state
        self.assertEqual(session.status, GameSession.Status.SCORING)
        self.assertEqual(team1.score, 10)
        self.assertEqual(team2.score, 5)
        self.assertTrue(a1.is_locked)
        self.assertEqual(a1.points_awarded, 10)

    def test_late_join_workflow(self):
        """Test team joining after game has started"""
        session = GameSession.objects.create(
            game=self.game,
            admin_name="Host",
            status=GameSession.Status.PLAYING,
            started_at=timezone.now(),
        )

        # Team joins late
        late_team = SessionTeam.objects.create(
            session=session, name="Late Team", joined_late=True
        )

        self.assertTrue(late_team.joined_late)
        self.assertGreater(late_team.joined_at, session.started_at)
