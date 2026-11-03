# Deployment security verification — Pass 2

Verified locally on **2026-11-03 UTC**. No files were staged or committed, no code was pushed or deployed, and no GitHub settings, secrets, credentials, IAM policies, firewalls, or production containers were changed.

## Implemented

- Replaced `appleboy/ssh-action@master` with release **v1.2.5**'s full commit SHA, `0ff4204d59e8e51228ff73bce53f80d53301dee2`.
- Explicitly selected its **drone-ssh 1.8.2** helper and limited the deploy job token to `contents: read`.
- Made runtime `.env` owner-only before writing secret values, using `umask 077` and `chmod 600` for both new and existing files.
- Changed PostgreSQL's host binding from all interfaces on port 5433 to **127.0.0.1:5433**. Its internal port, web/backup hostname, and persistent volume are unchanged.
- Replaced unexpected exception text in four view handlers with stable generic JSON messages plus server-side exception logging. Preserved existing error status codes; the missing first-question-info case now returns an intentional safe 404 instead of exposing AttributeError text.
- Preserved deliberate `InvalidTransition` HTTP 400 messages, documented their public-message contract next to the exception class, and exercised all six affected API endpoints with real lifecycle failures.
- Added deployment/configuration regression tests to the existing dependency-policy CI gate.
- Added [operational guidance](README.md) covering branch protection, safe database tunnels, rollout checks, old-image exposure assessment, credential rotation criteria, and residual SSH/download verification limits.

The existing dependency policy, Python security fixes, npm lockfile, Docker allowlist, and uncommitted work were preserved. The temporary pyasn1 cooldown exception from Pass 1 is still bounded and remains scheduled for removal after **2026-11-03 06:33 UTC**; see [Pass 1 verification](../python-security/verification.md#release-review-and-bounded-emergency-exception).

## Action review

Read-only upstream inspection confirmed that tag `v1.2.5` points directly to the selected commit. Its commit date is **2026-01-28**, GitHub reports its commit signature verified, and the release was published that day. Inspected the pinned `action.yml` and `entrypoint.sh`, including supported inputs, secret passing, helper selection, download behavior, and output handling. Helper **1.8.2** was published **2025-11-28** and matches the pinned entry point's default. Both are well beyond the seven-day release window; no new action/helper age exception was introduced.

These checks establish the reviewed versions and behavior, not an independent security audit. The helper still downloads over HTTPS without a repository-pinned checksum, and the workflow does not yet configure mandatory SSH host-key fingerprint verification. No required secret was invented or silently introduced to enable it. Those limits are explicit in the operational guide.

Sources: [action release](https://github.com/appleboy/ssh-action/releases/tag/v1.2.5), [pinned action](https://github.com/appleboy/ssh-action/blob/0ff4204d59e8e51228ff73bce53f80d53301dee2/action.yml), [pinned entry point](https://github.com/appleboy/ssh-action/blob/0ff4204d59e8e51228ff73bce53f80d53301dee2/entrypoint.sh), [helper release](https://github.com/appleboy/drone-ssh/releases/tag/v1.8.2).

## Checks and results

| Check | Result |
| --- | --- |
| New view-error tests before implementation | Failed on missing logs, raw error behavior, and the missing-question status; six deliberate lifecycle-error cases already passed |
| `uv run --locked python manage.py test quiz.tests.test_error_responses` | **10 passed**, including eight unexpected-error/DEBUG subcases and all six lifecycle-error endpoints |
| Full Django suite | **468 passed** |
| `python tools/test_deployment_security.py` | **3 passed** |
| `python tools/test_python_audit.py` | **2 passed** |
| `VERIFY_DOCKER_CONTEXT=1 python tools/test_dependency_policy.py` | **5 passed** |
| `make audit-python` | **No known vulnerabilities** |
| `npm audit` | **0 known vulnerabilities** |
| `uv lock --check` | Passed |
| Black check | Passed; **112 Python files**, no unrelated formatting changes |
| Django system check and migration check | Passed; no model changes |
| Workflow, Dependabot, Compose YAML parsing | Passed |
| Production Docker build | Passed; local image `trivia-deployment-security:local` |
| Built image with networking disabled: Django check and static collection | Passed; **363 static files collected** |
| Chromium host/team flow tests | **23 passed** |
| Mobile Safari My Games/host-recovery tests | **2 passed** |
| `git diff --check` | Passed |

### What the tests actually exercise

The error tests call the real routed views while making their underlying query dependencies raise a distinctive exception. With **DEBUG both false and true**, response content must stay generic while a server-side log record retains that exact exception and traceback. Separate tests exercise an actual malformed ORM input, the empty lookup, and the successful response shape. Lifecycle tests invoke the real SessionDirector/API without replacing the transition logic.

Deployment tests normalize a copy of the actual Compose configuration with **placeholder environment values**, verifying the loopback host binding, internal web/backup DB routes, and unchanged named volume. They execute only the actual workflow's secret-file-writing fragment with placeholder secrets in temporary directories, checking mode 600 for both new files and old mode-644 files. They also assert the reviewed action/helper pins, deploy permissions, and CI prerequisites. They never connect to a droplet or execute the SSH/prune/deploy script.

Browser checks used a freshly created, migrated, seeded PostgreSQL database and a separate server on port 8766. The server and database were removed afterward; the normal development server was not modified. This pass ran the focused 23 Chromium host/team cases and two WebKit My Games cases with **no retries**, not the full browser matrix. The existing final-round label race reproduced against both dependency sets in Pass 1 was not changed or rerun here.

## CodeQL triage

Read-only GitHub inspection found ten open `py/stack-trace-exposure` alerts before this pass:

- **Four genuine unexpected-error disclosures in `quiz/views.py`** (original alerts 7–10): repaired locally and covered by failure-path tests. Hosted CodeQL has not yet rerun on these unpushed changes, so alert closure is not claimed.
- **Six intentional domain-error messages in `quiz/session_api.py`** (original alerts 1–6): catch only `InvalidTransition`; its constructors currently contain fixed user-safe text or an integer answer count. Kept these actionable validation errors and tested all six endpoints. Do not wrap arbitrary exceptions or request/secret text in this exception in future.

No alerts were dismissed, no CodeQL query was disabled, and no suppression annotations were added. The six domain-message alerts may remain visible for human triage.

## Remaining human/environment steps

1. Review and commit/push through the normal human process, let the actual hosted Actions/audits/CodeQL run, and deploy a rebuilt image/recreated containers. Local config tests do not prove the current production database listener or firewall is restricted.
2. Apply the [branch-protection recommendations](README.md#recommended-github-branch-protection-manual) after GitHub knows the new check names. Read-only inspection still found `main` unprotected, with no applicable rules; no settings were changed.
3. Verify the deployed `.env` permissions, loopback binding, external database-port denial, HTTPS app flows, and backup health. Keep the Docker engine maintained and verify cloud/host firewall behavior, including Docker/UFW and old-engine localhost-publication caveats.
4. Assess old images/build caches/registry access and rotate affected credentials if exposure is plausible. No deployed image, access logs, or credential values were inspected here.
5. Deliberately configure mandatory SSH host-key verification using a fingerprint obtained through a trusted channel. Version pinning alone does not authenticate the droplet or checksum the helper download.
6. Remove the temporary pyasn1 exception after its documented maturity timestamp.

These are concrete rollout/operational tasks, not a claim that the repository work makes the entire project secure or that a production incident has occurred.
