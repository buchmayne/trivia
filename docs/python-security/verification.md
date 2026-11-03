# Python security remediation — Pass 1

Verified locally on **2026-11-03 UTC**. Nothing was staged, committed, pushed, deployed, or changed in GitHub settings. This follows the initial [dependency-policy/build-isolation work](../dependency-security/verification.md).

## Outcome

- Reviewed all **68 open GitHub Dependabot alerts** against the actual manifests/lockfile. They covered nine packages, including duplicate findings in `pyproject.toml` and `uv.lock` and advisories for features the application does not use.
- The updated locked versions match **none of those 68 vulnerable-version ranges**. This is a local version comparison, **not a claim that GitHub alerts have closed**: they remain tied to the published default branch until reviewed changes reach it.
- The new real Python audit initially found **four more pyasn1 advisories**, which were fixed too. The final `make audit-python` reports **no known vulnerabilities** for the exported requirements applicable to this interpreter/platform.
- Added the same audit to the existing dependency-policy CI job, which is already a prerequisite of deployment.
- No application source or existing browser tests were changed. The previous session's Playwright, lockfile, cooldown, Docker boundary, and Dependabot changes remain intact.

## Reviewed version changes

| Package | Before | After | Context |
| --- | --- | --- | --- |
| Django | 5.2.16 | 5.2.17 | Production; security patch within the existing 5.2 line. GeoDjango is not enabled, but staying patched also avoids relying on feature-specific exclusions. |
| Django REST Framework | 3.16.0 | 3.18.2 | Production; application API uses DRF viewsets/content negotiation. Fixes request-processing issues; token-auth-specific advisories are not evidence this app uses token auth. |
| Pillow | 12.3.0 | 13.0.0 | Production; image upload conversion and backfill use Pillow decoding. Upstream fixes image-decoder/encoder issues; not every affected format/path is used here. |
| urllib3 | 2.7.0 | 2.8.0 | Production; also used transitively by AWS tooling. Fixes response/proxy processing. |
| sqlparse | 0.5.5 | 0.6.0 | Production via Django; fixes parser complexity issues. No direct public arbitrary-SQL parser endpoint was found. |
| certifi | 2026.7.22 | 2026.10.18 | Development dependency graph; refreshed CA trust bundle. Not present in the verified production image. |
| cryptography | 49.0.0 | 50.0.0 | Development dependency graph; no application PKCS#7 decryption API was found. Not present in the verified production image. |
| oauthlib | 3.3.1 | 4.0.0 | Development Google Sheets tooling; application is not an OAuth authorization server. Not present in the verified production image. |
| Black | 26.3.1 | 26.10.1 | Development formatter. The flagged upstream GitHub Action configuration is not used here; upgraded without changing repository formatting. |
| pyasn1 | 0.6.4 | 0.6.5 | Transitive development dependency; four additional decoder CPU-exhaustion advisories found by the new scanner. Not present in the verified production image. |

Direct dependency minimums/pins were raised where appropriate. Other fixes remain transitive locked dependencies rather than unnecessary application dependencies.

### Compatibility and lockfile scope

**Python 3.11+ is now required** because Pillow 13 explicitly removes Python 3.10 support. Production/CI already use Python 3.13. This must not be advertised as retaining Python 3.10 compatibility.

Apart from the ten targeted package upgrades, no existing package version was upgraded. Dropping Python 3.10 removes its obsolete numpy/pandas lockfile branches and the now-unused `pytz` dependency. Existing versions for the remaining interpreters were retained. The new optional `security` group adds `pip-audit==2.10.1` and its dependencies; these are included in the lockfile and audited, not copied into the production environment by `--no-dev`.

### Release review and bounded emergency exception

Checked fixed versions against GitHub advisory data, publisher release notes, and PyPI release metadata. All 29 newly selected package/version pairs (fixes and scanner dependencies) were non-yanked and had no active advisories in their PyPI metadata. All locked artifact upload timestamps meet the seven-day rule except the two explicitly exempted pyasn1 artifacts.

pyasn1 0.6.5 was uploaded on **2026-10-27 at 06:32:48–49 UTC**, a few hours short of seven days at verification time. Rather than leave four known vulnerabilities or disable the policy globally, `pyproject.toml` contains:

```toml
exclude-newer-package = { pyasn1 = "2026-10-28T00:00:00Z" }
```

This permits only that package's artifacts uploaded before a fixed date; **it does not admit future pyasn1 releases**. The exact reviewed version is locked to 0.6.5. All other packages retain the ordinary seven-day cutoff.

**Removal:** on/after **2026-11-03 06:33 UTC**, remove the `exclude-newer-package` line and its explanatory comments, then run:

```sh
uv lock
uv sync --locked
make audit-python
```

Verify pyasn1 remains at 0.6.5. This exception addresses:

