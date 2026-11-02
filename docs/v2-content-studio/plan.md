# V2 content studio — implementation plan

Source of truth: [spec.md](spec.md). This plan builds **only a local, parallel experiment**. Do not convert old content, alter `quiz` models/admin/API/fixtures, deploy to production, implement live play, or create commits. Each task is a reviewable vertical slice; after each, run the new app's tests and make sure the legacy suite still runs before the next slice.

## Shared decisions and verification baseline

- New Django app `studio`, separate v2 tables and `/studio/` routes. Route access requires `DEBUG` **and** a separate opt-in setting, plus authenticated staff or existing game-admin permission. `studio` must not appear in `quiz/management/commands/export_content.py`, `quiz/management/commands/seed_db.py`, or `quiz/fixtures/content.json`. Use a separate local-file storage namespace for v2 media; do not instantiate legacy S3 fields.
- Domain services own writes/validation; forms/views are adapters. Use stable task format codes; evaluation keys are validated small JSON objects referencing relational response items. Preview projections for question and reveal are separate. `Challenge` is library content, `Task` is the answerable unit, and `Placement` connects challenges to games. Challenges may be reused without copying them.
- Consult `quiz/models.py`, `quiz/admin.py`, `quiz/session_api.py`, `quiz/scoring.py`, `quiz/fields.py`, `pub_trivia/settings.py`, `pub_trivia/urls.py`, `quiz/tests/`, and `docs/CONTENT_WORKFLOW.md` for existing patterns and regression risks. Keep new code within the bounded `studio` app where possible.
- Unless otherwise noted, verify after each task with `uv run manage.py test studio` and `uv run manage.py makemigrations --check --dry-run`; after tasks affecting project wiring also run `uv run manage.py check`. The final task runs `uv run manage.py test quiz studio`. These commands require the repo's configured local PostgreSQL/test environment; do not point them at production.

## 1. Isolated studio and quick-capture inbox

**Goal:** Be able to save a rough idea immediately without opening Django admin or creating a game.

**Context / files:** `docs/v2-content-studio/spec.md` (Requirements 1, 8; Experiment isolation), `pub_trivia/settings.py`, `pub_trivia/urls.py`, `quiz/models.py` (auth profile only). New `studio/models.py`, migration, views/templates/URLs, domain operations, and tests.

**Approach:** Add only v2 `Category` and `Challenge` at first, with draft/ready state and timestamps; drafts require a title or notes, category can be unset. Provide an authorized, development-opt-in library page with quick capture, editing, category creation, search, and status/category filters. Marking Ready is unavailable until task validation exists. Keep v2 outside legacy export/seed. Gate both route registration and write access (not merely navigation links).

**Acceptance criteria:** An authorized developer captures an idea with only a title or only notes and can find/edit it later; empty input is rejected without losing entered values. Unauthenticated/unauthorized users cannot read or write studio content. Routes are unavailable with opt-in off or `DEBUG=False`. No legacy content or fixture changes.

**Verify:** Baseline commands above; `uv run manage.py test studio` includes route-gate/auth and draft CRUD tests. With opt-in enabled in the local development environment, run `uv run manage.py runserver` and capture/re-find an idea at `/studio/`. Test route denial with settings overrides.

## 2. First complete challenge: free-text task and text-only previews

**Goal:** Author and preview a usable one-task challenge without groups, choices, or media.

**Context / files:** Spec (Requirements 2, 3, 5, 7; `Task`/`ContentBlock`; Preview contract). New `studio` models, migration, validation/projection services, editor views/templates, and tests.

**Approach:** Add `Task` and ordered text `ContentBlock`s scoped to a challenge/task and prompt/reveal phase. Support free-text format with `{"reference_text": "..."}`. Provide add/edit/reorder task and text-block controls and separate question/reveal projections. A draft stays incomplete if necessary; each save as Ready checks category, at least one task, presentable prompt, positive task points, and nonblank reference answer. Challenge maximum is computed from tasks, never stored. Keep group/item owner fields extendable in later tasks.

**Acceptance criteria:** A single-task challenge can be marked Ready, its question preview excludes the reference answer and reveal blocks, and its reveal preview shows the answer plus optional explanation. A draft with missing data saves; an invalid Ready save reports specific fields and does not persist Ready state. Two differently formatted tasks can ultimately coexist without a new challenge type.

**Verify:** Baseline commands; tests for draft/Ready transitions, computed points, prompt vs reveal payloads, and invalid reference/prompt. Exercise one full draft-to-preview workflow in the browser.

## 3. Reusable-game assembly (text-only)

**Goal:** Prove the core library/game boundary before implementing more response formats.

**Context / files:** Spec (Requirements 5–7; `Game`, `GameRound`, `Placement`; Game builder). New `studio` models/migration, assembly operations, pages/projections, and tests.

**Approach:** Create independent games and ordered per-game rounds/placements. Library search selects Ready challenges; initial placement validates Ready. Provide add/remove/reorder and derived game-wide question numbers, informational category coverage, and ordered game question/reveal preview. Populate library “last used” from latest placement creation timestamp. A subsequent edit of the same challenge is reflected in all game previews; a later-draft challenge should preview with a visible incomplete warning rather than crashing.

**Acceptance criteria:** One challenge appears in two different games with different round/question positions and a single category; changing its content changes both previews without copying it. No categories are required in game assembly. Number/order and last-use data are correct after placement changes.

**Verify:** Baseline commands; tests for two-game reuse, ordering/numbering, category coverage, last-use, placement validation, and edit propagation. Manually assemble a two-round game from existing Ready challenges.

## 4. Choose-one answers with structured options

**Goal:** Author the idiom-style challenge: one shared instruction and multiple tasks, each with its own choices.

