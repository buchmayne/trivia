# Python vulnerability remediation (Pass 1)

Approved in conversation on 2026-11-03: address the existing Python vulnerability backlog before reviewing deployment hardening. Preserve the previous session's uncommitted dependency/build-isolation work. No commits, deployment, credential rotation, remote settings changes, or alert dismissals are authorized.

## Design and invariants

Use targeted upgrades for the nine packages named in the current Dependabot alerts, plus dependency changes required by those upgrades and the new audit tool. Prefer the first reviewed fixed release over a blanket latest-version refresh. Keep the global seven-day artifact cooldown and both reviewed lockfiles. Raise direct dependency floors/pins where they would otherwise permit known-vulnerable releases. Keep transitive packages transitive and record their reviewed versions in `uv.lock`.

Pillow 13 requires Python 3.11+, so the application metadata must stop advertising Python 3.10 support. Production and CI already run Python 3.13. Do not keep a vulnerable Pillow version for Python 3.10.

Add a pinned `pip-audit` in an optional `security` dependency group, excluded from the production image. Audit a locked export of all Python dependency groups, including the audit tooling, rather than the incidental packages installed on one machine. Do not install packages from the exported requirements during auditing, automatically fix dependencies, or suppress advisories. Advisory-service/network failures must fail the CI check. Reuse the existing dependency-policy deployment gate.

Do not change application behavior except compatibility fixes demonstrably required by these upgrades. Keep deployment hardening (Pass 2) separate.

## 1. Validate and remediate the alerts

- **Goal:** The reviewed Python lockfile no longer matches the current advisory ranges.
- **Context/source:** The security assessment and approved Pass 1; 68 GitHub alerts across nine packages (including duplicate manifests and feature-specific issues).
- **Files:** `pyproject.toml`, `uv.lock`, application/tests only if required for compatibility.
- **Approach:** Check GitHub advisory ranges and PyPI fixed-release metadata, age, Python requirements, and publisher release information. Upgrade only affected packages and required dependencies. Document applicability without treating every alert as an exploitable application path.
- **Acceptance:** Fixed versions satisfy the cooldown without a blanket exception; unrelated existing packages stay locked where possible; manifests accurately declare supported Python versions.
- **Verify:** `uv lock --check`; `uv sync --locked`; compare pre/post package sets and artifact timestamps; run vulnerability audit, Django tests, browser regressions, and production image checks.

## 2. Prevent unnoticed Python vulnerability regressions

- **Goal:** Local maintainers and CI can scan the same reviewed dependency set.
- **Files:** `pyproject.toml`, `uv.lock`, `Makefile`, `.github/workflows/django.yml`, `tools/test_dependency_policy.py`, `docs/dependency-security/README.md`.
- **Approach:** Add an optional pinned audit-tool group and `make audit-python`; export the locked all-group requirements to a temporary file, audit without dependency resolution/installation, and remove the file on success or failure. Invoke it from the existing dependency-policy job.
- **Acceptance:** Known advisories and service errors produce a nonzero exit; all dependency groups are covered; the application itself is not queried as a public package; scanner tooling stays outside production installs; no permanent advisory ignore list is added.
- **Verify:** Execute the real audit against the lockfile and a harmless known-vulnerable requirements fixture; test locked export scope and production exclusion; rerun dependency-policy tests including Docker context behavior.

## 3. Record verification and remaining rollout steps

- **Goal:** The review distinguishes local remediation from hosted alert closure and deployed protection.
- **Files:** `docs/python-security/verification.md`, `docs/dependency-security/README.md`, `docs/dependency-security/verification.md`.
- **Acceptance:** Record exact version changes, checks actually run, unresolved findings, compatibility implications, and any unavailable verification. GitHub alerts are not claimed closed before the default branch is updated, and production is not claimed fixed before deployment.
- **Verify:** Review documentation against command output; `git diff --check`; confirm no unrelated source/data files changed.