- [GHSA-mm57-4v3p-rchx](https://github.com/advisories/GHSA-mm57-4v3p-rchx)
- [GHSA-2qm8-x737-gmw5](https://github.com/advisories/GHSA-2qm8-x737-gmw5)
- [GHSA-9m75-vc3g-4x39](https://github.com/advisories/GHSA-9m75-vc3g-4x39)
- [GHSA-fm9c-5rcf-2q5p](https://github.com/advisories/GHSA-fm9c-5rcf-2q5p)

Publisher references: [Pillow 13](https://github.com/python-pillow/Pillow/releases/tag/13.0.0), [DRF 3.18.2](https://github.com/encode/django-rest-framework/releases/tag/3.18.2), [Django 5.2.17](https://docs.djangoproject.com/en/5.2/releases/5.2.17/), [urllib3 2.8](https://github.com/urllib3/urllib3/blob/2.8.0/CHANGES.rst), [sqlparse 0.6](https://github.com/andialbrecht/sqlparse/blob/0.6.0/CHANGELOG), [cryptography 50](https://github.com/pyca/cryptography/blob/50.0.0/CHANGELOG.rst), [OAuthlib 4](https://github.com/oauthlib/oauthlib/blob/v4.0.0/CHANGELOG.rst), [pyasn1 0.6.5](https://github.com/pyasn1/pyasn1/releases/tag/v0.6.5).

## Checks actually run

| Check | Result |
| --- | --- |
| `make audit-python` on macOS/Python 3.13 | **No known vulnerabilities** |
| Equivalent locked all-group audit in disposable Linux/Python 3.13 container | **No known vulnerabilities** |
| Real scanner against old pinned-version metadata | **Exit 1**, findings in all ten affected packages; no old package was installed by this scan |
| Real scanner with uncached advisory query through an unreachable local proxy | **Exit 1**; service failure is not treated as a clean scan |
| `python tools/test_python_audit.py` | **2 tests passed**, including four Makefile success/failure subcases |
| `VERIFY_DOCKER_CONTEXT=1 python tools/test_dependency_policy.py` | **5 tests passed** |
| `uv lock --check`, `uv sync --locked` | Passed |
| Django application tests after the final package upgrade | **458 passed** |
| Django system check and `makemigrations --check --dry-run` | Passed; no model changes |
| `uv run --locked black . --check` | Passed; **110 Python files**, no application reformatting required |
| `npm audit` | **0 known vulnerabilities** |
| Locked artifact age check | **782 artifacts**; only the two documented pyasn1 artifacts younger than seven days |
| Production Docker build | Passed; local image `trivia-python-security:local` |
| Built image with `--network none`: Django system check | Passed |
| Built image with `--network none`: static collection | Passed; **363 static files** |
| Built image versions, fixture, secret/tooling exclusions | Verified patched Django/DRF/Pillow; seed fixture present; `.env`, Sheets key, Node modules, audit tooling, Black, numpy, pandas absent |
| Chromium regressions | **50 passed, 1 failed**; existing final-round label race described below |
| Focused mobile Safari My Games / host recovery | **2 passed** |

The audit-command tests execute the real Makefile with a substitute external `uv` process to verify locked/all-group export, exact scanner invocation, failure propagation, and temporary-file cleanup. A separate test invokes real offline uv exports, compares all exported package/version pairs to the lockfile, verifies the project itself is omitted, and verifies scanner/dev tools are excluded from the production graph. The scanner's success, vulnerable-input, and service-failure paths were also exercised separately against the real advisory API.

### Existing browser failure reproduced on the baseline

Browser checks used fresh, migrated, seeded local PostgreSQL databases and dedicated servers, not the normal development database/server. Temporary servers and databases were removed afterward. Chromium excluded the same three diagnostic/QA scenarios as the previous session; WebKit coverage was the two My Games cases, not the full cross-browser matrix.

`e2e/tests/host-round-advance-label.spec.ts` sometimes reads the previous nonempty button label before the final-round leaderboard fetch updates it. It then invokes `adminStartNextRound`, which waits for `#playingState` even though the game just completed. The failure is a ten-second timeout at `e2e/helpers/session-helpers.ts:211`.

To distinguish a regression from timing noise, ran that test three times against **each** dependency set, using separate freshly seeded databases, unchanged app/test sources, the same Playwright release, and Python **3.13.1**:

- Old dependency baseline: **1 passed, 2 failed**.
- Updated dependencies: **1 passed, 2 failed**, with the identical timeout and stale label.

This is an existing intermittent failure, not a clean full-browser-suite result. It was not hidden with retries, weakened assertions, or an unrelated application/test change in this security pass. Its fix remains a separate task.

## Limits and remaining steps

- The scanner evaluates environment markers for its Python/platform; audits passed locally on both macOS/Python 3.13 and a disposable Linux/Python 3.13 container. The hosted CI job still needs to run after pushing. This is not a comprehensive scan of all universal-lockfile variants, OS packages, base images, or browser binaries.
- Local advisory sources and GitHub use different advisory identifiers/aggregation, so their finding counts need not match. Neither count establishes application exploitability.
- No hosted workflow or Dependabot refresh has run for these unpushed changes. Do not dismiss GitHub alerts as a substitute for landing fixed manifests/lockfile on the default branch.
- Remove the bounded pyasn1 exception after the timestamp above.
- Review/commit through the normal human process, allow hosted CI to pass, and deploy a rebuilt image before claiming production remediation.
- `git diff --check` passed. Temporary browser databases/servers and the isolated old-dependency virtual environment were removed; the normal development server was left alone.
- **Subsequent Pass 2:** deployment action pinning, database host binding, unintended exception disclosure, and operational guidance are recorded separately in [deployment security verification](../deployment-security/verification.md). No rollout or credential-exposure investigation was performed.
