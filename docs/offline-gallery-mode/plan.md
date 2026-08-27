# Offline Gallery Mode - Implementation Plan

Source spec: `docs/superpowers/specs/2026-08-15-offline-gallery-mode-design.md`

This plan breaks the spec into four tasks. Task 1 is foundational (settings + URL
wiring) and should land first. Tasks 2 and 4 depend on Task 1. Task 3 is fully
independent and can be done in any order.

## Shared context for all tasks

This is a personal, dev-only tool for running a single trivia game's gallery mode
offline (e.g. at a campsite with no internet). It must never affect production
settings, CI, or `quiz/tests/`. No automated test coverage is required for any of these
tasks - verification is manual, as described in each task below.

Key existing files referenced throughout:
- `pub_trivia/settings.py` - main Django settings (DATABASES, MEDIA_ROOT,
  AWS_CLOUDFRONT_DOMAIN defined here)
- `pub_trivia/urls.py` - root URL conf
- `quiz/fields.py` - `CloudFrontURLField`, `S3ImageField`, `S3VideoField`
- `quiz/models.py` - `Game`, `Category`, `QuestionType`, `QuestionRound`, `Question`,
  `Answer` (the models relevant to gallery mode; `Question.game`, `Question.category`,
  `Question.question_type`, `Question.game_round` are FKs, `Answer.question` is a FK,
  `Category.games` is M2M)
- `Makefile` - existing `run` target: `uv run manage.py runserver`; existing `start`
  target runs `init_trivia.py`
- `init_trivia.py` - existing Google Sheets-based team assignment script (read for
  reference/duplication in Task 3)

---

## Task 1: Offline settings module and media serving

**Goal:** Add `pub_trivia/settings_offline.py` and wire up local media serving so the
app can run against a local SQLite DB and local media folder, with zero impact on
normal dev/prod settings.

**Context:** Production/dev settings serve media through S3/CloudFront
(`CloudFrontURLField.get_full_url` prefixes `settings.AWS_CLOUDFRONT_DOMAIN`). Offline
mode needs this to resolve to locally-served files instead, and needs Django to
actually serve `MEDIA_ROOT` over HTTP (not currently wired up anywhere, since prod never
needs it).

**Relevant files:**
- `pub_trivia/settings.py` (read only - reference `BASE_DIR`, `DATABASES`,
  `MEDIA_ROOT`, `MEDIA_URL`, `AWS_CLOUDFRONT_DOMAIN`)
- `pub_trivia/urls.py` (edit)
- `pub_trivia/settings_offline.py` (new)

**Proposed approach:**
1. Create `pub_trivia/settings_offline.py`:
   ```python
   from .settings import *  # noqa

   OFFLINE_MODE = True
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.sqlite3",
           "NAME": BASE_DIR / "offline_bundle" / "db.sqlite3",
       }
   }
   MEDIA_ROOT = BASE_DIR / "offline_bundle" / "media"
   AWS_CLOUDFRONT_DOMAIN = "/media"
   ```
2. In `pub_trivia/urls.py`, add (import `settings` and `static` from
   `django.conf`/`django.conf.urls.static`):
   ```python
   if getattr(settings, "OFFLINE_MODE", False):
       urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   ```
   This must be additive only - no behavior change when `OFFLINE_MODE` is absent
   (normal dev/prod).
3. Add `offline_bundle/` to `.gitignore`.

**Acceptance criteria:**
- Running the app with `DJANGO_SETTINGS_MODULE=pub_trivia.settings` (i.e. normal dev)
  is byte-for-byte unaffected - `OFFLINE_MODE` doesn't exist, `urlpatterns` unchanged,
  `AWS_CLOUDFRONT_DOMAIN` unchanged.
- Running with `DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline` starts without
  errors even before `offline_bundle/` exists (Django shouldn't crash on import just
  because the SQLite file/media dir don't exist yet - they get created by Task 2's
  download command or `migrate`).
- `offline_bundle/` does not show up in `git status` after being created.

**Source reference:** Design spec, "Architecture" section.

**Verify:**
```bash
# Normal settings still work
uv run manage.py check

# Offline settings load without error
DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline uv run manage.py check
```

**Out of scope:** Populating the SQLite DB with real content (Task 2), the
`run-offline` Makefile target (Task 4).

---

## Task 2: `download_game_offline` management command