**Context / files:** Spec (Requirements 2–4; `ResponsePool`, `ResponseItem`, single-choice evaluation key). New `studio` models/migration, task editor controls, validation/projections, tests.

**Approach:** Add task-local response pools and ordered items with prompt/reveal text blocks. Each choose-one task has a pool with at least two items and `{"correct_item_id": <item ID>}`; validate item ownership and that the key survives item reorder without relying on letters or display position. Allow multiple tasks with different formats in a challenge.

**Acceptance criteria:** The two-idiom example can be authored as one challenge with two distinct three-option tasks; question preview shows each task's own options without correctness data; reveal identifies correct items and optional explanation. Foreign/deleted option IDs prevent a Ready save with actionable errors.

**Verify:** Baseline commands; tests for per-task item isolation, mixed free-text/choose-one challenges, reordering, and key/preview separation. Author the two-idiom example manually in the studio.

## 5. Context groups and shared-pool matching

**Goal:** Share instructions/media position and one answer bank across related tasks, without treating groups as answerable.

**Context / files:** Spec (Requirement 2–3; `ContextGroup`, `ResponsePool` ownership/ancestry; matching key). New `studio` schema/validation/editor/projection tests.

**Approach:** Add ordered, optionally nested context groups. Allow a response pool on a challenge/group, with tasks in its subtree referencing that pool. Matching task keys select one ID in the shared pool; tasks retain independent prompt, points, and reveal. Validate no ancestry cycles, cross-challenge links, illegal pool scope, duplicate sibling order, or invalid item IDs. Keep the one-task editor simple without groups.

**Acceptance criteria:** A matching challenge with several prompts and a common bank is authored and previewed correctly. Nesting shared context changes only relevant descendants. Incorrect ownership/cycles are rejected; group content cannot be submitted or scored.

**Verify:** Baseline commands; model and editor tests for valid ancestor pools, invalid sibling/unrelated pools, recursive groups, mixed task formats, and shared prompt projection. Manually author a multi-task matching challenge.

## 6. Ranking with distinct display order, key, and reveal

**Goal:** Demonstrate that a task's submitted items, correct ordering, and explanatory reveal are independent.

**Context / files:** Spec (Requirements 3–4; ranking key; content blocks at item scope). New `studio` validation/editor/projection tests; extend task-local pools from task 4.

**Approach:** Support ranking items with ordered display position and `{"ordered_item_ids": [...]}` containing exactly one permutation of those item IDs. Let each item have separate reveal blocks, so an animal-speed example can reveal speeds alongside the correctly ranked animals. Do not implement team submissions, partial-credit scoring, or historical snapshots.

**Acceptance criteria:** An author can reorder displayed items without corrupting the key, set correct order separately, and attach explanatory text per item. Question preview exposes neither correct order nor item reveal; reveal shows correct order and explanation. Missing, repeated, or foreign item IDs are rejected on Ready save.

**Verify:** Baseline commands; tests for permutations, order independence, item-level reveals and preview separation. Manually author the animal-speed example.

## 7. Local image/video blocks throughout the editor

**Goal:** Test the actual media-heavy authoring experience without accessing production S3.

**Context / files:** Spec (Requirement 4; Experiment isolation and media; Invariants), `quiz/image_processing.py` and `quiz/fields.py` for reusable validation logic **but not storage fields**, `pub_trivia/settings.py`. New v2 `ContentBlock` file storage/forms/editor/preview/tests.

**Approach:** Extend ordered prompt/reveal blocks to support local image/video files for challenge, group, task, and response-item owners. Validate type/size, add alt text for images, preserve draft edits on bad upload, and handle missing local files gracefully. Use a v2-only ignored local media directory and development-only delivery route. Reuse pure image optimization if practical; do not change or instantiate S3-backed legacy fields.

**Acceptance criteria:** Images and videos upload, replace, and preview at both prompt and reveal scopes, including on a choice/item. Invalid or oversize files show helpful errors without saving broken references; no S3 calls or legacy media records occur.

**Verify:** Baseline commands; tests with temporary local storage for supported/invalid files, authorization on upload/media delivery, and missing-file preview. Run the studio locally and upload/preview one image and one video. Inspect the v2 storage path and confirm the fixture remains unchanged.

## 8. End-to-end experiment and regression gate

**Goal:** Confirm the v2 studio is usable for real new content and truly isolated from the running app.

**Context / files:** Entire spec; `quiz/tests/`, `quiz/management/commands/export_content.py`, `quiz/management/commands/seed_db.py`, `quiz/fixtures/content.json`. New `studio` integration/permission tests and concise local setup/use instructions under `docs/v2-content-studio/`.

**Approach:** Test complete editor-to-game workflows (draft and Ready; single/multi-task; all four formats; media; category search and last use). Confirm question previews never include answer/reveal data. Test opt-in and `DEBUG` denial, permissions, and failures on incomplete content. Document enabling the local experiment, applying **new-table-only** migrations, and creating a sample game; no production deploy steps. Browser-check the workflow with representative examples and record friction for follow-up iterations rather than silently expanding the initial scope.

**Acceptance criteria:** A new game containing free-text, idiom-style choose-one, ranking, matching, and media challenges can be authored and previewed entirely in studio. Legacy gallery/live/admin behavior and fixture contents are unchanged. The local-only gate works when disabled; regression tests pass.

**Verify:** `uv run manage.py check`; `uv run manage.py makemigrations --check --dry-run`; `uv run manage.py test quiz studio`; compare `git diff -- quiz quiz/fixtures/content.json` (must be empty). With the local development opt-in, `uv run manage.py runserver` and manually create/preview the representative game on both narrow and wide browser viewports. Do not run `seed_db --force` against any shared/production database to verify this experiment.
