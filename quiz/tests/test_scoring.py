"""
Unit tests for quiz.scoring.

These tests exercise the Scorer adapters directly. They do not go through
HTTP, view auth, or transactions. The interface under test is is_multi_part,
split_submission, auto_score, and scorer_for resolution.
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
from quiz.scoring import (
    MatchingScorer,
    MultipleOpenEndedScorer,
    RankingScorer,
    SingleAnswerScorer,
    scorer_for,
)


def _fixture(question_type_name, *, with_answer_text=False, with_prompts=False):
    """Build a minimal Game/Question/Round/Session/Team and return the lot."""
    qt = QuestionType.objects.create(name=question_type_name)
    game = Game.objects.create(name=f"G-{question_type_name}")
    round_ = QuestionRound.objects.create(name="R1", round_number=1)
    question = Question.objects.create(
        game=game,
        question_type=qt,
        question_number=1,
        text="Q",
        total_points=3,
        game_round=round_,
    )
    # Three parts/items, points 1 each, correct_rank 1..3 in display order.
    for i in range(1, 4):
        Answer.objects.create(
            question=question,
            text=f"prompt-{i}" if with_prompts else None,
            answer_text=f"correct-{i}" if with_answer_text else None,
            display_order=i,
            correct_rank=i,
            points=1,
        )
    session = GameSession.objects.create(game=game, admin_name="A")
    session_round = SessionRound.objects.create(session=session, round=round_)
    team = SessionTeam.objects.create(session=session, name="T1")
    return question, session_round, team


# ----------------------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------------------


class ScorerForTest(TestCase):
    def test_resolves_ranking(self):
        qt = QuestionType.objects.create(name="Ranking")
        game = Game.objects.create(name="G")
        q = Question.objects.create(
            game=game, question_type=qt, question_number=1, text="?"
        )
        self.assertIsInstance(scorer_for(q), RankingScorer)

    def test_resolves_matching(self):
        qt = QuestionType.objects.create(name="Matching")
        game = Game.objects.create(name="G")
        q = Question.objects.create(
            game=game, question_type=qt, question_number=1, text="?"
        )
        self.assertIsInstance(scorer_for(q), MatchingScorer)

    def test_resolves_multiple_open_ended(self):
        qt = QuestionType.objects.create(name="Multiple Open Ended")
        game = Game.objects.create(name="G")
        q = Question.objects.create(
            game=game, question_type=qt, question_number=1, text="?"
        )
        self.assertIsInstance(scorer_for(q), MultipleOpenEndedScorer)

    def test_unknown_type_falls_back_to_single(self):
        qt = QuestionType.objects.create(name="Fictional Type")
        game = Game.objects.create(name="G")
        q = Question.objects.create(
            game=game, question_type=qt, question_number=1, text="?"
        )
        self.assertIsInstance(scorer_for(q), SingleAnswerScorer)


# ----------------------------------------------------------------------------
# is_multi_part predicates
# ----------------------------------------------------------------------------


class IsMultiPartTest(TestCase):
    def test_ranking_is_always_multi_part(self):
        q, _, _ = _fixture("Ranking")
        self.assertTrue(RankingScorer().is_multi_part(q))

    def test_matching_is_always_multi_part(self):
        q, _, _ = _fixture("Matching")
        self.assertTrue(MatchingScorer().is_multi_part(q))

    def test_multiple_open_ended_multi_part_iff_prompts_present(self):
        q_with, _, _ = _fixture("Multiple Open Ended", with_prompts=True)
        q_without, _, _ = _fixture("Multiple Open Ended", with_prompts=False)
        self.assertTrue(MultipleOpenEndedScorer().is_multi_part(q_with))
        self.assertFalse(MultipleOpenEndedScorer().is_multi_part(q_without))

    def test_single_answer_never_multi_part(self):
        q, _, _ = _fixture("Free Text")
        self.assertFalse(SingleAnswerScorer().is_multi_part(q))


# ----------------------------------------------------------------------------
# RankingScorer.auto_score
# ----------------------------------------------------------------------------


class RankingScorerAutoScoreTest(TestCase):
    def _submit_ranking(self, question, session_round, team, placements):
        """Create the unsplit TeamAnswer that the player would submit.

        placements is the player's array: index = position, value = the
        display_order of the item placed at that position.
        """
        ta = TeamAnswer.objects.create(
            team=team,
            question=question,
            session_round=session_round,
            answer_text=json.dumps(placements),
        )
        return RankingScorer().split_submission(ta)

    def test_all_correct(self):
        q, sr, t = _fixture("Ranking")
        # Item with display_order=1 has correct_rank=1, place it at position 1, etc.
        parts = self._submit_ranking(q, sr, t, [1, 2, 3])
        RankingScorer().auto_score(parts, q)
        for pa in parts:
            self.assertEqual(pa.points_awarded, 1)

    def test_all_wrong(self):
        q, sr, t = _fixture("Ranking")
        parts = self._submit_ranking(q, sr, t, [3, 1, 2])
        RankingScorer().auto_score(parts, q)
        for pa in parts:
            self.assertEqual(pa.points_awarded, 0)

    def test_partial_credit(self):
        q, sr, t = _fixture("Ranking")
        # Position 1 correct (item 1, rank 1); position 2 wrong; position 3 wrong.
        parts = self._submit_ranking(q, sr, t, [1, 3, 2])
        RankingScorer().auto_score(parts, q)
        scored = sorted(parts, key=lambda p: p.answer_part.display_order)
        self.assertEqual([p.points_awarded for p in scored], [1, 0, 0])

    def test_missing_position_scores_zero(self):
        q, sr, t = _fixture("Ranking")
        parts = self._submit_ranking(q, sr, t, [1])  # only one placement
        RankingScorer().auto_score(parts, q)
        scored = sorted(parts, key=lambda p: p.answer_part.display_order)
        self.assertEqual([p.points_awarded for p in scored], [1, 0, 0])


# ----------------------------------------------------------------------------
# MatchingScorer.auto_score
# ----------------------------------------------------------------------------


class MatchingScorerAutoScoreTest(TestCase):
    def _submit(self, question, session_round, team, submissions):
        ta = TeamAnswer.objects.create(
            team=team,
            question=question,
            session_round=session_round,
            answer_text=json.dumps(submissions),
        )
        return MatchingScorer().split_submission(ta)

    def test_exact_match_all(self):
        q, sr, t = _fixture("Matching", with_answer_text=True)
        parts = self._submit(q, sr, t, ["correct-1", "correct-2", "correct-3"])
        MatchingScorer().auto_score(parts, q)
        for pa in parts:
            self.assertEqual(pa.points_awarded, 1)

    def test_case_insensitive_and_whitespace_trimmed(self):
        q, sr, t = _fixture("Matching", with_answer_text=True)
        parts = self._submit(q, sr, t, ["  CORRECT-1  ", "Correct-2", "correct-3"])
        MatchingScorer().auto_score(parts, q)
        for pa in parts:
            self.assertEqual(pa.points_awarded, 1)

    def test_wrong_matches_get_zero(self):
        q, sr, t = _fixture("Matching", with_answer_text=True)
        parts = self._submit(q, sr, t, ["wrong", "correct-2", "also wrong"])
        MatchingScorer().auto_score(parts, q)
        scored = sorted(parts, key=lambda p: p.answer_part.display_order)
        self.assertEqual([p.points_awarded for p in scored], [0, 1, 0])


# ----------------------------------------------------------------------------
# split_submission shape
# ----------------------------------------------------------------------------


class SplitSubmissionTest(TestCase):
    def test_creates_one_team_answer_per_part(self):
        q, sr, t = _fixture("Ranking")
        ta = TeamAnswer.objects.create(
            team=t,
            question=q,
            session_round=sr,
            answer_text=json.dumps([2, 1, 3]),
        )
        parts = RankingScorer().split_submission(ta)
        self.assertEqual(len(parts), 3)
        # Each part is locked and links to a distinct Answer part.
        for pa in parts:
            self.assertTrue(pa.is_locked)
            self.assertIsNotNone(pa.answer_part)

    def test_malformed_json_yields_empty_part_texts(self):
        q, sr, t = _fixture("Ranking")
        ta = TeamAnswer.objects.create(
            team=t, question=q, session_round=sr, answer_text="not-json"
        )
        parts = RankingScorer().split_submission(ta)
        self.assertEqual(len(parts), 3)
        for pa in parts:
            self.assertEqual(pa.answer_text, "")
