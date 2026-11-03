# Playwright security assessment

## Recommendation: keep Playwright, but update it and tighten its separation from production

Your concern is reasonable—Playwright launches real browsers, so vulnerabilities matter. But **I did not find evidence that your project needs to remove it for security reasons.** The better response here is maintenance and isolation, rather than losing your browser tests.

I checked the project’s actual installed dependencies, ran npm’s vulnerability audit, and looked up current GitHub security advisories and Playwright’s documentation. **No files or dependencies were changed during that assessment.** This Markdown file records the response; versions and audit findings below reflect that research, not a new check.

### What the research found

It helps to distinguish three things that can get grouped together under “Playwright vulnerabilities”:

| Component | What I found | Relevance to your project |
|---|---|---|
| **Playwright itself** | [CVE-2025-59288](https://github.com/advisories/GHSA-7mvr-c777-76hp): certain browser-installation scripts disabled HTTPS certificate verification, allowing an attacker intercepting the download to substitute malicious software. GitHub lists **1.55.1** as the first patched version. | Your installed and locked version is **1.58.1**, which is newer than the fix. |
| **Playwright MCP server**, used by AI tools | [CVE-2025-9611](https://github.com/advisories/GHSA-6fg3-hvw7-2fwq): an attacker could send unauthorized requests to a locally running MCP server. Fixed in **0.0.40**. | This is a separate package, `@playwright/mcp`. It is **not in this project’s dependency tree**. That does not assess any separately configured AI tools on your machine. |
| **The browsers Playwright downloads** | Chromium, Firefox, and WebKit have their own vulnerabilities and need updates. | Relevant: upgrading Playwright and installing its corresponding browsers keeps these test browsers current. |

**`npm audit` reported zero known vulnerabilities across your locked npm dependencies.** That is reassuring, but it is not a guarantee: it does not comprehensively scan the downloaded browser executables or detect unknown vulnerabilities.

The broad claim that Playwright is currently dangerous because it has “lots of CVEs” is **not supported by the package advisories I found for your setup**. Browser-engine CVEs and separate products such as Playwright MCP should not be treated as interchangeable with vulnerabilities in your test package.

### Your project’s actual exposure

Playwright is a **development-only dependency** used for browser tests. Your configuration defaults to testing your own app at `localhost:8000`; I found no configured remote browser-control server.

That is a substantially different risk from running a browser automation service against arbitrary websites supplied by strangers.

You also have **13 browser-test files**, covering host/team flows, navigation synchronization, session recovery, and answer persistence. Removing Playwright would remove that automated browser coverage unless it were replaced. Django tests alone cannot fully verify browser-side JavaScript behavior.

There is, however, a deployment issue worth addressing:

**Your `Dockerfile` copies the entire build directory, and there is no `.dockerignore`.** Consequently, local `node_modules`, test artifacts, or other unnecessary files can enter the production image if present on the build machine. Your deployment workflow also writes `.env` before building, so that file falls within the broad copy.

I have not inspected a deployed image, so this is a finding about the build configuration—not proof of what is currently deployed. It is worth fixing independently of Playwright.

### How I recommend moving forward

1. **Update Playwright and its browsers.**  
   You have **1.58.1** installed; npm reported **1.64.1** as latest at the time of the assessment. Upgrade on a branch, reinstall the Chromium/WebKit versions you use, and run the browser tests before accepting the update.

2. **Automate npm dependency updates.**  
   Your Dependabot configuration covers Python and GitHub Actions, but not npm. Add weekly npm updates so Playwright does not quietly fall behind. Its browser binaries are tied to its releases rather than simply following your everyday browser’s automatic updates.

3. **Keep test tooling and secrets out of production images.**  
   Add a carefully reviewed `.dockerignore` or narrow the Docker copy instructions. Exclude development dependencies, browser-test artifacts, `.git`, and secrets such as `.env`; supply production secrets at runtime instead.

4. **Use browser tests with limited privileges and test data.**  
   Keep them aimed at your own local/test environments, avoid production credentials, and do not expose browser-control or report servers publicly. If you later automate visits to untrusted websites, revisit sandboxing and isolation—the risk changes materially.

### Would removing it ever make sense?

Yes—if you no longer use the browser tests and do not intend to maintain them, removing Playwright would reduce unused software and maintenance. But switching to Selenium or another browser tool would **not eliminate browser vulnerabilities**; it would mostly replace one dependency and maintenance process with another.

**My recommendation is to retain the coverage, update Playwright, add npm update monitoring, and fix the Docker build boundary.** That is a more proportionate security improvement than removing it based on the advisories found here.

Sources: the two linked security advisories, [Playwright browser/update documentation](https://playwright.dev/docs/browsers), and [Playwright’s container isolation guidance](https://playwright.dev/docs/docker).

If you have the article or warning that prompted this, share it—I can check whether it describes a different issue that this assessment should account for.
