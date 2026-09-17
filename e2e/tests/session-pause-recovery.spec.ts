import { test, expect } from '../fixtures/session';
import { execSync } from 'child_process';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  adminLockRound,
} from '../helpers/session-helpers';

/**
 * A session auto-pauses when the host has not been seen for ADMIN_TIMEOUT_SECONDS.
 * The host page heartbeats on every poll, so that only happens when the host is
 * genuinely gone - and when it does, both sides have to say so and be able to
 * come back. Before the heartbeat existed, a paused session showed the host a
 * blank page with no controls and could not be revived at all.
 */

type Page = import('@playwright/test').Page;

function runDjangoShell(code: string) {
  execSync(`uv run manage.py shell -c "${code.replace(/"/g, '\\"')}"`, {
    cwd: process.cwd() + '/..',
    stdio: 'pipe',
  });
}

/** Backdate the host's last-seen timestamp so the next state poll pauses. */
function backdateHostLastSeen(code: string) {
  runDjangoShell(`
from django.utils import timezone
from datetime import timedelta
from quiz.models import GameSession
from quiz.session_api import ADMIN_TIMEOUT_SECONDS
stale = timezone.now() - timedelta(seconds=ADMIN_TIMEOUT_SECONDS + 30)
GameSession.objects.filter(code='${code}').update(admin_last_seen=stale)
`);
}

function sessionStatus(code: string): string {
  const out = execSync(
    `uv run manage.py shell -c "
from quiz.models import GameSession
print('STATUS:' + GameSession.objects.get(code='${code}').status)
"`,
    { cwd: process.cwd() + '/..', encoding: 'utf-8' }
  );
  return out.match(/STATUS:(\w+)/)![1];
}

async function adminVisible(page: Page, id: string) {
  return page.evaluate((el) => !document.getElementById(el)?.classList.contains('hidden'), id);
}

test.describe('Session pause and recovery', () => {
  test('a host reading answers during scoring does not get paused out', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(120000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Scoring Team');
    await waitForTeamView(team.page);
    await adminStartGame(adminPage);
    await adminLockRound(adminPage);
    await expect(adminPage.locator('#scoringState')).toBeVisible({ timeout: 10000 });

    // Scoring is the state where the host reads for a while without clicking
    // anything. Pretend they have been at it since before the timeout.
    backdateHostLastSeen(session.code);
    await adminPage.waitForTimeout(6000);

    expect(sessionStatus(session.code)).not.toBe('paused');
    expect(await adminVisible(adminPage, 'scoringState')).toBe(true);
    await expect(team.page.locator('#teamScoring')).toBeVisible();
  });

  test('teams are told the game paused and keep their question', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(120000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Paused Team');
    await waitForTeamView(team.page);
    await adminStartGame(adminPage);
    await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    // The host tab goes to sleep: its timers stop, so it stops checking in.
    await adminPage.evaluate(() => {
      for (let i = 1; i < 10000; i++) clearInterval(i);
    });
    backdateHostLastSeen(session.code);

    // The team's own poll trips the timeout.
    await expect(team.page.locator('#teamPausedBanner')).toBeVisible({ timeout: 15000 });
    expect(sessionStatus(session.code)).toBe('paused');

    // The question and its inputs stay put - the server still accepts answers.
    await expect(team.page.locator('#teamPlaying')).toBeVisible();
    await expect(team.page.locator('#teamQuestionDisplay')).not.toBeEmpty();

    // The host tab wakes up: returning to it checks in and resumes the game.
    await adminPage.evaluate(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await expect
      .poll(() => sessionStatus(session.code), { timeout: 15000 })
      .toBe('playing');
    await expect(team.page.locator('#teamPausedBanner')).toBeHidden({ timeout: 15000 });
    await expect(team.page.locator('#teamPlaying')).toBeVisible();
  });

  test('host can resume a paused session when its heartbeat cannot get through', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(120000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Resume Team');
    await waitForTeamView(team.page);
    await adminStartGame(adminPage);

    // Host page is alive but its heartbeats are not reaching the server.
    await adminPage.route('**/admin/heartbeat/', (route) => route.abort());
    backdateHostLastSeen(session.code);

    // It pauses, and the host is offered a way back rather than a blank page.
    await expect(adminPage.locator('#pausedState')).toBeVisible({ timeout: 15000 });
    const resumeBtn = adminPage.locator('#resumeSessionBtn');
    await expect(resumeBtn).toBeVisible();

    // Connectivity returns; the host clicks Resume.
    await adminPage.unroute('**/admin/heartbeat/');
    await resumeBtn.click();

    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 15000 });
    await expect(adminPage.locator('#pausedState')).toBeHidden();
    expect(sessionStatus(session.code)).toBe('playing');
    await expect(team.page.locator('#teamPausedBanner')).toBeHidden({ timeout: 15000 });
  });
});
