# Dependency security and updates

## Policy

Keep Playwright for browser coverage. Wait **seven days** before selecting newly published npm packages or Python registry artifacts. Review dependency updates and their lockfile changes before merging; do not automatically merge them.

The cooldown is an extra defense against a compromised publisher releasing malware. Seven days gives the community a detection window, **not a guarantee that a release is safe**. Older releases can still be malicious or vulnerable, and urgent security patches sometimes need a reviewed exception.

### Supported tools

- Node.js **22.9+**, preferably the Node 24 LTS line.
- npm **11.17.0+**. CI uses the reviewed version **11.17.0**.
- uv **0.13.5+**. CI and the production image use the reviewed version **0.13.5**.
- Python **3.11+** is required by the application (Pillow 13 drops Python 3.10). Production and CI use **3.13**. The standalone policy tests require Python 3.11+.

`.npmrc` enables `engine-strict` and `package.json` declares the required Node/npm versions. `pyproject.toml` declares uv's `required-version`. Unsupported clients must fail instead of silently omitting the policy.

If upgrading an existing standalone uv installation:

```sh
uv self update 0.13.5
```

For pip-managed uv installations instead:

```sh
python -m pip install uv==0.13.5
```

For an older npm installation:

```sh
npm install --global npm@11.17.0 --ignore-scripts
```

These bootstrap tools are pinned to explicitly reviewed versions, rather than downloading the latest release on every CI run or Docker build. When changing those pins, verify the new tool release is at least seven days old and update Docker, CI, the supported-version declaration, the policy test, and this document together. The initial uv/tooling update refreshed lockfile metadata without upgrading Python packages. The subsequent [Python security pass](../python-security/verification.md) upgrades affected Python packages separately.

## Python/npm equivalents

| Task | Python / uv | npm |
| --- | --- | --- |
| Dependency declarations | `pyproject.toml` | `package.json` |
| Reviewed exact versions and artifact hashes | `uv.lock` | `package-lock.json` |
| Install the reviewed set, without rewriting the lockfile | `uv sync --locked` | `npm ci` |
| Add a dependency | `uv add PACKAGE` | `npm install --save-dev PACKAGE` |
| Upgrade one dependency within its declared range | `uv lock --upgrade-package PACKAGE` | `npm update PACKAGE` |
| Seven-day selection rule | `[tool.uv] exclude-newer = "7 days"` | `.npmrc`: `min-release-age=7` (in **days**) |

Commit both lockfiles with intentional dependency updates. `package-lock.json` is no longer ignored by Git. There are no production JavaScript dependencies: the npm project is for browser testing only.

**Cooldowns govern selection of new registry releases, not a fresh security review of every locked download.** In particular, `npm ci` installs the exact reviewed lockfile, including a version deliberately approved through an emergency exception. A lockfile's hashes protect against changed artifact contents, not malware already present in the approved artifact. Do not accept arbitrary lockfile changes merely because installation succeeds.

uv's cutoff uses each distribution file's upload time, not just the date the package version was announced. Some files for an otherwise old version may therefore be temporarily unavailable. A cutoff also cannot vouch for Git/path dependencies, OS packages, base images, or external downloads.

## Ordinary setup and tests

From the repository root:

```sh
make install       # uv sync --locked
make e2e-install   # npm ci, then install this Playwright release's browsers
make test
make e2e
```

To run a focused browser test:

```sh
make e2e TEST=host-flow
npm test -- my-games.spec.ts --project=chromium
```

The npm scripts enter `e2e/` so they load the existing Playwright configuration and its development-server command correctly. They use the locally installed CLI and do not offer to download an unreviewed test runner if dependencies are missing.