**Goal:** A management command that packages one game's gallery content (questions,
answers, rounds, categories) plus all referenced media into `offline_bundle/`.

**Context:** Must run under normal settings (real Postgres DB, real internet access to
CloudFront), and produce a bundle consumable by `settings_offline.py` (Task 1) with
zero further transformation - relative media paths in the SQLite DB must exactly match
files under `offline_bundle/media/`.

**Relevant files:**
- `quiz/management/commands/download_game_offline.py` (new)
- `quiz/models.py` (read - `Game`, `Category`, `QuestionType`, `QuestionRound`,
  `Question`, `Answer`)
- `quiz/fields.py` (read - understand how `CloudFrontURLField` stores relative paths so
  downloaded files are saved to matching relative paths under `media/`)
- `quiz/management/commands/seed_db.py` (read for reference - existing example of a
  content-loading management command in this codebase, for style/conventions)
- `pub_trivia/settings_offline.py` (read only, from Task 1 - target DB path)

**Proposed approach:**
1. Command signature: `uv run manage.py download_game_offline <game_id>`.
2. Validate `game_id` exists via `Game.objects.get(pk=game_id)`; exit with a clear
   error (non-zero exit code, no bundle changes) if not found.
3. Delete `offline_bundle/` if it exists, recreate `offline_bundle/db.sqlite3` and
   `offline_bundle/media/`.
4. Register a second database connection at runtime pointed at the new SQLite file
   (Django `connections` API, alias e.g. `"offline"`), run migrations against it
   (`call_command("migrate", database="offline")`).
5. Copy rows into the offline DB using Django ORM against the `"offline"` alias:
   `Game`, its `categories` (M2M), the `QuestionType`s and `QuestionRound`s referenced
   by its questions, all `Question`s (`game_id=game_id`), and all `Answer`s for those
   questions. Preserve primary keys so FKs still resolve correctly across the two DBs
   (use `.using("offline")` with explicit `pk=` on save, or bulk_create with `pk`
   preserved).
6. For each copied `Question`/`Answer` row, for each of
   `question_image_url`/`answer_image_url`/`question_video_url`/`answer_video_url`
   that is non-empty: build the full CloudFront URL (reuse
   `CloudFrontURLField.get_full_url`), `requests.get()` it, and write the bytes to
   `offline_bundle/media/<relative_path>` (creating subdirectories as needed) where
   `<relative_path>` is the same relative path already stored in the field (strip the
   CloudFront domain, not the full URL).
7. On a per-file download failure (non-200 response, timeout, connection error): log a
   warning with the URL and continue; collect into a `failures` list.
8. Print a final summary: game name, `game_number`, count of questions copied, count of
   media files downloaded successfully, count of failures (with URLs listed), bundle
   size on disk (`du`-style sum of `offline_bundle/`).

**Acceptance criteria:**
- Running the command against a real game with images populates
  `offline_bundle/db.sqlite3` such that loading it under `settings_offline` and
  querying `Question.objects.filter(game_id=<id>)` returns the same questions/answers
  as the source DB.
- Every non-empty media URL field on a copied row has a corresponding file physically
  present at `offline_bundle/media/<relative path>`.
- Re-running the command for the same or a different game fully replaces the previous
  bundle (no leftover files from a prior run).
- A single broken/missing media URL does not abort the command; it's reported in the
  summary and the rest of the bundle still completes.
- Command exits non-zero with a clear message if `game_id` doesn't exist.

**Source reference:** Design spec, "Download Command" section.

**Verify:**
```bash
# Pick a real game id with images/videos from your dev DB
uv run manage.py download_game_offline <game_id>

# Confirm bundle contents
ls offline_bundle/
ls offline_bundle/media/

# Confirm the offline DB has the expected content
DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline uv run manage.py shell -c \
  "from quiz.models import Question; print(Question.objects.count())"
```

**Out of scope:** The `download-offline` Makefile wrapper (Task 4), serving the
downloaded media over HTTP (already handled by Task 1).

---

## Task 3: Offline team assignment script (`init_trivia_offline.py`)

**Goal:** A standalone offline variant of `init_trivia.py` that reads players from a
local CSV and writes team assignments to a local CSV, with no Google Sheets/network
dependency.

**Context:** `init_trivia.py` currently depends on `gspread`/`oauth2client` and a live
Google Sheet for both input (player list) and output (team assignment upload). This
script duplicates the assignment/reveal logic (intentionally - not extracted into a
shared module, per design decision) and swaps only the I/O layer.

