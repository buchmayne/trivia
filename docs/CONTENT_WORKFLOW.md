# Content workflow

How to add trivia content locally and deploy it to production without
disturbing user accounts, live sessions, or analytics.

## The model

Content and user/session/analytics data are **separated by fixture**, not
by environment.

- **Content** (Game, Question, Answer, Category, QuestionType, QuestionRound)
  lives in `quiz/fixtures/content.json` in the repo. Local is the source
  of truth; production is overwritten from the fixture when it changes.
- **User data** (`auth.User`, `quiz.UserProfile`, `account.EmailAddress`),
  **session data** (`GameSession`, `SessionTeam`, `SessionRound`,
  `TeamAnswer`), and **analytics** (`GameResult`, `PlayerStats`) are
  preserved on every deploy. The seed command excludes them by name -
  see `EXCLUDED_MODELS` in `quiz/management/commands/seed_db.py`.

## Add content locally

```bash
# 1. Run the dev server and the admin
uv run manage.py runserver
# Visit http://localhost:8000/admin/

# 2. Create or edit Games, Questions, Answers, Categories, Rounds.
#    The admin UI is the authoring surface. Don't edit content.json by hand.

# 3. (Optional) Smoke-test in the live session UI at /quiz/play/
```

## Deploy content to production

```bash
make preprod                                # export + black + tests
git add quiz/fixtures/content.json
git commit -m "Add <month-year> game content"
git push origin main
```

That's the entire workflow. GitHub Actions does the rest.

### What `make preprod` does

Defined in `Makefile`. Three steps:

1. `uv run manage.py export_content` - serializes the six content models
   from your local DB to `quiz/fixtures/content.json`. `Game.owner` is
   nullified so the fixture loads cleanly in any environment.
2. `uv run black .` - format.
3. `uv run manage.py test quiz` - full suite.

If any step fails, fix it before committing.

### What CI/CD does on push to `main`

From `.github/workflows/django.yml`:

1. **Test job**: migrates a fresh Postgres, runs `seed_db` twice (fixture
   idempotency check), runs the full test suite, runs `black --check`.
2. **Deploy job** (only on push to `main`, after tests pass):
   - SSH to the droplet, `git reset --hard origin/main`.
   - Regenerate `.env` from GitHub Secrets.
   - `docker-compose down --remove-orphans && docker-compose up -d --build`.
     The `web` container boots with: `migrate -> seed_db -> collectstatic -> gunicorn`.
     `seed_db` (no `--force`) **skips if any quiz content already exists**, so
     this step is a no-op on a normal deploy.
   - Diff `quiz/fixtures/content.json` between previous HEAD and new HEAD.
     If it changed (or this is the first deploy), wait for the web container
     to be ready, then run `seed_db --force`. This filters and reloads
     content models only; user/session/analytics rows are untouched.

In short: **a deploy reloads content if and only if `content.json` changed
in the push.** Code-only deploys never touch the database content.

## Common operations

### Force a re-seed without changing content

Re-export and commit:

```bash
make export-content
git add quiz/fixtures/content.json
git commit -m "Force content re-seed" --allow-empty
git push
```

The re-exported file is byte-identical only if nothing changed locally; in
that case CI will see no diff and skip the seed. To genuinely force a
re-seed of unchanged content, SSH in and run
`docker-compose exec web uv run manage.py seed_db --force` manually.

### Pull production content back to local

```bash
# On the droplet
docker-compose exec web uv run manage.py export_content --output /tmp/prod.json
docker cp trivia_app_web:/tmp/prod.json ./prod.json

# Locally
uv run manage.py loaddata prod.json
```

### Full local DB snapshot (backup, not for deploy)

```bash
make dump-data   # writes db_initial_data.json (all tables, all rows)
```

This file is for local recovery only. Production never loads it.

### Clean up old sessions on production

```bash
docker-compose exec web uv run manage.py cleanup_sessions --dry-run
docker-compose exec web uv run manage.py cleanup_sessions           # default: > 30 days
docker-compose exec web uv run manage.py cleanup_sessions --days=7
```

### Production database backups

A `db-backup` container runs daily and keeps 7 daily + 4 weekly snapshots
under `./backups/` on the droplet. Restore with `pg_restore`.

## Troubleshooting

**Content didn't update after deploy.**
Check the diff: `git show --stat HEAD | grep content.json`. If
`content.json` isn't in the commit, CI skipped the seed by design.
Re-export, commit, push.

**A new game won't load (FK error on `owner`).**
`export_content` and `seed_db` both null out `Game.owner` to avoid
cross-environment user FK breakage. If you see an `owner` FK error, you
likely loaded an old fixture made before the nullify behavior. Re-export
with `make export-content`.

**Users disappeared after deploy.**
This should be impossible: `seed_db --force` filters by `EXCLUDED_MODELS`
in `quiz/management/commands/seed_db.py` and never touches `auth.user`,
`quiz.userprofile`, or `account.emailaddress`. If it happens, restore
from `./backups/` and open an issue - the filter list has regressed.

## File reference

| File | Role |
|------|------|
| `quiz/fixtures/content.json` | The content payload. Generated, committed, deployed. |
| `quiz/management/commands/export_content.py` | Local DB -> fixture. |
| `quiz/management/commands/seed_db.py` | Fixture -> DB, with model filtering and `--force`. |
| `quiz/management/commands/cleanup_sessions.py` | Remove old live sessions. |
| `Makefile` (`preprod`, `export-content`, `dump-data`) | Author-side commands. |
| `docker-compose.yml` (`web.command`) | Container boot sequence. |
| `.github/workflows/django.yml` | Test + deploy pipeline. |
