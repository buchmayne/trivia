# Standalone SQLite studio sandbox — design

The studio's first human workflow test must not connect to, migrate, or write the normal local PostgreSQL database. Reuse the existing `studio` Django app, but run it as a separate, localhost-only Django site with its own settings and URL configuration. Do not fork the authoring logic or replace the legacy site's settings.

## Isolation boundary

- A dedicated `studio_sandbox` settings module installs only Django auth, content types, sessions, messages, static files, and `studio`. It does not import `pub_trivia.settings`, load `.env`, install `quiz`, or configure PostgreSQL, S3, Redis, or outbound email.
- Its only database is an ignored on-disk SQLite file under `.studio-sandbox/`. Any future studio media must use a separate local storage directory there. Studio routes remain gated by DEBUG, the opt-in flag, and a staff login created in this sandbox database.
- A dedicated entry point explicitly selects sandbox settings and rejects `--settings` overrides. Sandbox-only URLs expose login and `/studio/`, not quiz, admin, or production routes. Use a distinct cookie name and a localhost-only server port so that browser sessions do not interfere with the regular application.
- Sandbox initialization and teardown must be explicit. No project-level `.env` or main settings changes are needed. Deleting `.studio-sandbox/` removes its database, login, drafts, and local files; it does not undo or change anything in the dev PostgreSQL database.

## Verification

Use Django's own migrations on SQLite, including the auth/session tables. Exercise a login, draft capture, choose-one task and option entry, Ready validation, previews, and game placement with sandbox-only tests. Verify the sandbox has no `quiz` app or PostgreSQL connection configured and that its ignored database files remain untracked. Continue to run the existing PostgreSQL-backed suite separately for backend-specific behavior (SQLite does not exercise the same concurrency/locking semantics). Browser verification remains a separate manual step when a real browser is available.
