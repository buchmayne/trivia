# V2 content studio — experimental spec

## What

Build a **development-only, parallel content system** for authoring reusable trivia challenges and assembling new games from them. A purpose-built Django-backed studio replaces the *authoring experience* for new v2 content, not the existing Django admin or live game. Its purpose is to test whether a cleaner domain model makes it faster to capture an idea, develop a challenge with media and a meaningful reveal, and put it in a game. Create new v2 content from scratch; do not convert old questions.

## Context

Today `quiz/models.py` makes `Question` belong to one `Game`, and an `Answer` may stand for an answerable subquestion, a ranking/matching item, or a solution. `Question.answer_bank` is unstructured text. `quiz/admin.py` exposes these overlapping fields in the Django admin; `quiz/session_api.py`, `quiz/scoring.py`, and gallery/live templates branch on `QuestionType.name`. The committed fixture has 309 questions and 1,146 answers. The existing authoring, playback, fixture, session, and analytics systems must continue to work without v2 content.

The v2 experiment is **not a migration project or a production feature**. Its only database migrations create new v2 tables in a development database. The legacy models, records, APIs, admin screens, media references, and content fixture are untouched. Do not deploy this experimental branch to production; route guards are defense in depth, not a production rollout plan.

## Requirements

1. Quick capture: save a new challenge as a draft using a working title **or** rough notes; it need not have a category, task, or evaluation key yet. Browse, search, edit, and filter the library by category and draft/ready status.
2. Develop a challenge independently of games. Assign at most one category; define shared instructions/media, optional nested context groups, and one or more answerable tasks. The common one-task case must require no group or shared pool setup.
3. Each task has its own response format, point maximum, prompt content/media, evaluation key, and optional reveal content/media. Include working authoring controls for free text, choose-one, ranking, and matching against a shared item pool. Different task formats may coexist in one challenge.
4. Support ordered text, image, and video blocks in prompt and reveal content at challenge, group, task, and response-item scope. Images/videos can be uploaded and previewed in the studio; v2 uploads use isolated local storage, not S3/CloudFront. A correct evaluation key is distinct from what is shown in the reveal (e.g., ranked animals vs. their actual speeds).
5. Mark a challenge Ready only after format-specific checks pass. Ready challenges can be found and placed into multiple v2 games. A challenge's current content is shown in all future game previews; no snapshots, copies, or version history.
6. Create v2 games with ordered rounds and challenge placements. Round and question order/number belong to placements, not challenges. Show category coverage as information only; never require a particular category or count. Library “last used” means the most recent placement creation time, not a historical play date.
7. Provide question and reveal previews for a challenge, plus an ordered game preview. The question preview must not include the evaluation key or reveal-only blocks in its data payload. No player input, live sessions, scoring execution, or publication is required.
8. Keep the v2 app independent of legacy `quiz` content tables and serializers. Reuse Django authentication and pure media-processing utilities if helpful, but do not reuse legacy `Answer` or S3-specific fields as v2 domain entities.

## Design

### Bounded contexts and relationships

Create a separate Django app (proposed name: `studio`) with only new tables and `/studio/` authoring routes. Use thin views and application-level operations for validation/creation, so domain rules are not confined to form widgets and a future non-Django editor could use the same conceptual contracts.

| Model | Essential data and relationships | Rule |
|---|---|---|
| `Category` | Name; has many `Challenge`s | One category per challenge, optional for a draft. Separate v2 catalog; no legacy category FK. |
| `Challenge` | Working title, rough notes, status (`draft`/`ready`), nullable category FK, timestamps | Reusable content identity, not owned by a game. A draft requires either title or notes; points are computed from its tasks. |
| `ContextGroup` | Challenge FK, nullable parent group FK, sibling order | Optional nestable shared context; cannot be submitted or scored. Parent must belong to the same challenge; cycles forbidden. |
| `Task` | Challenge FK, optional group FK, sibling order, stable format code, positive max points, nullable response-pool FK, JSON evaluation key | One answerable unit. Group and pool must belong to its challenge. A Ready challenge has at least one task. |
| `ResponsePool` | Belongs to exactly one challenge, group, or task | Shared pools can be used by descendant tasks within the same challenge; task-local pools belong to one task. |
| `ResponseItem` | Pool FK, sibling order | One presented choice/ranking/matching item. It can have its own prompt and reveal blocks. |
| `ContentBlock` | Kind (`text`/`image`/`video`), text body or locally stored file, order, exactly one owner (challenge, group, task, or item), phase (`prompt`/`reveal`), media alt text where relevant | One ordered stream of content at each scope and phase, rather than repeated `*_image_url` columns. Validate body/file against kind; escape plain text rather than rendering arbitrary HTML. |
| `Game` | Name, description, timestamps | V2-only assembly; independent of legacy `Game`. |
| `GameRound` | Game FK, name, order | Belongs to exactly one v2 game (unlike the current shared round lookup). |
| `Placement` | GameRound FK, Challenge FK, order, created timestamp | Holds the game's ordering; display question number is derived from ordered rounds/placements. Reuse the same challenge across games without copying content. |

