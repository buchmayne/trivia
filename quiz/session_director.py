"""
SessionDirector: owns the GameSession lifecycle state machine.

The state graph the Director enforces:

    LOBBY --start--> PLAYING
    PLAYING --lock_round--> SCORING
    SCORING --complete_round--> REVIEWING
    REVIEWING --show_leaderboard--> LEADERBOARD
    {REVIEWING, LEADERBOARD} --advance--> PLAYING (next round)
                            --advance--> COMPLETED (no more rounds)

PAUSED is handled by GameSession.pause/resume directly; it is orthogonal to
the lifecycle and the Director defers to the model for it.

Transitions raise InvalidTransition with a human-readable reason when called
from an illegal state. Views translate that to HTTP 400.

Predicates (accepts_team_joins, accepts_answers_for_round) let non-admin
views ask the Director instead of re-deriving the rules with inline status
string compares.
"""

from __future__ import annotations

from typing import Optional

from django.db import models, transaction
from django.utils import timezone

from .models import (
    GameSession,
    Question,
    SessionRound,
    SessionTeam,
    TeamAnswer,
)
from .scoring import scorer_for


class InvalidTransition(Exception):
    """Raised when a lifecycle method is called from an illegal state."""


class SessionDirector:
    """One module, one interface, owning all GameSession state transitions."""

    def __init__(self, session: GameSession):
        self.session = session

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def start(self) -> dict:
        """LOBBY -> PLAYING. Activates the first round and sets current question."""
        session = self.session
        if session.status != GameSession.Status.LOBBY:
            raise InvalidTransition("Game already started")
        if session.teams.count() < 1:
            raise InvalidTransition("Need at least 1 team")

        first_session_round = session.session_rounds.first()
        if not first_session_round:
            raise InvalidTransition("No rounds found in game")

        first_question = (
            session.game.questions.filter(game_round=first_session_round.round)
            .order_by("question_number")
            .first()
        )

        session.status = GameSession.Status.PLAYING
        session.current_round = first_session_round.round
        session.current_question = first_question
        session.started_at = timezone.now()
        session.save()

        first_session_round.status = SessionRound.Status.ACTIVE
        first_session_round.started_at = timezone.now()
        first_session_round.save()

        return {
            "status": "started",
            "current_question_id": first_question.id if first_question else None,
        }

    def set_current_question(self, question: Question) -> dict:
        """Admin navigates to a specific question.

        Allowed when the question's round is non-PENDING. In REVIEWING mode,
        restricted to the current round.
        """
        session = self.session
        session_round = session.session_rounds.filter(round=question.game_round).first()
        if not session_round or session_round.status == SessionRound.Status.PENDING:
            raise InvalidTransition("Question not in active round")

        if (
            session.status == GameSession.Status.REVIEWING
            and question.game_round != session.current_round
        ):
            raise InvalidTransition(
                "Can only navigate within current round in review mode"
            )

        session.current_question = question
        session.current_round = question.game_round
        session.save()

        return {
            "status": "ok",
            "question_id": question.id,
            "question_number": question.question_number,
        }

    @transaction.atomic
    def lock_round(self) -> dict:
        """PLAYING -> SCORING. Splits multi-part answers, auto-scores where
        the question type's Scorer is mechanical, fills 0s for missing
        submissions, locks all TeamAnswers in the round."""
        session = self.session
        session_round = session.session_rounds.get(round=session.current_round)

        if session_round.status != SessionRound.Status.ACTIVE:
            raise InvalidTransition("Round not active")

        questions_in_round = session.game.questions.filter(
            game_round=session.current_round
        ).prefetch_related("answers", "question_type")

        teams = list(session.teams.order_by("id"))

        for question in questions_in_round:
            scorer = scorer_for(question)
            is_multi_part = scorer.is_multi_part(question)

            for team in teams:
                existing = TeamAnswer.objects.filter(
                    team=team, question=question, answer_part__isnull=True
                ).first()

                if is_multi_part:
                    if existing:
                        part_answers = scorer.split_submission(existing)
                        scorer.auto_score(part_answers, question)
                        existing.delete()
                    else:
                        # No submission: create 0-point placeholders per part.
                        for answer_part in question.answers.order_by("display_order"):
                            TeamAnswer.objects.create(
                                team=team,
                                question=question,
                                answer_part=answer_part,
                                session_round=session_round,
                                answer_text="",
                                is_locked=True,
                                points_awarded=0,
                                scored_at=timezone.now(),
                            )
                else:
                    if existing:
                        existing.is_locked = True
                        existing.save(update_fields=["is_locked"])
                    else:
                        TeamAnswer.objects.create(
                            team=team,
                            question=question,
                            session_round=session_round,
                            answer_text="",
                            is_locked=True,
                            points_awarded=0,
                            scored_at=timezone.now(),
                        )

        session_round.status = SessionRound.Status.LOCKED
        session_round.locked_at = timezone.now()
        session_round.save()

        session.status = GameSession.Status.SCORING
        session.save()

        return {"status": "locked"}

    def score_answer(self, answer: TeamAnswer, points: int) -> dict:
        """Award points to a single TeamAnswer and recompute the team total.

        The view is responsible for resolving the TeamAnswer (the lookup has
        four input shapes) and validating the points range against either
        answer_part.points or question.total_points.
        """
        answer.points_awarded = points
        answer.scored_at = timezone.now()
        answer.save()

        team = answer.team
        team.score = (
            team.answers.filter(points_awarded__isnull=False).aggregate(
                total=models.Sum("points_awarded")
            )["total"]
            or 0
        )
        team.save()

        question_total = (
            TeamAnswer.objects.filter(
                team=team,
                question=answer.question,
                points_awarded__isnull=False,
            ).aggregate(total=models.Sum("points_awarded"))["total"]
            or 0
        )

        return {
            "team_answer_id": answer.id,
            "answer_part_id": answer.answer_part_id,
            "points_awarded": points,
            "question_total": question_total,
            "team_score": team.score,
        }

    def complete_round(self) -> dict:
        """SCORING -> REVIEWING. All answers must be scored before this fires.
        Resets current_question to the first question of the round for review."""
        session = self.session
        session_round = session.session_rounds.get(round=session.current_round)

        unscored = TeamAnswer.objects.filter(
            session_round=session_round,
            points_awarded__isnull=True,
        ).count()
        if unscored > 0:
            raise InvalidTransition(f"{unscored} answers still need scoring")

        session_round.status = SessionRound.Status.SCORED
        session_round.scored_at = timezone.now()
        session_round.save()

        session.status = GameSession.Status.REVIEWING
        session.current_question = (
            session.game.questions.filter(game_round=session.current_round)
            .order_by("question_number")
            .first()
        )
        session.save()

        return {
            "status": "reviewing",
            "round_number": session.current_round.round_number,
            "round_name": session.current_round.name,
        }

    def show_leaderboard(self) -> dict:
        """REVIEWING -> LEADERBOARD."""
        session = self.session
        if session.status != GameSession.Status.REVIEWING:
            raise InvalidTransition("Not in review mode")
        session.status = GameSession.Status.LEADERBOARD
        session.save()
        return {"status": "leaderboard"}

    def advance(self) -> dict:
        """{REVIEWING, LEADERBOARD} -> PLAYING (next round) or -> COMPLETED."""
        session = self.session
        if session.status not in [
            GameSession.Status.REVIEWING,
            GameSession.Status.LEADERBOARD,
        ]:
            raise InvalidTransition("Not in review or leaderboard mode")

        next_session_round = (
            session.session_rounds.filter(
                round__round_number__gt=session.current_round.round_number,
                status=SessionRound.Status.PENDING,
            )
            .order_by("round__round_number")
            .first()
        )

        if next_session_round:
            next_session_round.status = SessionRound.Status.ACTIVE
            next_session_round.started_at = timezone.now()
            next_session_round.save()

            first_question = (
                session.game.questions.filter(game_round=next_session_round.round)
                .order_by("question_number")
                .first()
            )

            session.status = GameSession.Status.PLAYING
            session.current_round = next_session_round.round
            session.current_question = first_question
            session.save()

            return {
                "status": "next_round",
                "round_number": next_session_round.round.round_number,
                "round_name": next_session_round.round.name,
            }

        # No more rounds: game over.
        session.status = GameSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save()

        standings = [
            {"rank": i + 1, "name": t.name, "score": t.score}
            for i, t in enumerate(session.teams.order_by("-score"))
        ]
        return {"status": "game_complete", "standings": standings}

    # ------------------------------------------------------------------
    # Predicates - for non-admin views that need to ask the lifecycle
    # whether something is allowed, without owning the rule.
    # ------------------------------------------------------------------

    def accepts_team_joins(self) -> tuple[bool, Optional[str]]:
        """Whether a new team may join right now. Returns (allowed, reason)."""
        session = self.session
        if session.status == GameSession.Status.COMPLETED:
            return False, "Game has ended"
        if session.status == GameSession.Status.SCORING:
            return False, "Cannot join during scoring"
        if not session.allow_late_joins and session.status != GameSession.Status.LOBBY:
            return False, "Late joins not allowed"
        if session.teams.count() >= session.max_teams:
            return False, "Session full"
        return True, None

    def accepts_answers_for_round(
        self, session_round: SessionRound
    ) -> tuple[bool, Optional[str]]:
        """Whether a team may submit/update an answer in the given round."""
        if session_round.status != SessionRound.Status.ACTIVE:
            return False, "Round not active for answers"
        return True, None
