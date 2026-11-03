# Dependency security verification

Verified locally on **2026-11-03 UTC**. Nothing was committed or deployed.

This records the **initial dependency-policy/build-isolation implementation**, before the Python vulnerability remediation. For subsequent package upgrades, audit coverage, and current results, see [Python security verification](../python-security/verification.md).

## Implemented

- Playwright **1.58.1 → 1.64.1**, with matching Chromium and WebKit browsers installed.
- Seven-day minimum release age for new npm and Python registry resolutions.
- npm dependency installation scripts disabled; unsupported npm/Node clients rejected through strict engine requirements.
- Local uv **0.5.18 → 0.13.5**; that reviewed bootstrap version is pinned in Docker and CI.
- **No Python package versions changed.** The uv lockfile refresh primarily adds artifact upload timestamps and the relative cutoff metadata, with some redundant environment markers normalized by the newer resolver.
- `package-lock.json` removed from `.gitignore`, so the reviewed npm dependency set can be included in version control.
- Weekly npm and native uv Dependabot updates, with a seven-day routine-update cooldown.
- Production Docker context restricted to application inputs, excluding secrets and developer tooling.
- CI policy/audit job added and made a prerequisite of deployment.
- Setup, update, emergency-exception, and limitation documentation in [README.md](README.md).

## Checks and results

| Check | Result |
| --- | --- |
| Synthetic npm/uv policy and Docker allowlist tests | **5 passed** |
| Django application tests | **458 passed** |
| Chromium browser regression suite | **51 passed** |
| Mobile Safari / WebKit My Games and host-recovery tests | **2 passed** |
| Browser-test discovery | **54 tests found in 13 files** for Chromium |
| `npm ci` | Passed; installs the reviewed lockfile |
| `npm audit` | **0 known npm vulnerabilities** |
| npm registry publication-time check | All six locked npm dependency versions older than seven days |
| Python artifact timestamp check | All **820** locked registry artifacts older than seven days |
| `uv lock --check` and `uv sync --locked` | Passed |
| `uv run --locked python manage.py check` | Passed |
| `uv run --locked black . --check` | Passed; 109 Python files checked |
| YAML parsing and Dependabot cooldown/deployment-gate checks | Passed |
| `git diff --check` | Passed |
| Production Docker build | Passed |
| Built image: Django system check, with networking disabled | Passed |
| Built image: static collection, with networking disabled | Passed; **372 files collected** |
| Actual repository Docker context export/inspection | Application inputs and seed fixture present; `.env`, credentials, Node dependencies, local environments, browser artifacts, and other excluded inputs absent |

The policy tests exercise real npm and uv commands against harmless local registries. They verify direct and transitive cooldowns, failure when only a too-new release satisfies the constraint, suppressed npm install scripts, unsupported npm-engine rejection, reproducible locked installs, and package-scoped emergency exceptions. Docker's actual build-context matching is also tested, including nested secret/cache fixtures.

## Browser test isolation and scope

Browser tests ran against a freshly created, migrated, seeded PostgreSQL database and a separate local development server on port 8765. The temporary database and server were removed afterward; the normal development server was left alone.

Chromium command, with `CI=1` and `BASE_URL` set to the isolated server:

```sh
npm test -- --project=chromium \
  --grep-invert='Diagnostic Test|Robust QA|Visual QA' \
  --retries=0 --reporter=line --timeout=20000 --max-failures=5
```

The three QA/diagnostic scenarios were deliberately excluded; they are not included in the 51 passing browser regressions.

The additional WebKit check was:

```sh
npm test -- my-games.spec.ts --project=mobile-safari \
  --retries=0 --reporter=line --timeout=20000 --max-failures=2
```

This is focused WebKit coverage, not a claim that the full suite ran on every configured browser/device.

## Existing type-check errors

```sh
./node_modules/.bin/tsc --noEmit -p e2e/tsconfig.json
```

This still reports **13 existing TypeScript diagnostics** in `e2e/helpers/robust-helpers.ts` and `e2e/tests/qa-robust.spec.ts`: nullable values, unresolved `CODE` / `ADMIN_TOKEN` identifiers, an incompatible error-property type, and an implicit-any parameter.

An isolated baseline copy using the previous **Playwright 1.58.1**, the same TypeScript version, and the same Node types produced **identical diagnostic output** to Playwright 1.64.1. These are not introduced by the upgrade and were left unchanged rather than expanding this security task into QA-helper fixes.

## Remaining human/environment steps

- Review and include the new `package-lock.json` alongside the manifest/configuration changes. No files were staged or committed by the assistant.
- GitHub **Dependabot alerts** and **Dependabot security updates** were subsequently verified enabled through read-only API checks, along with secret scanning and push protection. No remote settings were changed.
- Let the new workflow run on GitHub after pushing; local checks are not a hosted Actions/Dependabot execution.
- Deploy a rebuilt image through the normal process to apply the production build exclusions. Existing images are not retroactively cleaned; assess old-image access and credential rotation separately if needed.

Zero npm advisories and a seven-day wait are not guarantees of safety, and neither is a full scan of browser executables or the production image.