Browser tests create and modify application data. Use a local/test database and test accounts, not production credentials. The default server is `http://localhost:8000`. To use a separately managed test server, set both `CI=1` (disables Playwright's automatic server startup) and `BASE_URL=http://127.0.0.1:PORT`. `CI=1` also enables the configuration's CI retries and reporter; command-line flags can override these.

### Updating Playwright

```sh
npm update @playwright/test
./node_modules/.bin/playwright install chromium webkit
npm audit
npm test -- --list --project=chromium
make e2e
```

If intentionally raising the declared version floor, use `npm install --save-dev @playwright/test@VERSION` with a reviewed version that satisfies the cooldown. Review `package.json` and `package-lock.json` together.

The downloaded browser versions follow the Playwright package release. **npm's release-age setting does not independently age-check or scan Playwright's browser archives.** Refresh the browsers whenever Playwright is upgraded; they do not simply follow your everyday browser's automatic updates. Do not expose Playwright control/report servers publicly or reuse real account sessions in browser tests. Automating arbitrary untrusted websites would require a separate sandbox/isolation review.

### Dependency installation scripts

`.npmrc` sets `ignore-scripts=true`. Third-party npm lifecycle scripts do not run during installation. Explicit commands such as `npm test` and the Playwright browser-install command still work.

This project does not require npm dependency install scripts. If a future dependency needs one, investigate and review it rather than disabling this protection globally. Blocking install scripts does **not** make malicious code safe to import or execute later.

### Updating Python dependencies

```sh
uv lock --upgrade-package PACKAGE
uv sync --locked
make test
```

The global seven-day policy also covers transitive registry dependencies. Normal updates keep other locked versions where possible. Use `uv lock --upgrade` only when deliberately reviewing a broader dependency update.

## Dependabot and CI

`.github/dependabot.yml` checks npm and Python weekly, targeting `dev`, with a seven-day cooldown for routine version-update PRs. Python uses the native `uv` ecosystem so `uv.lock` is maintained alongside `pyproject.toml`. Playwright packages are grouped together.

Dependabot's cooldown does **not** delay security-update PRs. Security updates target the repository's default branch; the routine-update `target-branch: dev` setting does not move them to `dev`. If a security PR needs a release that the local cooldown blocks, use a narrow, reviewed exception as described below.

In GitHub repository settings, ensure **Dependabot alerts and Dependabot security updates** are enabled. These repository settings are separate from `dependabot.yml`; editing the file alone does not enable them.

The dependency-policy CI job checks the policy against synthetic local registries, tests the Docker context allowlist and Python audit entry point, validates the Python lockfile, installs the npm lockfile, runs `npm audit` and `make audit-python`, and checks browser-test discovery. It does not run the application browser suite. Deployment requires both that job and the existing Django tests to pass.

`npm audit` checks known advisories for npm dependencies. It is not a comprehensive vulnerability scan of downloaded browsers, Python dependencies, or the production image.

### Python vulnerability audits

```sh
make audit-python
```

This exports hashed requirements from `uv.lock` using `--locked --all-groups --no-emit-project`, then runs the reviewed `pip-audit==2.10.1` with `--require-hashes --disable-pip --strict`. The scanner queries PyPI's advisory API without resolving or installing the exported packages. The temporary requirements file is removed on success or failure. Known vulnerabilities, invalid requirements, and advisory-service errors fail the command and the existing CI deployment gate; no advisories are automatically ignored or fixed.

The scanner and its dependencies are locked in an optional `security` dependency group, not installed by ordinary `uv sync --locked` or the production image's `uv sync --frozen --no-dev`. Running the audit installs that group into the local environment. It includes production, development, and security-tool requirements, but evaluates environment markers for the Python/platform running the scan. CI scans Python 3.13 on Linux; it is not an exhaustive audit of every platform variant in the universal lockfile.

Audit after dependency updates and periodically even without lockfile changes: new advisories can affect previously reviewed releases. Passing tests or meeting the cooldown does not mean an audit is clean. See [the Python security verification](../python-security/verification.md) for the current remediation results and temporary exception.

## Emergency security-fix exceptions

Do not wait seven days if a reviewed security fix needs faster adoption. Verify the advisory and publisher's release information, choose the exact intended fixed version, inspect the resulting lockfile diff, and run tests. Document the reason and removal date in the PR.

Prefer a **package-specific exception** over disabling the policy for all dependencies. Dependencies of an exempt package remain subject to the normal rule unless independently exempted.

### npm

For a one-command exception (replace the illustrative package/version):

```sh
npm install --save-dev PACKAGE@FIXED_VERSION --min-release-age-exclude=PACKAGE
npm audit
npm test -- --list --project=chromium
```

For Playwright, its matching `playwright` and `playwright-core` packages may also need exceptions because all three are released together. Include only the packages necessary:

```sh
npm install --save-dev @playwright/test@FIXED_VERSION \
  --min-release-age-exclude=@playwright/test \
  --min-release-age-exclude=playwright \
  --min-release-age-exclude=playwright-core
./node_modules/.bin/playwright install chromium webkit
```

Review and include the changed lockfile. Subsequent `npm ci` installs reproduce that reviewed version; the default seven-day rule remains unchanged for future resolutions. Do not add a permanent wildcard exclusion or run `npm audit fix --force` blindly.

### Python / uv

Record a temporary, package-scoped exception in `[tool.uv]` so local resolution, CI's lockfile check, and collaborators all agree. For example, if `urllib3` needs an urgent fix:

```toml
[tool.uv]
required-version = ">=0.13.5"
exclude-newer = "7 days"
# Temporary: explain the advisory and removal date in the PR.
exclude-newer-package = { urllib3 = "0 days" }
```

Then update that package, confirm the intended fixed version was selected, and test:

```sh
uv lock --upgrade-package urllib3
uv sync --locked
make test
```

If necessary, adjust the declared minimum version to require the reviewed fix. Include both the exception and the updated lockfile in the PR. Once the selected release's needed artifacts are seven days old, remove the exception, run `uv lock` and `uv sync --locked`, and verify the fixed version remains selected. Do not leave open-ended exceptions behind.

## Production build boundary

`.dockerignore` is an allowlist: only the Python manifests, README, `manage.py`, application packages, templates, static sources, and Dockerfile enter the build. Seed data under `quiz/fixtures/` remains available. Nested secrets and generated caches are excluded too.

Developer virtual environments, `node_modules`, browser tests/reports, `.git`, local database dumps, `.env`, and Google Sheets credentials are not copied into the image. Docker Compose still supplies `.env` through the existing runtime `env_file` setting; excluding it from the build does not disable runtime configuration. The image installs only the Python production dependencies.

If new runtime files are introduced outside the allowed paths, deliberately update the allowlist and its test. Never copy secrets into an image as a workaround. Previously built images are not retroactively cleaned by this change: deploy a rebuilt image through the normal process. Whether old images need deletion or exposed credentials need rotation depends on where those images were stored and who could access them.

## Verifying the policy

The implementation's test results and remaining limitations are recorded in
[verification.md](verification.md).

```sh
uv run --locked python tools/test_dependency_policy.py
# Also exercise Docker's actual ignore rules, with Docker running:
VERIFY_DOCKER_CONTEXT=1 uv run --locked python tools/test_dependency_policy.py
uv lock --check
python tools/test_python_audit.py
make audit-python
npm ci
npm audit
uv run --locked black . --check
make test
```

The synthetic registries contain harmless mature and one-day-old parent/child packages. Tests verify seven-day filtering for direct and transitive dependencies, blocked npm install scripts, rejection of unsupported npm engines, reproducible locked installs, and narrow emergency exceptions. These tests do not download or execute packages from public registries.

## References

- [npm minimum release age](https://docs.npmjs.com/cli/v11/using-npm/config/#min-release-age)
- [npm installation scripts](https://docs.npmjs.com/cli/v11/using-npm/config/#ignore-scripts)
- [uv dependency cooldowns](https://docs.astral.sh/uv/concepts/resolution/#dependency-cooldowns)
- [Dependabot cooldowns](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference#cooldown)
- [Playwright browser updates](https://playwright.dev/docs/browsers)
- [Original Playwright assessment](../playwright-security-assessment.md) (historical findings before these changes)
