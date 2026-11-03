# Deployment and operational security

The repository changes in this workstream reduce dependency risk, accidental build-time secret inclusion, database exposure, and unintended error disclosure. They do **not** establish that a currently running droplet, every old image, or every credential is safe.

For local results and scope, see [Pass 2 verification](verification.md). For dependency maintenance and the short-lived pyasn1 exception, see [dependency policy](../dependency-security/README.md) and [Pass 1 verification](../python-security/verification.md).

## What deployment now enforces

- Deployment waits for both Django tests and the dependency-policy/audit job.
- The SSH action is pinned to reviewed release **v1.2.5**, commit `0ff4204d59e8e51228ff73bce53f80d53301dee2`, rather than mutable `master`.
- Its downloaded drone-ssh helper is explicitly selected as **1.8.2**. The deploy job's GitHub token has only `contents: read` permission.
- Runtime `.env` creation uses `umask 077` and repairs existing files to mode `600` before secret values are appended. This does not revoke copies already made elsewhere or restrict privileged Docker/root users.
- Docker's application-input allowlist excludes `.env`, Sheets credentials, local environments, Node/browser tooling, and unrelated local files from new image builds.
- PostgreSQL is published only on **127.0.0.1:5433**. Web and backup containers still use **db:5432**, with the existing database volume unchanged.

When updating the SSH action, verify the intended upstream release's commit and inspect `action.yml` and `entrypoint.sh`; review changes to helper downloads and credential handling. Update the regression test alongside an intentional pin change. Dependabot can propose action-SHA updates, but they still require review.

**Pinning is not complete SSH supply-chain or identity verification.** The pinned upstream action downloads its selected helper over HTTPS without a repository-pinned checksum. Its version check is not cryptographic integrity verification. The current workflow also does not set the action's `fingerprint` input. Before treating runner-to-droplet authentication as hardened, obtain the server host-key fingerprint through a trusted channel (for example the provider console), register it securely, and deliberately wire mandatory host verification into the workflow. Do not trust an unverified `ssh-keyscan` response as the sole source of identity. No new required secret or host fingerprint was silently invented in this change.

## Recommended GitHub branch protection (manual)

Read-only API inspection on 2026-11-03 found no classic protection or applicable rules for `main`. This work does not change those settings.

After the new workflow has run and GitHub knows its check names, create a ruleset or branch protection for `main`:

1. Require pull requests rather than routine direct pushes.
2. Require the **`test`** and **`dependency-policy`** job checks to pass. Select the actual checks shown by GitHub, not guessed display strings. Consider requiring the **Analyze (Python)** CodeQL check once its normal hosted execution is confirmed.
3. Require branches to be up to date before merge, or use a merge queue if one is introduced later.
4. Block force pushes and branch deletion. Keep any administrator/emergency bypass narrow and explicit.
5. If another maintainer is available, require one approving review and dismiss stale approvals when code changes. Do not configure a solo-maintainer approval requirement with no eligible reviewer and no deliberate emergency process.
6. Consider equivalent check requirements on `dev`, where routine Dependabot updates are directed.

Keep Dependabot alerts/security updates, secret scanning, and push protection enabled (already verified enabled). Require strong account authentication, review repository collaborators and deploy-key access periodically, and avoid automatically merging security-tool updates solely because their tests pass.

## Database access after deployment

There is no need to open PostgreSQL publicly for the web service or backups. Local administration on the droplet can still use Compose:

```sh
docker-compose exec db psql -U "$DB_USER" -d "$DB_NAME"
```

Supply the intended database/user in your administrative environment; do not paste credentials into command history. Existing [backup/restore procedures](../BACKUP_RESTORE.md) still operate through the internal database service.

For a remote database client, use an SSH tunnel with explicit loopback binding (replace `USER@DROPLET`):

```sh
ssh -N -L 127.0.0.1:15433:127.0.0.1:5433 USER@DROPLET
# In another local terminal; psql will prompt for a password if required:
psql -h 127.0.0.1 -p 15433 -U DB_USER -d DB_NAME
```

Do not restore the `0.0.0.0:5433` mapping as a workaround for remote access.