Use stable machine-readable task format codes rather than editable `QuestionType.name` strings. A task references one pool when its format needs items. The evaluation key is a **small format-discriminated JSON value**, validated by the domain layer on every save as Ready; text, files, choice labels, and *display* ordering live in the relational records above, *not* in an opaque JSON question document. IDs in the key are integer response-item IDs. The v1 key shapes are:

- `free_text`: `{"reference_text": "..."}` — nonblank reference answer for later manual review (not automatic string grading); no pool required.
- `single_choice`: `{"correct_item_id": 123}` — ID from the task's pool (at least two items).
- `ranking`: `{"ordered_item_ids": [123, 124]}` — exact permutation of all IDs in the task's pool (at least two items); this correct order differs from display order.
- `matching`: `{"correct_item_id": 123}` — ID from a group/challenge-level shared pool (at least two items); each matching task has its own prompt and points.

Tasks can mix formats within one challenge. Format-specific UI and future grading code may be added without changing the challenge/task/placement structure. Do **not** implement grading, submissions, or an abstract generic scoring engine in this prototype. A future grader must be able to interpret the key without parsing reveal content; future per-item partial-credit rubrics can be specified when grading is implemented. Until then, `Task.max_points` is the maximum for that task and challenge total is `SUM(task.max_points)`; don't persist a redundant challenge total.

Validate owner exclusivity for content blocks/pools and ordering uniqueness; reject cross-challenge group/pool/item links. Group ancestry must be acyclic, and a task may use a task-local pool or a pool on its containing group/ancestor/challenge. A draft can be incomplete. Transition to Ready checks category, at least one task, presentable prompt context, positive task points, required pool/items/key for each format, and no broken references. Placing a challenge requires Ready at placement time. Do **not** add a versioning system or extra restrictions for subsequent edits; game preview reads the current challenge and handles missing draft content gracefully.

### Studio workflow

- **Library / inbox:** immediate draft capture, search and category/status filters, last-placement timestamp, open editor. An idea can start with just a title or notes; Ready requires meaningful content.
- **Challenge editor:** edit shared context and ordered tasks; add groups or shared pools only when needed; select a task format to show its appropriate key/item controls. Save drafts without forcing completeness; show actionable, field-level errors when marking Ready. Upload and replace image/video blocks. Preview question and reveal separately.
- **Game builder:** create rounds, search/filter Ready challenges, add/remove/reorder placements, see derived question numbering and informational category coverage. Preview the ordered game, including its question and reveal states. Creating a challenge from this flow may link to the same library editor, not a second content model.
- **Preview contract:** build separate server-side `question` and `reveal` projections from the same domain objects. The question projection excludes evaluation keys, reveal blocks, and correct-order/correct-item information. The reveal projection contains the resolved correct result and reveal blocks; it need not expose the raw evaluation-key JSON. Do not send hidden answers to the question preview and rely on CSS to conceal them.

Use ordinary Django views/templates/forms (or small client-side enhancements) behind the purpose-built studio; no new frontend framework is necessary for the prototype. Keep accessibility, keyboard navigation, and quick repeat entry in mind, but defer final visual design until the workflow can be tried with real content.

### Experiment isolation and media

