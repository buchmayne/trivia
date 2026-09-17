import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  adminLockRound,
  adminScoreAllAnswers,
  adminCompleteRound,
  adminShowLeaderboard,
  adminStartNextRound,
} from '../helpers/session-helpers';

/**
 * When the host lets teams navigate questions on their own, the team page has
 * to keep following the session: it must leave the question behind when the
 * round is locked, and it must not carry a question choice into the next round.
 */

type Page = import('@playwright/test').Page;

async function teamView(page: Page) {
  return page.evaluate(() => {
    const vis = (id: string) => !document.getElementById(id)?.classList.contains('hidden');
    return {
      badge: document.getElementById('statusBadge')?.textContent,
      playing: vis('teamPlaying'),
      scoring: vis('teamScoring'),
      question: (document.getElementById('teamQuestionDisplay')?.innerText || '').slice(0, 40),
    };
  });
}

async function enableTeamNavigation(adminPage: Page, teamPage: Page) {
  await adminPage.locator('#toggleTeamNavBtn').click();
  await expect(teamPage.locator('#teamQuestionNav')).toBeVisible({ timeout: 10000 });
}

async function teamQuestionOptions(teamPage: Page): Promise<string[]> {
  return teamPage
    .locator('#teamQuestionSelector option')
    .evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value).filter(Boolean));
}

test.describe('Team question navigation stays in sync with the session', () => {
  test('team leaves its own question when the host locks the round', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(120000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Sync Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await enableTeamNavigation(adminPage, team.page);

    // Team moves to a question the host is not on.
    const options = await teamQuestionOptions(team.page);
    expect(options.length).toBeGreaterThan(1);
    await team.page.selectOption('#teamQuestionSelector', options[options.length - 1]);
    await team.page.waitForTimeout(1000);
    expect((await teamView(team.page)).playing).toBe(true);

    await adminLockRound(adminPage);

    await expect
      .poll(async () => (await teamView(team.page)).scoring, { timeout: 15000 })
      .toBe(true);
    expect((await teamView(team.page)).playing).toBe(false);
  });

  test('team follows the host into the next round instead of its old question', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(180000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Round Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await enableTeamNavigation(adminPage, team.page);

    // Team navigates away from the host's question in round 1.
    const options = await teamQuestionOptions(team.page);
    await team.page.selectOption('#teamQuestionSelector', options[options.length - 1]);
    await team.page.waitForTimeout(1000);
    const round1Question = (await teamView(team.page)).question;
    expect(round1Question.length).toBeGreaterThan(0);

    // Host takes the game into the next round.
    await adminLockRound(adminPage);
    await adminScoreAllAnswers(adminPage, 1);
    await adminCompleteRound(adminPage);
    await adminShowLeaderboard(adminPage);
    await adminStartNextRound(adminPage);

    await expect
      .poll(async () => (await teamView(team.page)).playing, { timeout: 15000 })
      .toBe(true);

    // The team must be on the new round's question, not the one it chose before.
    await expect
      .poll(async () => (await teamView(team.page)).question, { timeout: 15000 })
      .not.toBe(round1Question);

    const adminQuestion = (await adminPage.locator('#questionDisplay').innerText()).slice(0, 40);
    expect((await teamView(team.page)).question).toBe(adminQuestion);
  });

  test('a stalled team tab catches up as soon as it is looked at again', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(120000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Stalled Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await enableTeamNavigation(adminPage, team.page);
    await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    // Simulate a backgrounded tab whose timers the browser has throttled away.
    await team.page.evaluate(() => {
      for (let i = 1; i < 10000; i++) clearInterval(i);
    });

    await adminLockRound(adminPage);
    await team.page.waitForTimeout(5000);

    // With its poll dead, the tab is still showing the question.
    expect((await teamView(team.page)).playing).toBe(true);

    // Returning to the tab must bring it up to date without waiting for a tick.
    await team.page.evaluate(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await expect
      .poll(async () => (await teamView(team.page)).scoring, { timeout: 5000 })
      .toBe(true);
  });
});
