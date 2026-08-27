# Offline Gallery Mode - Design Spec

## Context

The host needs to run a single trivia game entirely offline (e.g. while camping) using
gallery mode only. Two production dependencies break without internet access:

1. Question/answer images and videos are served from S3 via CloudFront.
2. `init_trivia.py` (team assignment) reads player lists from and writes results to
   Google Sheets.

This is a personal, dev-only tool for one specific use case. It must never affect
production behavior, CI, or the deployed app. It does not need automated test coverage
in `quiz/tests/`.

## Scope

**In scope:**
- Downloading a single game's content (questions, answers, rounds, categories, media)
  into a self-contained local bundle.
- Running the Django app locally against that bundle in gallery-mode-only, with no
  network dependency.
- A local, CSV-based variant of team assignment that doesn't require Google Sheets.

**Out of scope:**
- Live session mode, analytics mode, or the admin interface while offline (untouched;
  may or may not function, not a requirement).
- Multiple simultaneous offline bundles/games (only one game is ever needed offline at
  a time).
- Any change to production settings, CI, or `quiz/tests/`.
- Automated test coverage for the offline tooling.

## Architecture

Two new, isolated pieces are added on top of the existing app. Nothing in the existing
production code paths (settings.py, urls.py used in prod, models) changes behavior for
normal dev/prod runs.

1. **`offline_bundle/`** (gitignored, project root): a self-contained directory holding
   - `db.sqlite3` - a SQLite database containing only the copied content for one game
   - `media/` - a folder mirroring the S3 key structure for that game's downloaded
     images/videos

   Only one bundle is active at a time. Re-running the download command always wipes and
   rebuilds the bundle from scratch (no incremental/append mode, no multi-game support).

2. **`pub_trivia/settings_offline.py`**: imports everything from `settings.py`, then
   overrides:
   - `DATABASES["default"]` -> SQLite at `offline_bundle/db.sqlite3`
   - `MEDIA_ROOT` -> `offline_bundle/media/`
   - `AWS_CLOUDFRONT_DOMAIN` -> `/media` (so `CloudFrontURLField.get_full_url` resolves
     to locally-served media instead of CloudFront)
   - `OFFLINE_MODE = True` (new flag)

   `pub_trivia/urls.py` gets one additive change:
   ```python
   if getattr(settings, "OFFLINE_MODE", False):
       urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   ```
   This is a no-op for normal dev/prod since `OFFLINE_MODE` is not set there.

## Download Command

`quiz/management/commands/download_game_offline.py`

Usage: `uv run manage.py download_game_offline <game_id>` - run under normal
`settings` (real DB, real internet access), not `settings_offline`.

Steps:
1. Delete any existing `offline_bundle/`, recreate `offline_bundle/db.sqlite3`, and run
   migrations against it via Django's multi-database support (a second `"offline"`
   connection pointed at the new SQLite file for the duration of the command).
2. Copy exactly the rows needed for gallery mode into the offline database:
   - The target `Game`
   - Its related `Category`, `QuestionType`, `QuestionRound` rows
   - All `Question` rows for the game
   - All `Answer` rows for those questions

   No `GameSession`, `SessionTeam`, `TeamAnswer`, `GameResult`, `PlayerStats`, or `User`
   data is copied - gallery mode only.
3. For every `question_image_url`, `answer_image_url`, `question_video_url`, and
   `answer_video_url` on the copied rows, download the file from CloudFront via
   `requests` and write it to `offline_bundle/media/<same relative path>`, preserving
   the exact key structure. This means `CloudFrontURLField` needs no offline-specific
   logic - it always just prefixes whatever `AWS_CLOUDFRONT_DOMAIN` currently is.
4. Print a summary: game name, question count, media files downloaded, bundle size on
   disk.

### Error handling

- If `game_id` doesn't exist, exit with a clear error before creating/wiping the bundle.
- Individual media download failures (404, timeout, etc.) are logged as warnings and
  collected into a "failures" list printed in the final summary. The command does not
  abort on a single failed file - partial offline content is preferable to none.
- `settings_offline.py` does not fall back to S3 for anything. A missing local file
  simply 404s in the browser - acceptable for this use case.

## Offline Team Assignment

`init_trivia_offline.py` (new file, sibling to `init_trivia.py`, project root).

A full standalone copy of `init_trivia.py`'s `Player`/`Team`/assignment/reveal logic
(duplicated intentionally, not extracted into a shared module - simplicity over DRY for
a two-script throwaway tool) with these differences:

- **Input**: reads players from a local CSV file (`players.csv` by default, path
  prompted for interactively) with the same columns the Google Sheet uses today
  (`name`, `gender`, `partner`) instead of `read_player_list_from_gsheet`.
- **Output**: writes the resulting team/scoring dataframe (same shape as
  `create_game_df`) to a local CSV file (`trivia-<date>.csv`) instead of uploading to a
  live Google Sheet via `gspread`.
- Same interactive prompts (CSV path, number of teams, minimum team size), same
  dramatic terminal team reveal.
- No `gspread` / `oauth2client` / network dependency at runtime.

The resulting CSV can be copied into the real Google Sheet by hand once back online.

## Makefile & Workflow

```makefile
run-offline:
	DJANGO_SETTINGS_MODULE=pub_trivia.settings_offline uv run manage.py runserver

download-offline:
	uv run manage.py download_game_offline $(GAME_ID)

start-offline:
	uv run python init_trivia_offline.py
```

End-to-end usage:
1. While online: `make download-offline GAME_ID=42`
2. While online: `make start-offline` (or run it at the campsite if a generator/laptop
   battery only, no internet needed either way)
3. At the campsite: `make run-offline`, browse to gallery mode, run the game

`offline_bundle/` is added to `.gitignore`.

## Verification Plan

No automated test suite coverage (this is a personal dev-only tool, out of scope for
`quiz/tests/` and CI). Manual verification instead:

1. `make download-offline GAME_ID=<id>` against a real game with images and videos.
   Confirm summary output shows expected question count and media downloaded.
2. `make run-offline`, browse gallery mode for that game with wifi disabled, confirm
   images/videos load from local media rather than failing.
3. `make start-offline` with a sample `players.csv`, confirm teams are assigned and the
   output CSV has the expected structure.