Gate all studio routes/operations behind an explicit development opt-in and `DEBUG`; require an authenticated authorized author (existing game-admin permission or staff). Production routes must not expose studio even if the app is installed. Keep files under a separate ignored local directory/URL namespace, using a local Django storage backend for v2 blocks; do not use `S3ImageField`, `S3VideoField`, or production media credentials. Validate uploaded file type and size, use existing pure image optimization if appropriate, and show upload errors without losing draft text. V2 models are not added to `export_content`/`seed_db` or `quiz/fixtures/content.json`.

## Decisions

| Choice | Alternatives and reason | Reversible? |
|---|---|---|
| Separate v2 Django app/tables and custom studio | Replacing legacy models/admin or migrating fixtures now risks working gameplay and prevents rapid experimentation. | Yes; experiment can be discarded. |
| Challenges independent of games; placements own game position | Current `Question.game` blocks reuse. Copying questions into each game would recreate that limitation. | Hard to change after authoring content; treat as core. |
| One category per challenge, derived category use in games | Per-placement categories and `Category.games` duplicate classification/derived state without an observed use case. | Possible later. |
| Tasks as answerable leaves; optional nested groups only share context | An unrestricted answerable tree makes scoring ownership unclear; flat tasks alone make nested shared context awkward. | Extendable without redefining tasks. |
| Separate structured key and optional reveal blocks | Reveal text/media explains, but cannot reliably serve as machine-readable correctness. | Core. |
| Relational content/items plus validated format-key JSON | A single JSON document weakens authoring/querying; a new answer table per format requires repeated migrations. JSON is limited to format-specific key data. | Key schemas must be versioned/validated if changed later. |
| Library-first drafts and independent game assembly | Game-first-only authoring imposes friction when capturing spontaneous ideas. | Yes. |
| Local-only uploads and previews | Reusing S3 confuses experiment storage with production assets. | Yes; file storage can be swapped later. |

## Invariants and error behavior

- The legacy app behaves identically with or without the experiment enabled. No existing question, game, session, analytics record, legacy fixture, or legacy media object is changed by studio actions.
- A challenge has at most one category. Ready requires at least one valid task; the displayed challenge maximum is computed from task maxima. Duplicate sibling order, foreign response-item IDs, pool references to another challenge, and group cycles are rejected.
- Draft saves accept incomplete content. Every save as Ready and every initial placement runs the relevant validation and shows specific errors rather than partially saving an invalid Ready state or placement. Invalid/missing local media produces an editor/preview error or placeholder, not a server crash. An already placed challenge subsequently edited as a draft may show an incomplete-content warning in preview; no new blocking/versioning workflow is needed for this unlikely case.
- Operations that update a challenge, its tasks/items/blocks, or a game's placements should be transactional at the database level. File uploads use normal safe file handling; if an upload fails, do not mark the challenge Ready or create a broken reference. Escaped text, CSRF protection, authorized access, and limits/type checks apply to all editor endpoints.

## Testing strategy

- Model/domain tests: independent challenge reuse across two games; placement order/derived numbering; category and last-use queries; task/points totals; no group cycles/cross-challenge links; task-local vs shared pools; draft-to-Ready validation for all four formats; malformed/foreign IDs rejected.
- Editor integration tests: quick draft capture, incomplete draft save, Ready validation errors, category/status search, create/reorder/remove game placements, and edit propagation to both game previews.
- Projection tests: prompt and reveal content/media at each scope; item order; question projection contains **no** evaluation key or reveal-only content; ranking correct order and speed-style explanation may differ; a mixed-format challenge renders in preview.
- Media/security tests: image/video upload and preview with local test storage; bad type/oversize failure; no S3 write; authorization, CSRF, and disabled routes in non-development settings.
- Regression: run existing `quiz` tests and verify legacy fixtures/export and gallery/live routes still work; no old data is migrated. Try a real newly authored game with single-task, multipart, media, ranking, matching, and idiom-style local-choice challenges, and judge whether capture/edit/assemble is faster than the current admin workflow.

## Out of scope

Legacy question/answer conversion; replacing Django admin or gallery/live UI; team submissions, grading, sessions, results, analytics, or historical snapshots; production deployment or production data migrations; enforcement of category quotas; automated interpretation of legacy `answer_bank` values; new authoring features that do not help evaluate the initial workflow.
