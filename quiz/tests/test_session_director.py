"""
Unit tests for quiz.session_director.SessionDirector.

These tests construct a GameSession directly and drive the lifecycle through
the Director's interface. No HTTP, no test client, no auth decorators - the
seam is one Python module.
"""

import json

from django.test import TestCase

from quiz.models import (
    Answer,
    Game,
    GameSession,
    Question,
    QuestionRound,
    QuestionType,
    SessionRound,
    SessionTeam,
    TeamAnswer,
)
from quiz.session_director import InvalidTransition, SessionDirector


def _build_game(num_rounds=2, questions_per_round=2):
    """A minimal game with N rounds, M questions per round, one team."""
    game = Game.objects.create(name="G")
    qt = QuestionType.objects.create(name="Free Text")
    qnum = 1
    rounds = []
    for r in range(1, num_rounds + 1):
        rnd = QuestionRound.objects.create(name=f"R{r}", round_number=r)
        rounds.append(rnd)
        for _ in range(questions_per_round):
            Question.objects.create(
                game=game,
                question_type=qt,
                question_number=qnum,
                text=f"Q{qnum}",
                total_points=10,
                game_round=rnd,
            )
            qnum += 1
    return game, rounds


def _build_session(num_rounds=2, questions_per_round=2, num_teams=2):
    game, rounds = _build_game(num_rounds, questions_per_round)
    session = GameSession.objects.create(game=game, admin_name="A")
    for r in rounds:
        SessionRound.objects.create(session=session, round=r)
    teams = [
        SessionTeam.objects.create(session=session, name=f"T{i}")
        for i in range(1, num_teams + 1)
    ]
    return session, rounds, teams


# ----------------------------------------------------------------------------
# start()
# ----------------------------------------------------------------------------


class StartTest(TestCase):
    def test_start_from_lobby_activates_first_round(self):
        session, rounds, _ = _build_session()
        result = SessionDirector(session).start()

        session.refresh_from_db()
        self.assertEqual(session.status, GameSession.Status.PLAYING)
        self.assertEqual(session.current_round_id, rounds[0].id)
        self.assertIsNotNone(session.current_question)
        self.assertIsNotNone(session.started_at)
        self.assertEqual(result["status"], "started")

        first_session_round = session.session_rounds.get(round=rounds[0])
        self.assertEqual(first_session_round.status, SessionRound.Status.ACTIVE)
        self.assertIsNotNone(first_session_round.started_at)

    def test_start_rejected_when_not_in_lobby(self):
        session, _, _ = _build_session()
        session.status = GameSession.Status.PLAYING
        session.save()
        with self.assertRaises(InvalidTransition):
            SessionDirector(session).start()

    def test_start_rejected_with_no_teams(self):
        session, _, _ = _build_session(num_teams=0)
        # _build_session(num_teams=0) still adds 0 teams since range(1,1) empty
        session.teams.all().delete()
        with self.assertRaises(InvalidTransition):
            SessionDirector(session).start()


# ----------------------------------------------------------------------------
# lock_round() -> complete_round() -> show_leaderboard() -> advance()
# ----------------------------------------------------------------------------


