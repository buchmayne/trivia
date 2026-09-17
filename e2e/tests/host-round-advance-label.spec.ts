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
 * The leaderboard's advance button leads somewhere different on the last round:
 * to the final results rather than to another round. Its label has to say so,
 * and has to keep saying so through the 2s state poll.
 */

const POLL_INTERVAL_MS = 2000;
const MAX_ROUNDS = 6;

test.describe('Host round advance button label', () => {
  test('final round leaderboard offers game results, not another round', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(180000);

    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Label Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);

    const advanceBtn = adminPage.locator('#startNextRoundBtn');
    const labels: string[] = [];

    for (let round = 1; round <= MAX_ROUNDS; round++) {
      await adminLockRound(adminPage);
      await adminScoreAllAnswers(adminPage, 1);
      await adminCompleteRound(adminPage);
      await adminShowLeaderboard(adminPage);

      await expect(advanceBtn).toBeVisible({ timeout: 10000 });
      // The label is set when leaderboard data lands, one fetch after render.
      await expect
        .poll(async () => advanceBtn.textContent(), { timeout: 10000 })
        .not.toBe('');

      const label = (await advanceBtn.textContent())?.trim() ?? '';
      labels.push(label);
      console.log(`Round ${round} leaderboard button: "${label}"`);

      if (label === 'View Game Results') {
        break;
      }

      expect(label).toBe('Start Next Round');
      await adminStartNextRound(adminPage);
    }

    // The last round reached must be the one offering results.
    expect(labels[labels.length - 1]).toBe('View Game Results');
    expect(labels.length).toBeGreaterThan(1);

    // The state poll must not clobber the label back to "Start Next Round".
    await adminPage.waitForTimeout(POLL_INTERVAL_MS * 3);
    await expect(advanceBtn).toHaveText('View Game Results');

    // And the button does what it says.
    await advanceBtn.click();
    await expect(adminPage.locator('#completedState')).toBeVisible({ timeout: 15000 });
  });
});
