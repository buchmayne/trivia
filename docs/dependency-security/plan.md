# Dependency security implementation plan

Approved in conversation: retain Playwright, use a seven-day release cooldown for npm and Python, update the supported uv version, add routine npm updates, and isolate production build inputs. No commits are authorized.

## 1. Enforce the release policy and preserve reproducible installs

- **Goal:** New registry resolutions avoid releases younger than seven days; ordinary installs use reviewed lockfiles.
- **Files:** `.npmrc`, `package.json`, `package-lock.json`, `pyproject.toml`, `uv.lock`, `Makefile`, `Dockerfile`, `.github/workflows/django.yml`.
- **Approach:** Require npm with minimum-release-age support and modern uv with duration-based `exclude-newer`; disable npm dependency install scripts; pin the reviewed uv bootstrap version in CI and Docker. Use `npm ci` and `uv sync --locked`. Update only Playwright and its browsers, preserving unrelated Python dependency versions where possible.
- **Acceptance:** Unsupported clients fail rather than silently dropping protections; updated Playwright and its npm dependencies meet the cooldown; both lockfiles install successfully. Existing Python versions are not broadly upgraded.
- **Verify:** Configuration regression tests; synthetic local-registry resolution checks; `npm ci`; `npm audit`; `uv lock --check`; `uv sync --locked`; browser test discovery and execution.

## 2. Monitor routine updates and isolate production inputs

- **Goal:** Routine update PRs observe the cooldown, and production images contain application inputs rather than developer tooling or secrets.
- **Files:** `.github/dependabot.yml`, `.dockerignore`, dependency-policy tests.
- **Approach:** Add weekly npm updates and seven-day npm/Python cooldowns; use Dependabot's native uv support for `uv.lock`. Allowlist the application files needed by the Python image and explicitly keep secrets/caches out. Preserve Docker Compose's existing runtime environment injection.
- **Acceptance:** Application code, templates, static sources, and seed fixtures remain available; `.env`, credentials, Node dependencies, browser artifacts, and local virtual environments are excluded. Security update handling remains distinct from routine cooldowns.
- **Verify:** Parse the YAML; test policy consistency; build/export a scratch-image copy of the real Docker context and inspect included/excluded paths; attempt the production build and Django checks.

## 3. Document maintenance and verify

- **Goal:** Explain the npm/Python equivalents, the limits of age filtering, and the reviewed security-fix override.
- **Files:** `docs/dependency-security/README.md`, `README.md`.
- **Approach:** Document supported clients, locked installs, explicit updates, browser refreshes, npm script restrictions, and temporary package-scoped exceptions. Record actual test outcomes and limitations in the final report.
- **Acceptance:** A maintainer can install, update, audit, and deliberately override the cooldown without changing the default policy permanently. Documentation does not claim age is proof of safety or that frozen lockfile installs re-vet every artifact's age.
- **Verify:** Execute documented ordinary-install commands; run policy regression tests and the project's Django/browser suites where feasible.

## Scope boundaries

No replacement of Playwright, application behavior changes, automatic merging, unrelated Python upgrades, production deploy, secret-value inspection, or commits. A cooldown is a delay before selecting new registry releases, not a guarantee against compromise, a scan of browser binaries, or a substitute for lockfile review. npm's rule does not cover the separately downloaded Playwright browsers; their versions follow the reviewed Playwright release. Emergency security patches require a deliberate, reviewed exception.
