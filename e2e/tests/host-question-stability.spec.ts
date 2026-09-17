import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  adminNextQuestion,
  adminLockRound,
  adminScoreAllAnswers,
  adminCompleteRound,
} from '../helpers/session-helpers';

/**
 * The host page polls session state every 2s. Re-rendering the question
 * container on every poll replaces the <video> element, which makes media
 * questions flicker and resets playback mid-video. These tests mark the
 * rendered node and assert it survives several polls, while still being
 * replaced when the question actually changes.
 */

const POLL_INTERVAL_MS = 2000;

/** Stamp the currently rendered node so a re-render can be detected. */
async function markRenderedNode(page: import('@playwright/test').Page, containerId: string) {
  await page.evaluate((id) => {
    const node = document.querySelector(`#${id} .question-container`);
    if (!node) {
      throw new Error(`No question container rendered in #${id}`);
    }
    (node as HTMLElement).dataset.renderProbe = 'original';
  }, containerId);
}

/** True if the node marked by markRenderedNode is still in the DOM. */
async function markSurvived(page: import('@playwright/test').Page, containerId: string) {
  return page.evaluate((id) => {
    const node = document.querySelector(`#${id} .question-container`);
    return node instanceof HTMLElement && node.dataset.renderProbe === 'original';
  }, containerId);
}

test.describe('Host question rendering stability', () => {
  test('host question display survives repeated state polls', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Stability Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await expect(adminPage.locator('#questionDisplay .question-container')).toBeVisible({
      timeout: 10000,
    });

    await markRenderedNode(adminPage, 'questionDisplay');

    // Sit through several poll cycles with no state change.
    await adminPage.waitForTimeout(POLL_INTERVAL_MS * 3);

    expect(await markSurvived(adminPage, 'questionDisplay')).toBe(true);
  });

  test('host question display re-renders when the question changes', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Nav Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await expect(adminPage.locator('#questionDisplay .question-container')).toBeVisible({
      timeout: 10000,
    });

    const firstText = await adminPage.locator('#questionDisplay').innerText();
    await markRenderedNode(adminPage, 'questionDisplay');

    await adminNextQuestion(adminPage);
    await expect
      .poll(async () => adminPage.locator('#questionDisplay').innerText(), { timeout: 10000 })
      .not.toBe(firstText);

    expect(await markSurvived(adminPage, 'questionDisplay')).toBe(false);
  });

  test('host review display survives repeated state polls', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Review Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await adminLockRound(adminPage);
    await adminScoreAllAnswers(adminPage, 1);
    await adminCompleteRound(adminPage);

    await expect(adminPage.locator('#reviewQuestionDisplay .question-container')).toBeVisible({
      timeout: 15000,
    });

    await markRenderedNode(adminPage, 'reviewQuestionDisplay');
    await adminPage.waitForTimeout(POLL_INTERVAL_MS * 3);

    expect(await markSurvived(adminPage, 'reviewQuestionDisplay')).toBe(true);
  });
});