class LifecycleHappyPathTest(TestCase):
    def setUp(self):
        self.session, self.rounds, self.teams = _build_session(
            num_rounds=2, questions_per_round=2
        )
        SessionDirector(self.session).start()
        self.session.refresh_from_db()

    def _submit_answers_for_current_round(self):
        """Each team submits a non-empty answer for each question in the round."""
        questions = self.session.game.questions.filter(
            game_round=self.session.current_round
        )
        session_round = self.session.session_rounds.get(
            round=self.session.current_round
        )
        for team in self.teams:
            for q in questions:
                TeamAnswer.objects.create(
                    team=team,
                    question=q,
                    session_round=session_round,
                    answer_text="some answer",
                )

    def _score_all_answers_in_current_round(self, points=5):
        session_round = self.session.session_rounds.get(
            round=self.session.current_round
        )
        for ta in TeamAnswer.objects.filter(session_round=session_round):
            SessionDirector(self.session).score_answer(ta, points)

    def test_full_round_cycle(self):
        self._submit_answers_for_current_round()

        # lock
        SessionDirector(self.session).lock_round()
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.SCORING)
        sr = self.session.session_rounds.get(round=self.rounds[0])
        self.assertEqual(sr.status, SessionRound.Status.LOCKED)

        # score
        self._score_all_answers_in_current_round(points=5)
        for team in self.teams:
            team.refresh_from_db()
            # 2 questions x 5 points
            self.assertEqual(team.score, 10)

        # complete
        SessionDirector(self.session).complete_round()
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.REVIEWING)
        sr.refresh_from_db()
        self.assertEqual(sr.status, SessionRound.Status.SCORED)

        # leaderboard
        SessionDirector(self.session).show_leaderboard()
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.LEADERBOARD)

        # advance to next round
        result = SessionDirector(self.session).advance()
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.PLAYING)
        self.assertEqual(self.session.current_round_id, self.rounds[1].id)
        self.assertEqual(result["status"], "next_round")

    def test_advance_after_final_round_completes_game(self):
        # Round 1
        self._submit_answers_for_current_round()
        SessionDirector(self.session).lock_round()
        self._score_all_answers_in_current_round()
        SessionDirector(self.session).complete_round()
        SessionDirector(self.session).advance()  # -> round 2

        # Round 2
        self.session.refresh_from_db()
        self._submit_answers_for_current_round()
        SessionDirector(self.session).lock_round()
        self._score_all_answers_in_current_round()
        SessionDirector(self.session).complete_round()
        result = SessionDirector(self.session).advance()

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, GameSession.Status.COMPLETED)
        self.assertIsNotNone(self.session.completed_at)
        self.assertEqual(result["status"], "game_complete")
        self.assertEqual(len(result["standings"]), 2)


# ----------------------------------------------------------------------------
# Invalid-transition guards
# ----------------------------------------------------------------------------


class InvalidTransitionTest(TestCase):
    def setUp(self):
        self.session, self.rounds, self.teams = _build_session()

    def test_lock_round_rejected_when_round_not_active(self):
        # Session still in LOBBY, no round is ACTIVE.
        # Director.lock_round expects an ACTIVE current round.
        SessionDirector(self.session).start()
        # Now lock it - that's fine. Then try to lock again.
        # Submit something first so lock_round doesn't error elsewhere.
        sr = self.session.session_rounds.get(round=self.rounds[0])
        for team in self.teams:
            for q in self.session.game.questions.filter(game_round=self.rounds[0]):
                TeamAnswer.objects.create(
                    team=team, question=q, session_round=sr, answer_text="x"
                )
        SessionDirector(self.session).lock_round()

        with self.assertRaises(InvalidTransition):
            SessionDirector(self.session).lock_round()

    def test_complete_round_rejected_with_unscored_answers(self):
        SessionDirector(self.session).start()
        sr = self.session.session_rounds.get(round=self.rounds[0])
        for team in self.teams:
            for q in self.session.game.questions.filter(game_round=self.rounds[0]):
                TeamAnswer.objects.create(
                    team=team, question=q, session_round=sr, answer_text="x"
                )
        SessionDirector(self.session).lock_round()
        # No scoring done yet.
        with self.assertRaises(InvalidTransition) as ctx:
            SessionDirector(self.session).complete_round()
        self.assertIn("need scoring", str(ctx.exception))

    def test_show_leaderboard_rejected_outside_reviewing(self):
        with self.assertRaises(InvalidTransition):
            SessionDirector(self.session).show_leaderboard()

    def test_advance_rejected_outside_review_or_leaderboard(self):
        with self.assertRaises(InvalidTransition):
            SessionDirector(self.session).advance()