## Rollout and production checks (manual)

No production host was accessed and no deployment was performed by the assistant. Use the normal review/commit/push process, confirm hosted tests/audits, and rebuild/recreate services through the normal deployment. Merely editing Compose does not change an already-running container's port mapping.

On the droplet, verify without printing `.env` or resolved secrets:

```sh
# Validate configuration without dumping interpolated environment values.
docker-compose config --quiet
stat -c '%a %U %n' .env
# Expected .env permissions: 600, owned by the deployment user.
docker-compose port db 5432
# Expected published address: 127.0.0.1:5433
# Optional: inspect only port bindings, not the complete container environment.
docker inspect --format '{{json .HostConfig.PortBindings}}' trivia_app_db
```

Then verify:

- Host/create/join/play flows work over HTTPS, static files load, and the database is healthy.
- A connection to the droplet's **public** address on 5433 fails from a separate machine. Confirm IPv4 and IPv6 firewall policy as applicable. Neither database port 5432 nor 5433 should be publicly allowed.
- Cloud and host firewall rules allow only intended services. Docker-published ports can bypass ordinary UFW rules; do not assume a UFW deny rule alone proves Docker isolation. Docker engines older than 28 also have a documented same-L2 limitation for localhost-published ports: keep the engine maintained and verify the actual firewall/network boundary.
- Backup credentials remain scoped to the backup bucket; media credentials and the SSH deploy account retain only their required permissions. No production IAM/firewall/account permissions were inspected here.
- Application exception logs are visible to operators, not exposed publicly. Do not enable production DEBUG or publish raw error logs to troubleshoot a client error.

## Previously built images and credentials

The old broad Docker copy could include `.env`, `.git`, and local credentials when present in the build context. This establishes a configuration risk, not proof that any particular credential was exposed.

Inventory the old images, registries, build caches, exports, and people/services that could read them. Check relevant access/audit logs. Do not print secret values into tickets, command output, or session transcripts while investigating. Deleting a file in a later image layer does not remove it from earlier layers.

If an image or its layers containing credentials were publicly accessible or accessible to an untrusted party, treat those credentials as compromised: rotate/revoke the affected database, AWS, email, Django signing, Google Sheets, or other credentials as appropriate, update their runtime sources, redeploy, and invalidate affected sessions when rotating signing material. Scope rotation to credentials actually present or plausibly exposed; do not assume every secret was in an image.

Delete/restrict obsolete images and caches deliberately after preserving required incident evidence and rollback/recovery options. Cleanup alone does not invalidate a copied credential. Avoid indiscriminate prune/delete commands against production or backup volumes.

## Error response policy and CodeQL triage

Unexpected errors in the four targeted gallery/admin lookup handlers return stable generic JSON messages. Detailed exception context is logged server-side. Existing status codes are retained; a missing first-question-info result now returns a safe **404 / No questions found** instead of an AttributeError message.

The six CodeQL findings in `quiz/session_api.py` are different: they catch only `InvalidTransition`, whose current constructors in `quiz/session_director.py` use deliberate public messages (fixed text or a numeric unscored-answer count). They do not catch arbitrary database/runtime exceptions and echo them. These actionable HTTP 400 responses are preserved and tested across all six endpoints. Future changes must not wrap arbitrary exceptions or secret/user-controlled text in `InvalidTransition`.

No CodeQL alerts were dismissed or suppressed. A hosted scan must confirm the four repaired findings; the six intentional domain-message findings may still be reported and require human triage rather than a blanket claim that CodeQL is clean.

## Local verification commands

```sh
python tools/test_deployment_security.py
uv run --locked python manage.py test quiz.tests.test_error_responses
uv run --locked python manage.py test quiz
make audit-python
VERIFY_DOCKER_CONTEXT=1 python tools/test_dependency_policy.py
python tools/test_python_audit.py
uv run --locked black . --check
git diff --check
```

The deployment tests normalize a copy of the actual Compose file with dummy values; they never dump the real `.env` or start/reconfigure production services. They also execute only the workflow's secret-file-writing fragment with placeholder secrets in temporary directories, checking both new and formerly world-readable files.
