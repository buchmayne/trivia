# Deployment and error-boundary hardening — Pass 2

Approved in conversation on 2026-11-03 after review of Pass 1. Preserve all existing uncommitted work. No commits, pushes, deployment, credential rotation, remote GitHub changes, or alert dismissals are authorized.

## Design

Keep the current deployment architecture and application response shapes. Make the SSH deployment implementation reproducible by pinning a reviewed published action commit and its explicitly selected drone-ssh version. Keep deploy-job token permissions read-only. Ensure newly written runtime `.env` files are owner-only, including files left by older deployments.

Publish PostgreSQL on `127.0.0.1:5433` only; do not change its internal port, volumes, application/backup service hostname, or normal container-to-container connectivity. Remote administrative access should use SSH forwarding, not a public database listener. Existing deployed containers do not change until recreated by a normal deployment.

Replace four broad exception-to-response conversions in `quiz/views.py` with stable public messages and server-side exception logging. Preserve their existing error status codes. Return the existing safe `No questions found` message with HTTP 404 when the first-question-info lookup finds no question, rather than exposing an AttributeError. Do not alter the six `InvalidTransition` responses: these are deliberate application-domain errors constructed from fixed messages or a numeric answer count, not arbitrary database/runtime exceptions. Document that triage and test real validation behavior rather than suppressing CodeQL alerts.

## Tasks and acceptance

### 1. Deployment boundary

- **Files:** `.github/workflows/django.yml`, `docker-compose.yml`, `tools/test_deployment_security.py`.
- **Approach:** Verify the released SSH action SHA/source and helper version; pin them. Narrow database host binding. Set restrictive runtime secret-file permissions before secret values are written.
- **Acceptance:** No mutable SSH action ref; no broad database host binding; web/backup internal connectivity and persistent volume remain unchanged; runtime `.env` is readable only by its owner. No new required GitHub secret is silently introduced.
- **Verify:** Offline configuration regression tests; normalize the actual Compose file with placeholder environment values and assert host binding/internal connections; inspect pinned upstream sources. Do not connect to production or execute SSH deployment locally.

### 2. Public error boundary

- **Files:** `quiz/views.py`, `quiz/tests/test_error_responses.py`; session-director/API code only if tests reveal an unintended disclosure.
- **Acceptance:** Unexpected exception text is absent from HTTP responses with DEBUG both off and on, full exception context is retained in server logs, successful response shapes remain covered, and meaningful lifecycle/validation messages are unchanged.
- **Verify:** Test failure branches through real views with failing underlying query dependencies, assert logs and response content; exercise all six domain-error endpoints using real SessionDirector transitions. Run the full Django suite and browser smoke checks.

### 3. Operational handoff

- **Files:** `docs/deployment-security/README.md`, `docs/deployment-security/verification.md`, root README and relevant existing security docs.
- **Acceptance:** Explain recommended branch protection without changing it; provide safe post-deploy database/access/image/credential checks; distinguish action pinning from binary checksums and SSH host-key verification. Record tests actually executed, CodeQL triage, and remaining environment limitations.
- **Verify:** Documentation link checks, `git diff --check`, production image build/system checks. Hosted Actions/CodeQL and deployed firewall/image state remain unverified until the human rollout.

## Out of scope

Fixing the existing final-round browser race, replacing the SSH deployment architecture, changing game authorization, introducing remote secrets, changing nginx/TLS behavior, blanket suppression of CodeQL, automatic cleanup of old production images, or applying branch rules remotely. The temporary pyasn1 exception from Pass 1 remains subject to its separately documented removal time.
