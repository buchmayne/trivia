# Refactor plan: Session lifecycle and per-type scoring

This plan implements Candidates 1 and 2 from the architecture review
(`/var/folders/.../architecture-review-20260523-162824.html`).

## Goals

- One module owns the GameSession state machine (`SessionDirector`).
- One module owns question-type-specific behavior (`Scorer`, with one adapter per type).
- `quiz/session_api.py` views become thin: parse, dispatch, serialize.
- Existing tests pass unchanged. Behavior is preserved.

## Non-goals

- No change to data model, URLs, or HTTP contracts.
- No change to auth decorators (`require_admin_token`, `require_team_token`).
- No change to template/JS frontend.

## Phase order

Scorer first, Director second. The Director's `lock_round` calls the Scorer,
so building Scorer first lets each phase land independently with green tests.

---

## Phase A: Scorer (Candidate 2)

### A1. Create `quiz/scoring.py`

- `Scorer` protocol / abstract base with:
  - `is_multi_part(question) -> bool`
  - `split_submission(team_answer) -> list[TeamAnswer]`
  - `auto_score(part_answers, question) -> None`
- Adapters:
  - `RankingScorer`
  - `MatchingScorer`
  - `MultipleOpenEndedScorer` (multi-part iff sub-question prompts present; no auto-score)
  - `SingleAnswerScorer` (default for everything else)
- Registry: `scorer_for(question) -> Scorer`, keyed by `question.question_type.name`.
- Unknown type name falls back to `SingleAnswerScorer`.

### A2. Move bodies of the three private helpers

From `quiz/session_api.py`:
- `_is_multi_part_question` -> `is_multi_part` on each adapter
- `_split_answer_into_parts` -> `RankingScorer.split_submission` / `MatchingScorer.split_submission` / `MultipleOpenEndedScorer.split_submission` (shared implementation, since they all parse the same JSON-array submission)
- `_auto_score_ranking_matching` -> `RankingScorer.auto_score` / `MatchingScorer.auto_score`

Behavior must remain byte-identical. The Ranking/Matching split logic and
correctness rules are copied verbatim.

### A3. Wire `admin_lock_round` to use the scorer

Replace the `if is_multi_part:` / `if question_type in ["Ranking", "Matching"]`
ladder with a single call:

```python
scorer = scorer_for(question)
if scorer.is_multi_part(question):
    ...
    scorer.auto_score(part_answers, question)
```

Also wire `_is_multi_part_question` call sites in `admin_get_scoring_data` and
the `admin_score_answer` per-part-max-points calc.

### A4. Tests

New `quiz/tests/test_scoring.py`:
- `RankingScorer.auto_score` correctness (3 cases: all correct, partial, none).
- `MatchingScorer.auto_score` correctness (case-insensitive, whitespace strip).
- `MultipleOpenEndedScorer.is_multi_part` depends on `Answer.text` presence.
- `SingleAnswerScorer.is_multi_part` is always False.
- `scorer_for` resolution and unknown-type fallback.

### A5. Delete old helpers

Remove `_is_multi_part_question`, `_split_answer_into_parts`,
`_auto_score_ranking_matching` from `session_api.py`.

### A6. Run full test suite

`uv run manage.py test quiz`

---

## Phase B: SessionDirector (Candidate 1)

### B1. Create `quiz/session_director.py`

```python
class InvalidTransition(Exception):
    """Raised when a lifecycle method is called from an illegal state."""

class SessionDirector:
    def __init__(self, session: GameSession): ...

    # transitions
    def start(self) -> dict: ...
    def set_current_question(self, question_id: int) -> dict: ...
    def lock_round(self) -> dict: ...
    def score_answer(self, *, team_answer=None, team_id=None,
                     question_id=None, answer_part_id=None,
                     points: int) -> dict: ...
    def complete_round(self) -> dict: ...
    def show_leaderboard(self) -> dict: ...
    def advance(self) -> dict: ...   # next round or COMPLETED

    # predicates - replace scattered status string compares
    def accepts_team_joins(self) -> tuple[bool, str | None]: ...
    def accepts_answers_for_round(self, session_round) -> tuple[bool, str | None]: ...
```

Transitions raise `InvalidTransition` with a message on bad state. They return
a dict the view can serialize directly (matching today's JSON shapes).

### B2. Move transition bodies from views

For each admin view, move the state-mutation body into the corresponding
director method. Keep the view's other concerns (auth, JSON parsing, points
validation, HTTP shaping) where they are.

Mapping:
- `admin_start_game` -> `director.start()`
- `admin_set_question` -> `director.set_current_question(qid)`
- `admin_lock_round` -> `director.lock_round()`
- `admin_score_answer` -> `director.score_answer(...)`
- `admin_complete_round` -> `director.complete_round()`
- `admin_show_leaderboard` -> `director.show_leaderboard()`
- `admin_start_next_round` -> `director.advance()`

### B3. Wire predicates in non-admin views

- `join_session`: replace the three `session.status == ...` checks with
  `accepts, reason = director.accepts_team_joins(); if not accepts: ...`.
- `team_submit_answer`: replace the `if session_round.status != ACTIVE` check
  with `director.accepts_answers_for_round(session_round)`.

### B4. Tests

New `quiz/tests/test_session_director.py`:
- Each transition: happy path + invalid-state raises `InvalidTransition`.
- `lock_round` integration with `Scorer` for one Ranking question.
- `advance` from REVIEWING to next round; from final round to COMPLETED.
- `accepts_team_joins` truth table across all statuses.

Tests construct a `GameSession` directly and call the director. No HTTP.

### B5. Run full test suite

`uv run manage.py test quiz`

---

## Phase C: Cleanup

- Confirm no inline `session.status == GameSession.Status.X` comparisons remain
  in `session_api.py` outside of `validate_session_access` and `rejoin_session`
  (those are auth-shaped, not lifecycle-shaped).
- Line count check: target `session_api.py` < 1100 lines (was 1509).
- Run `uv run black .` to format.

## Risk register

- **Behavior drift in Ranking/Matching auto-score**: mitigated by copying logic
  verbatim and the 10 existing lock-round tests.
- **Status transitions in `pause`/`resume`**: keep on the `GameSession` model
  for now. Director defers to model methods. Revisit later.
- **`admin_score_answer` is large**: it has four lookup branches plus team
  total recompute. The director owns the scoring + total recompute; the view
  keeps the lookup-branching (it's HTTP-input-shaped concern).

## Done when

- All existing tests pass.
- New tests in `test_scoring.py` and `test_session_director.py` pass.
- `session_api.py` no longer contains `_is_multi_part_question`,
  `_split_answer_into_parts`, `_auto_score_ranking_matching`.
- Admin view bodies are noticeably thinner: parse + call director + serialize.
