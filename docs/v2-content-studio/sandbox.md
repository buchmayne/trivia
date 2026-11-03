# Try the standalone content studio

This is an independent localhost-only Django site backed by `.studio-sandbox/studio.sqlite3`. Its settings do **not** import the normal project settings or `.env`, install `quiz`, or configure PostgreSQL/S3. The database, signing key, and (eventual) local media all live under the ignored `.studio-sandbox/` directory. Your regular local development database is not used by these commands.

From the repository root:

```bash
uv run python -m studio_sandbox.manage check
uv run python -m studio_sandbox.manage migrate
uv run python -m studio_sandbox.manage createsuperuser
uv run python -m studio_sandbox.manage runserver
```

`createsuperuser` prompts for a new **sandbox-only** login; it does not use your regular dev account. Open <http://127.0.0.1:8765/studio/> and sign in when redirected. Prefer this address rather than `localhost` to keep its browser cookies separate from a normal dev server opened as `localhost`. The launcher refuses non-loopback binding and settings overrides. Do not use `manage.py`, `make run`, or `docker-compose up` for this sandbox: those start the regular site with its regular database configuration.

## Try a real question

1. Create a category if necessary. Capture a challenge with just a working title or rough notes, then find it again in the library.
2. Open the challenge and add shared question text. Add a task, choose **Choose one**, and save. Add at least two options on the task page, then select and save its correct option. Add optional reveal details to an option.
3. Try **Mark Ready** before completing an option/key to see validation, then complete it and mark Ready. Compare **Question preview** (no answer/reveal) with **Reveal preview**.
4. For a multipart question, add another task with its own prompt, options, correct item and point value. Change the order of options and check the correct answer remains attached to the option, not to the letter.
5. Create a game and round under **Games**, place the Ready challenge, and preview it. Edit the challenge and revisit the game preview: placements reuse the current challenge content.

This prototype currently supports free-text and choose-one tasks, text blocks, and previews. Matching, ranking, uploads, and live gameplay are not implemented yet. The SQLite sandbox is for workflow evaluation; it does not replace running the PostgreSQL-backed automated tests before integrating these changes into the normal site.

## Stop or reset

Stop the sandbox server with Ctrl-C. All its persistent state is in `.studio-sandbox/`. To start from scratch, first make sure you are in the repository root, then remove **only** that directory:

```bash
rm -r .studio-sandbox
```

Repeat `migrate` and `createsuperuser` to recreate a fresh sandbox. Your normal database is unchanged throughout.

Sandbox checks (using a temporary SQLite test database rather than the persistent sandbox file):

```bash
uv run python -m studio_sandbox.manage test studio_sandbox
```
