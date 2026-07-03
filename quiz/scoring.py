"""
Per-question-type scoring strategies.

One Scorer adapter per QuestionType. Owns three concerns that previously
switched on QuestionType.name strings inside session_api.py:

  - is_multi_part:    does this question store one TeamAnswer per Answer part?
  - split_submission: split a JSON-array submission into per-part TeamAnswer rows
  - auto_score:       apply points_awarded where the rule is mechanical
                      (no-op for free-text types; admin scores manually)

Callers resolve a Scorer via `scorer_for(question)`. Unknown type names fall
back to SingleAnswerScorer, which is the safe default (single answer, manual
scoring).
"""

from __future__ import annotations

import json
from typing import Iterable, Protocol

from django.utils import timezone

from .models import Answer, Question, TeamAnswer

# ============================================================================
# Interface
# ============================================================================


class Scorer(Protocol):
    """Owns everything question-type-specific about lock-time behavior."""

    def is_multi_part(self, question: Question) -> bool: ...

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        """Split a JSON-array submission into per-part TeamAnswer rows.

        Only called when is_multi_part(question) is True. Returns the list of
        per-part TeamAnswer objects (created or updated). The caller is
        responsible for deleting the original combined TeamAnswer.
        """

    def auto_score(self, part_answers: list[TeamAnswer], question: Question) -> None:
        """Apply points_awarded for mechanically-scored types.

        For free-text / manual-only types this is a no-op.
        """


# ============================================================================
# Shared helpers
# ============================================================================


def _parse_json_array(answer_text: str) -> list:
    """Parse a JSON-array submission. Returns [] on any parse failure."""
    if not answer_text:
        return []
    try:
        parsed = json.loads(answer_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return [parsed] if parsed else []
    return parsed


def _split_into_parts(team_answer: TeamAnswer) -> list[TeamAnswer]:
    """Generic JSON-array split used by all multi-part types.

    Creates one TeamAnswer per Answer part, in display_order, populated from
    the corresponding array index of the original submission. Missing
    positions are stored as empty strings.
    """
    question = team_answer.question
    answer_parts = list(question.answers.order_by("display_order"))

    if not answer_parts:
        # No parts defined - nothing to split into. Caller will see the
        # original answer untouched.
        return [team_answer]

    parsed = _parse_json_array(team_answer.answer_text)

    created = []
    for idx, answer_part in enumerate(answer_parts):
        text = ""
        if idx < len(parsed) and parsed[idx] is not None:
            text = str(parsed[idx])

        part_answer, _ = TeamAnswer.objects.update_or_create(
            team=team_answer.team,
            question=question,
            answer_part=answer_part,
            defaults={
                "session_round": team_answer.session_round,
                "answer_text": text,
                "is_locked": True,
            },
        )
        created.append(part_answer)
    return created


# ============================================================================
# Adapters
# ============================================================================


class SingleAnswerScorer:
    """Default: one TeamAnswer per question, scored manually by admin."""

    def is_multi_part(self, question: Question) -> bool:
        return False

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        # Never called when is_multi_part is False, but keep a safe behavior.
        return [team_answer]

    def auto_score(self, part_answers, question: Question) -> None:
        return None


class MultipleOpenEndedScorer:
    """Multiple sub-questions, each manually scored.

    Multi-part iff at least one Answer row carries a sub-question prompt
    (Answer.text). If no prompts are defined the question behaves as a single
    open-ended answer.
    """

    def is_multi_part(self, question: Question) -> bool:
        for answer in question.answers.all():
            if answer.text and answer.text.strip():
                return True
        return False

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        return _split_into_parts(team_answer)

    def auto_score(self, part_answers, question: Question) -> None:
        return None  # admin scores manually


class RankingScorer:
    """Players place items in order. Each position correct iff the placed
    item's correct_rank equals the position (1-indexed)."""

    def is_multi_part(self, question: Question) -> bool:
        return True

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        return _split_into_parts(team_answer)

    def auto_score(self, part_answers: list[TeamAnswer], question: Question) -> None:
        # Look up the player's selected item per position by display_order.
        answers_by_display_order = {a.display_order: a for a in question.answers.all()}

        for idx, part_answer in enumerate(part_answers):
            answer_part = part_answer.answer_part
            if not answer_part:
                continue

            is_correct = False
            try:
                team_selection = (
                    int(part_answer.answer_text) if part_answer.answer_text else None
                )
            except ValueError, TypeError:
                team_selection = None

            if team_selection is not None:
                selected_item = answers_by_display_order.get(team_selection)
                if selected_item is not None:
                    expected_rank = idx + 1
                    is_correct = selected_item.correct_rank == expected_rank

            part_answer.points_awarded = answer_part.points if is_correct else 0
            part_answer.scored_at = timezone.now()
            part_answer.save()


class MatchingScorer:
    """Players type a match per prompt. Case-insensitive, whitespace-trimmed
    string equality against Answer.answer_text."""

    def is_multi_part(self, question: Question) -> bool:
        return True

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        return _split_into_parts(team_answer)

    def auto_score(self, part_answers: list[TeamAnswer], question: Question) -> None:
        for part_answer in part_answers:
            answer_part = part_answer.answer_part
            if not answer_part:
                continue

            submitted = (
                part_answer.answer_text.strip().lower()
                if part_answer.answer_text
                else ""
            )
            correct = (
                answer_part.answer_text.strip().lower()
                if answer_part.answer_text
                else ""
            )
            is_correct = submitted == correct

            part_answer.points_awarded = answer_part.points if is_correct else 0
            part_answer.scored_at = timezone.now()
            part_answer.save()


# ============================================================================
# Registry
# ============================================================================


_REGISTRY: dict[str, Scorer] = {
    "Ranking": RankingScorer(),
    "Matching": MatchingScorer(),
    "Multiple Open Ended": MultipleOpenEndedScorer(),
}

_DEFAULT: Scorer = SingleAnswerScorer()


def scorer_for(question: Question) -> Scorer:
    """Resolve the Scorer for a question's QuestionType.

    Falls back to SingleAnswerScorer when the question has no type, or when
    the type name is not in the registry. This keeps unknown / renamed types
    in a safe state (one answer, admin scores manually) rather than silently
    auto-scoring wrong.
    """
    if not question.question_type:
        return _DEFAULT
    return _REGISTRY.get(question.question_type.name, _DEFAULT)