**Relevant files:**
- `init_trivia.py` (read - source of truth for `Player`, `Team`,
  `sort_players_by_sex`, `assign_teams`, `generate_teams_list`, `dramatic_print`,
  `str_list_to_pretty_str`, `spotlight_reveal`, `display_teams`, `create_game_df`, and
  the `main()` flow/prompts to duplicate)
- `init_trivia_offline.py` (new, project root)

**Proposed approach:**
1. Copy `init_trivia.py` to `init_trivia_offline.py`.
2. Remove `requests`, `gspread`, `oauth2client` imports and the
   `read_player_list_from_gsheet`/`connect_to_gsheets` functions.
3. Add a `read_player_list_from_csv(csv_path: str) -> List[Player]` function: reads a
   CSV with columns `name`, `gender`, `partner` (same semantics as the Google Sheet
   today - `gender` is `"M"`/`"F"`, `partner` may be blank/NaN) using `pandas.read_csv`,
   mapping `gender` to `male: bool` and blank `partner` to `None`, same as the existing
   `.assign(...).replace({np.nan: None})` pattern in `init_trivia.py`.
4. Update `main()`:
   - Prompt for a CSV path (e.g. `players.csv`) instead of a sheet name.
   - Call `read_player_list_from_csv(csv_path)` instead of the gsheets flow (no
     `connect_to_gsheets()` call).
   - After building `game_df` via `create_game_df(assigned_teams)`, write it to
     `trivia-<date>.csv` via `game_df.to_csv(...)` instead of `sheet.update(...)`.
   - Keep the same number-of-teams / minimum-team-size prompts and the same
     `display_teams` dramatic reveal, unchanged.
5. Print the output CSV path at the end so it's obvious where the results landed.

**Acceptance criteria:**
- `init_trivia_offline.py` has no import of `gspread`, `oauth2client`, or `requests`,
  and runs with no network access.
- Given a `players.csv` with the same columns as today's Google Sheet, produces
  identical team assignment structure/output columns as `init_trivia.py` would (via
  `create_game_df`), written to a local CSV file.
- Interactive flow (prompts, dramatic reveal) matches `init_trivia.py`'s UX except for
  the CSV path prompt replacing the sheet name prompt.

**Source reference:** Design spec, "Offline Team Assignment" section.

**Verify:**
```bash
# Prepare a sample players.csv with columns: name,gender,partner
uv run python init_trivia_offline.py
# Enter the csv path, team count, and min team size at the prompts
# Confirm a trivia-<date>.csv is created with the expected team/score columns
cat trivia-*.csv
```

**Out of scope:** The `start-offline` Makefile wrapper (Task 4), uploading results back
to Google Sheets (explicitly manual, done later by the user once back online).

---

## Task 4: Makefile targets

**Goal:** Wire `Task 1`, `Task 2`, and `Task 3` together behind three `make` targets
matching the existing `make run` / `make start` UX.

**Context:** Depends on Tasks 1-3 being complete. This task is purely the Makefile
glue plus the `help` target's documentation line, per the existing pattern in
`Makefile`.

**Relevant files:**
- `Makefile` (edit)

**Proposed approach:**
1. Add targets:
   ```makefile
   run-offline:
   	DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline uv run manage.py runserver

   download-offline:
   	uv run manage.py download_game_offline $(GAME_ID)

   start-offline:
   	uv run python init_trivia_offline.py
   ```
2. Add these three targets to the `.PHONY` line.
3. Add corresponding lines to the `help` target's echo block, matching the existing
   style (e.g. `@echo "  make run-offline       - Run Django server against offline
   bundle (no internet needed)"`).

**Acceptance criteria:**
- `make download-offline GAME_ID=<id>` runs Task 2's command with the given game id.
- `make run-offline` runs the server under `settings_offline`.
- `make start-offline` runs Task 3's script.
- `make help` lists all three new targets.
- Existing targets (`run`, `start`, etc.) are unchanged.

**Source reference:** Design spec, "Makefile & Workflow" section.

**Verify:**
```bash
make help | grep offline
make download-offline GAME_ID=<id>
make run-offline
# Ctrl+C, then:
make start-offline
```

**Out of scope:** Any CI integration (explicitly out of scope per the design spec).
