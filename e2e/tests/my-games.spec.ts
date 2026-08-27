import { execSync } from 'child_process';
import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  adminStartGame,
  adminLockRound,
  getTeamCount,
  teamSubmitTextAnswer,
  loginViaForm,
  hostSessionAsLoggedInUser,
} from '../helpers/session-helpers';

/**
 * E2E coverage for the "My Games" portal and host-recovery flow (host
 * reclaiming a session after losing their original browser tab/device), and
 * the stale-tab messaging that results from the token rotation.
 *
 * Requires a logged-in host (GameSession.host_user set), so this suite
 * provisions its own verified Django user directly via manage.py shell
 * rather than the anonymous createSession fixture used elsewhere.
 */

let hostEmail: string;
let hostUsername: string;
const hostPassword = 'E2eHostPass123!';

function runDjangoShell(code: string): void {
  execSync(`uv run python manage.py shell -c "${code.replace(/"/g, '\\"')}"`, {
    cwd: '..',
    stdio: 'pipe',
  });
}

test.beforeAll(() => {
  const suffix = Date.now();
  hostUsername = `e2e_host_${suffix}`;
  hostEmail = `e2e_host_${suffix}@example.com`;

  runDjangoShell(`
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
u = User.objects.create_user(username='${hostUsername}', email='${hostEmail}', password='${hostPassword}')
EmailAddress.objects.create(user=u, email='${hostEmail}', verified=True, primary=True)
`);
});

test.afterAll(() => {
  runDjangoShell(`
from django.contrib.auth.models import User
User.objects.filter(username='${hostUsername}').delete()
`);
});

test.describe('My Games portal & host recovery', () => {
  test('host can reclaim a dropped session and continue without losing team progress', async ({
    browser,
    joinSession,
  }) => {
    // --- Original host tab: log in and start a session ---
    const originalContext = await browser.newContext();
    const originalPage = await originalContext.newPage();
    await loginViaForm(originalPage, hostEmail, hostPassword);

    const { code } = await hostSessionAsLoggedInUser(originalPage, 'E2E Host');
    await waitForAdminView(originalPage);

    // A team joins and the game starts
    const team = await joinSession(code, 'Recovery Test Team');
    await adminStartGame(originalPage);

    // Team makes progress that must survive the recovery
    await teamSubmitTextAnswer(team.page, 'Answer before host dropped');

    await expect(async () => {
      expect(await getTeamCount(originalPage)).toBe(1);
    }).toPass({ timeout: 10000 });

    // --- Host "loses" their tab/device: log in from a brand new browser
    // context (no shared localStorage) and recover via My Games ---
    const recoveredContext = await browser.newContext();
    const recoveredPage = await recoveredContext.newPage();
    await loginViaForm(recoveredPage, hostEmail, hostPassword);

    await recoveredPage.goto('/quiz/play/mine/');
    const sessionRow = recoveredPage.locator('.session-row', { hasText: code });
    await expect(sessionRow).toBeVisible({ timeout: 10000 });

    const rejoinBtn = recoveredPage.locator(`.rejoin-btn[data-code="${code}"]`);
    await expect(rejoinBtn).toBeVisible();

    await rejoinBtn.click();
    await recoveredPage.waitForURL(new RegExp(`/quiz/play/${code}/`));
    await waitForAdminView(recoveredPage);

    // The recovered tab has full host control and sees the team's progress
    await expect(async () => {
      expect(await getTeamCount(recoveredPage)).toBe(1);
    }).toPass({ timeout: 10000 });

    // --- The original (now stale) tab loses admin control on its next
    // admin action, with a clear message rather than a silent/generic error ---
    const staleLockBtn = originalPage.locator('#lockRoundBtn');
    if (await staleLockBtn.isVisible().catch(() => false)) {
      // The click triggers a confirm() dialog first, then (once the 403 comes
      // back) an alert() with our specific message. Accept every dialog and
      // record what we saw.
      const dialogMessages: string[] = [];
      originalPage.on('dialog', (dialog) => {
        dialogMessages.push(dialog.message());
        dialog.accept();
      });

      await staleLockBtn.click();

      await expect(async () => {
        expect(dialogMessages.join(' | ')).toContain('another device');
      }).toPass({ timeout: 5000 });

      await expect(originalPage.locator('#errorContainer')).toContainText(
        'another device',
        { timeout: 5000 }
      );
    }

    // --- The recovered tab can actually continue running the game, and the
    // team's pre-recovery answer is still there ---
    await adminLockRound(recoveredPage);
    await expect(recoveredPage.locator('#scoringState')).toBeVisible({
      timeout: 15000,
    });
    await expect(recoveredPage.locator('#scoringContent')).toContainText(
      'Answer before host dropped'
    );

    await originalContext.close();
    await recoveredContext.close();
  });

  test('completed games appear in My Games history with a working results link', async ({
    browser,
  }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginViaForm(page, hostEmail, hostPassword);

    const { code } = await hostSessionAsLoggedInUser(page, 'E2E History Host');
    await waitForAdminView(page);

    // Mark this session completed directly (fastest reliable way to exercise
    // the history/results path without playing an entire game end-to-end).
    runDjangoShell(`
from django.utils import timezone
from quiz.models import GameSession
GameSession.objects.filter(code='${code}').update(status='completed', completed_at=timezone.now())
`);

    await page.goto('/quiz/play/mine/');
    const historyRow = page.locator('.session-row', { hasText: code });
    await expect(historyRow).toBeVisible({ timeout: 10000 });

    const resultsLink = historyRow.locator('a', { hasText: 'View Results' });
    await expect(resultsLink).toBeVisible();
    await resultsLink.click();

    await page.waitForURL(new RegExp(`/quiz/play/${code}/`));
    // Completed sessions render without admin/team credentials in localStorage
    // for this tab - the page should not crash, and should reflect completion.
    await expect(page.locator('#statusBadge')).toContainText(/completed/i, {
      timeout: 10000,
    });

    await context.close();
  });
});
