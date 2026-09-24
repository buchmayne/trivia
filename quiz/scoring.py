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


def multi_part_answer_summary(
    question: Question, part_answers: Iterable[TeamAnswer]
) -> dict:
    """Fold a team's per-part TeamAnswer rows into a scoring/display summary.

    Used by both the admin scoring view (which needs per-part detail: text,
    points_awarded, max_points per Answer part) and the team's own answers
    view (which folds these into one combined answer_text + one lock/score
    status). Callers decide *whether* a question's answers are currently
    split into parts (that differs: admin checks the question type via
    scorer_for; the team view checks whether split rows exist yet, since a
    round isn't split until it's locked) - this only does the aggregation
    once that's known.

    Returns:
        parts: one dict per Answer part, in display_order, with
            answer_part_id, team_answer_id (None if not yet submitted),
            answer_text, points_awarded, max_points, is_scored.
        is_scored: True iff every part has points_awarded set.
        total_points_awarded: sum of points_awarded, or None if not all
            parts are scored yet.
        is_locked: True if any part's TeamAnswer row is locked.
    """
    answer_parts = list(question.answers.order_by("display_order"))
    part_lookup = {pa.answer_part_id: pa for pa in part_answers}

    parts = []
    total_points_awarded = 0
    all_scored = True
    any_locked = False

    for answer_part in answer_parts:
        part_answer = part_lookup.get(answer_part.id)
        if part_answer:
            parts.append(
                {
                    "answer_part_id": answer_part.id,
                    "team_answer_id": part_answer.id,
                    "answer_text": part_answer.answer_text,
                    "points_awarded": part_answer.points_awarded,
                    "max_points": answer_part.points,
                    "is_scored": part_answer.points_awarded is not None,
                }
            )
            if part_answer.points_awarded is not None:
                total_points_awarded += part_answer.points_awarded
            else:
                all_scored = False
            if part_answer.is_locked:
                any_locked = True
        else:
            parts.append(
                {
                    "answer_part_id": answer_part.id,
                    "team_answer_id": None,
                    "answer_text": "",
                    "points_awarded": None,
                    "max_points": answer_part.points,
                    "is_scored": False,
                }
            )
            all_scored = False

    return {
        "parts": parts,
        "is_scored": all_scored,
        "total_points_awarded": total_points_awarded if all_scored else None,
        "is_locked": any_locked,
    }


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

    Multi-part iff at least one Answer row has content that requires user input:
    - A sub-question prompt (Answer.text), OR
    - Question media (image/video), OR
    - A correct answer (Answer.answer_text) - implies evaluation needed

    If none of these are present, the question behaves as a single open-ended answer.
    """

    def is_multi_part(self, question: Question) -> bool:
        for answer in question.answers.all():
            has_prompt = answer.text and answer.text.strip()
            has_media = answer.question_image_url or answer.question_video_url
            has_answer = answer.answer_text and answer.answer_text.strip()
            if has_prompt or has_media or has_answer:
                return True
        return False

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        return _split_into_parts(team_answer)

    def auto_score(self, part_answers, question: Question) -> None:
        return None  # admin scores manually


class RankingScorer:
    """Players place items in order.

    Submission contract: a JSON array of Answer IDs in the player's ranked
    order (element p = the item the player placed at position p+1). This is
    self-describing and immune to display_order changes or per-team item
    shuffling.

    After the split, each item's TeamAnswer part stores the 1-based position
    the player assigned to that item, so a part is correct iff its stored
    position equals the item's correct_rank.

    Legacy format (before this contract): a JSON array of 0-based indices
    into the display-ordered item list. Recognized by the presence of a 0
    (Answer PKs start at 1; every full legacy permutation contains 0) and
    converted so pre-deploy submissions still grade correctly.
    """

    def is_multi_part(self, question: Question) -> bool:
        return True

    def split_submission(self, team_answer: TeamAnswer) -> list[TeamAnswer]:
        question = team_answer.question
        answer_parts = list(question.answers.order_by("display_order"))

        if not answer_parts:
            # No parts defined - nothing to split into. Caller will see the
            # original answer untouched.
            return [team_answer]

        positions_by_item = self._positions_by_item(
            team_answer.answer_text, answer_parts
        )

        created = []
        for answer_part in answer_parts:
            position = positions_by_item.get(answer_part.id)
            part_answer, _ = TeamAnswer.objects.update_or_create(
                team=team_answer.team,
                question=question,
                answer_part=answer_part,
                defaults={
                    "session_round": team_answer.session_round,
                    "answer_text": "" if position is None else str(position),
                    "is_locked": True,
                },
            )
            created.append(part_answer)
        return created

    def auto_score(self, part_answers: list[TeamAnswer], question: Question) -> None:
        for part_answer in part_answers:
            answer_part = part_answer.answer_part
            if not answer_part:
                continue

            try:
                placed_at = (
                    int(part_answer.answer_text) if part_answer.answer_text else None
                )
            except (ValueError, TypeError):
                placed_at = None

            is_correct = (
                placed_at is not None
                and answer_part.correct_rank is not None
                and placed_at == answer_part.correct_rank
            )

            part_answer.points_awarded = answer_part.points if is_correct else 0
            part_answer.scored_at = timezone.now()
            part_answer.save()

    @staticmethod
    def _positions_by_item(answer_text: str, answer_parts: list) -> dict[int, int]:
        """Map each Answer ID to the 1-based position the player placed it at.

        Accepts both the current format (ranked Answer IDs) and the legacy
        0-based-index format. Unresolvable entries (unknown IDs, non-ints)
        are ignored: the affected item is treated as unanswered.
        """
        parsed = _parse_json_array(answer_text)

        values = []
        for value in parsed:
            try:
                values.append(int(value))
            except (ValueError, TypeError):
                continue

        if 0 in values:
            # Legacy: element p = 0-based index of the item placed at
            # position p+1.
            id_by_index = [part.id for part in answer_parts]
            return {
                id_by_index[idx]: pos + 1
                for pos, idx in enumerate(values)
                if 0 <= idx < len(id_by_index)
            }

        # Current: element p = Answer ID placed at position p+1.
        return {item_id: pos + 1 for pos, item_id in enumerate(values) if item_id > 0}


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