# ----------------------------------------------------------------------------
# Predicates
# ----------------------------------------------------------------------------


class AcceptsTeamJoinsTest(TestCase):
    def test_lobby_accepts(self):
        session, _, _ = _build_session()
        allowed, reason = SessionDirector(session).accepts_team_joins()
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_completed_rejects(self):
        session, _, _ = _build_session()
        session.status = GameSession.Status.COMPLETED
        session.save()
        allowed, reason = SessionDirector(session).accepts_team_joins()
        self.assertFalse(allowed)
        self.assertEqual(reason, "Game has ended")

    def test_scoring_rejects(self):
        session, _, _ = _build_session()
        session.status = GameSession.Status.SCORING
        session.save()
        allowed, reason = SessionDirector(session).accepts_team_joins()
        self.assertFalse(allowed)
        self.assertEqual(reason, "Cannot join during scoring")

    def test_late_joins_disabled_after_lobby(self):
        session, _, _ = _build_session()
        session.allow_late_joins = False
        session.status = GameSession.Status.PLAYING
        session.save()
        allowed, reason = SessionDirector(session).accepts_team_joins()
        self.assertFalse(allowed)
        self.assertEqual(reason, "Late joins not allowed")

    def test_full_session_rejects(self):
        session, _, _ = _build_session(num_teams=2)
        session.max_teams = 2
        session.save()
        allowed, reason = SessionDirector(session).accepts_team_joins()
        self.assertFalse(allowed)
        self.assertEqual(reason, "Session full")


class AcceptsAnswersForRoundTest(TestCase):
    def test_active_round_accepts(self):
        session, rounds, _ = _build_session()
        SessionDirector(session).start()
        sr = session.session_rounds.get(round=rounds[0])
        allowed, reason = SessionDirector(session).accepts_answers_for_round(sr)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_pending_round_rejects(self):
        session, rounds, _ = _build_session()
        sr = session.session_rounds.get(round=rounds[1])
        allowed, reason = SessionDirector(session).accepts_answers_for_round(sr)
        self.assertFalse(allowed)
        self.assertEqual(reason, "Round not active for answers")


# ----------------------------------------------------------------------------
# Integration: lock_round + scorer for Ranking
# ----------------------------------------------------------------------------


class LockRoundWithRankingTest(TestCase):
    """Verify the Director's lock_round drives the Scorer correctly."""

    def test_ranking_auto_scored_at_lock(self):
        game = Game.objects.create(name="G")
        qt = QuestionType.objects.create(name="Ranking")
        rnd = QuestionRound.objects.create(name="R1", round_number=1)
        q = Question.objects.create(
            game=game,
            question_type=qt,
            question_number=1,
            text="Q",
            total_points=3,
            game_round=rnd,
        )
        for i in range(1, 4):
            Answer.objects.create(question=q, display_order=i, correct_rank=i, points=1)

        session = GameSession.objects.create(game=game, admin_name="A")
        SessionRound.objects.create(session=session, round=rnd)
        team = SessionTeam.objects.create(session=session, name="T1")

        SessionDirector(session).start()
        session.refresh_from_db()
        sr = session.session_rounds.get(round=rnd)

        # Submit a perfect ranking.
        TeamAnswer.objects.create(
            team=team,
            question=q,
            session_round=sr,
            answer_text=json.dumps([1, 2, 3]),
        )

        SessionDirector(session).lock_round()

        # Per-part TeamAnswers exist and are auto-scored.
        parts = TeamAnswer.objects.filter(
            team=team, question=q, answer_part__isnull=False
        )
        self.assertEqual(parts.count(), 3)
        for pa in parts:
            self.assertEqual(pa.points_awarded, 1)

        # The combined (pre-split) TeamAnswer is gone.
        self.assertFalse(
            TeamAnswer.objects.filter(
                team=team, question=q, answer_part__isnull=True
            ).exists()
        )
