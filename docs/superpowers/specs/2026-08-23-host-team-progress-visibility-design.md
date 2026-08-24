# Design: Host Visibility into Team Answer Progress

## Problem

The host view's Team Status panel (shown while a question is live) can only
tell the host whether a team has saved *any* non-empty answer text for the
current question. For multi-part questions (Multiple Open Ended, Matching),
this means a team that has typed a single character into one of four
required blanks looks identical to a team that has filled in all four
blanks. The host has no way to tell "almost done" teams from "just
started" teams, which makes it hard to judge when it's safe to move the
group to the next question without waiting on stragglers unnecessarily.

## Goals

- Let the host see, at a glance, whether each team is not started, in
  progress, or complete on the current question.
- For multi-part questions, show how many of the required parts are filled
  in (e.g. "2/4") so the host can judge how close a team is.
- No changes to answer submission/scoring behavior. This is a read-only
  visibility improvement.

## Non-goals

- Distinguishing an explicit "submit" action from autosaved drafts. Today
  the "Submit Answer" button and autosave both call the same endpoint and
  just overwrite `TeamAnswer.answer_text` - there is no `is_submitted`
  flag in the schema. Adding one was considered, but the user confirmed
  the bigger gain is distinguishing "just started" from "essentially
  done"; the submitted-vs-complete distinction is lower value and out of
  scope for this change.
- Changing the Round Progress strip (the per-question `submitted_count /
  total_teams` summary shown across all questions in the round). That
  stays exactly as it is today. This change is scoped to the Team Status
  panel for the *current* question only, which is what the host actually
  watches to decide when to advance.
- Any change to how Ranking questions are answered. Because a Ranking
  answer is saved as a full permutation the moment a team touches it, it
  has no meaningful partial state - it will naturally render as binary
  (not started / complete) under the new logic without special-casing.

## Design

### Progress computation (backend)

In `get_session_state` (`quiz/session_api.py`), for the current question
only, compute a per-team progress status from the existing
`TeamAnswer.answer_text` - no schema changes, no new writes:

1. No `TeamAnswer` row, or `answer_text` is empty -> `not_started`.
2. Otherwise, try to JSON-parse `answer_text`:
   - If it parses to a list (this is how Multiple Open Ended, Matching,
     and Ranking already store their answers client-side): count
     non-empty (post-strip) entries against the list length.
     - 0 filled -> `not_started`
     - all filled -> `complete`
     - some filled -> `in_progress`, with `filled` / `total` counts
   - If it does not parse to a list (plain string, single-answer
     questions) -> binary: non-empty text -> `complete`, else
     `not_started`.

This single algorithm requires no per-question-type branching on the
backend and naturally produces the right granularity for every question
type:
- Multiple Open Ended / Matching: full 3-tier progress with fraction.
- Ranking: binary, because the saved array is always fully populated the
  instant a drag occurs.
- Single-answer questions: binary, because there's only one field to fill.

### API response changes

Add to each entry in the `teams` list returned by `get_session_state`:

```json
{
  "id": 1,
  "name": "...",
  "score": 10,
  "joined_late": false,
  "has_answered_current": true,
  "progress_status": "in_progress",
  "progress_filled": 2,
  "progress_total": 4
}
```

- `progress_status`: `"not_started" | "in_progress" | "complete"`.
- `progress_filled` / `progress_total`: integers when `progress_status` is
  `"in_progress"` (or `"complete"` for multi-part questions, for
  consistency); `null` when not applicable (binary questions).
- `has_answered_current` is left in place unchanged (`== progress_status ==
  "complete"`) for backward compatibility, since nothing else needs to
  change to keep working.

### Frontend changes

`renderTeamStatus` in `quiz/templates/quiz/sessions/play.html` replaces the
current `✓ Answered / ○ Not answered yet` text with an icon + color + label
driven by `progress_status`:

- ⚪ gray - "Not started"
- 🟡 amber - "In progress (2/4)" (fraction shown only when
  `progress_total` is present)
- 🟢 green - "Complete"

New CSS classes in `static/css/session.css`
(`.progress-not-started`, `.progress-in-progress`, `.progress-complete`),
following the existing color tokens already used for
`.progress-question.complete` etc., so the new indicator is visually
consistent with the existing Round Progress strip styling.

## Testing

- Backend: unit tests in `quiz/tests/test_session_api.py` covering
  `get_session_state`'s new per-team fields for:
  - No answer saved -> `not_started`.
  - Single-answer question with text -> `complete`, `progress_total` is
    `null`.
  - Multi-part question (Multiple Open Ended) with some parts filled ->
    `in_progress` with correct `filled`/`total`.
  - Multi-part question with all parts filled -> `complete`.
  - Ranking question, answered -> `complete` (never `in_progress`).
  - Malformed/non-JSON `answer_text` -> falls back to binary logic
    instead of erroring.
- Frontend: manual verification via the host view (existing Playwright
  host-flow coverage in `e2e/tests/host-flow.spec.ts` is not extended
  here, since it doesn't currently assert on team-status text; can be
  revisited separately if desired).

## Rollout notes

No migrations, no data backfill - this is purely a derived/computed view
over existing data. Safe to ship as a single change.
