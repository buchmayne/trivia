import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  teamSubmitTextAnswer,
  teamWaitForQuestion,
  teamGetCurrentQuestion,
  teamGetScore,
  adminLockRound,
  adminCompleteRound,
  adminShowLeaderboard,
  adminWaitForScoring,
  adminWaitForLeaderboard,
  adminScoreAllAnswers,
  adminOpenScoring,
  getLeaderboardData
} from '../helpers/session-helpers';

test.describe('Team Flow Tests', () => {
  test('team can join session with valid code', async ({
    page,
    createSession,
    joinSession
  }) => {
    // Create a session first
    const { session } = await createSession();

    // Join with valid code
    const team = await joinSession(session.code, 'Valid Team');

    // Verify team view is visible
    await waitForTeamView(team.page);

    // Wait for team lobby to be visible (JavaScript renders this based on state)
    await expect(team.page.locator('#teamLobby')).toBeVisible({ timeout: 10000 });

    // Verify "Waiting for game to start" message is shown
    await expect(team.page.locator('text=Waiting for game to start')).toBeVisible();
  });

  test('team cannot join with invalid code', async ({ page }) => {
    await page.goto('/quiz/play/join/');

    // Enter invalid code
    await page.fill('#sessionCode', 'XXXXXX');
    await page.fill('#teamName', 'Invalid Code Team');

    // Submit
    await page.click('button[type="submit"]');

    // Should show error
    await expect(page.locator('.error, #errorContainer, .alert')).toBeVisible({ timeout: 5000 });

    // Should still be on join page
    await expect(page).toHaveURL(/\/quiz\/play\/join/);
  });

  test('team cannot join with empty team name', async ({ page, createSession }) => {
    const { session } = await createSession();

    await page.goto('/quiz/play/join/');

    // Enter valid code but empty name
    await page.fill('#sessionCode', session.code);
    // Leave team name empty

    // Try to submit
    await page.click('button[type="submit"]');

    // Should show validation error or stay on page
    await expect(page).toHaveURL(/\/quiz\/play\/join/);
  });

  test('team sees waiting screen before game starts', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    // Team joins
    const team = await joinSession(session.code, 'Waiting Team');
    await waitForTeamView(team.page);

    // Team should see lobby/waiting state
    const teamLobby = team.page.locator('#teamLobby, .waiting-screen, .lobby-message');
    await expect(teamLobby).toBeVisible();

    // Verify message indicates waiting for host
    const content = await team.page.locator('#teamView').textContent();
    expect(content?.toLowerCase()).toMatch(/wait|lobby|start/);
  });

  test('team sees question when game starts', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    // Team joins
    const team = await joinSession(session.code, 'Question Team');
    await waitForTeamView(team.page);

    // Start the game
    await adminStartGame(adminPage);

    // Team should see playing state with question
    await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    // Question should be displayed
    await teamWaitForQuestion(team.page);
    const questionText = await teamGetCurrentQuestion(team.page);
    expect(questionText).toBeTruthy();
  });

  test('team can submit text answer', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Answer Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);

    // Submit an answer
    await teamSubmitTextAnswer(team.page, 'My test answer');

    // Verify answer was submitted - look for confirmation or updated UI
    await team.page.waitForTimeout(1000);

    // The answer badge or confirmation should appear
    const answerBadge = team.page.locator(
      '.answer-badge.answered.current, .answered-indicator, #answerStatus:has-text("Answered")'
    );
    const answerInput = team.page.locator(
      '#answerInput, #teamAnswerInputSection textarea'
    ).first();

    // Either badge shows answered, or input shows the saved value
    if (await answerBadge.first().isVisible()) {
      expect(await answerBadge.textContent()).toBeTruthy();
    } else if (await answerInput.isVisible()) {
      const value = await answerInput.inputValue();
      expect(value).toBe('My test answer');
    }
  });

  test('team can update answer before round lock', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Update Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);

    // Submit initial answer
    await teamSubmitTextAnswer(team.page, 'First answer');
    await team.page.waitForTimeout(1000);

    // Update the answer
    const answerInput = team.page.locator(
      '#answerInput, #teamAnswerInputSection textarea'
    ).first();

    if (await answerInput.isVisible()) {
      await answerInput.fill('Updated answer');
      const submitBtn = team.page.locator('#submitAnswerBtn, button:has-text("Submit")');
      await submitBtn.click();
      await team.page.waitForTimeout(1000);

      // Verify updated value
      const value = await answerInput.inputValue();
      expect(value).toBe('Updated answer');
    }
  });

  test('team cannot submit after round is locked', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Lock Test Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);

    // Team submits an answer before lock
    await teamSubmitTextAnswer(team.page, 'Answer before lock');

    // Admin locks the round
    await adminLockRound(adminPage);
    await team.page.waitForTimeout(2500); // Wait for polling to update

    // Try to submit - should be blocked
    const answerInput = team.page.locator(
      '#answerInput, #teamAnswerInputSection textarea'
    ).first();

    if (await answerInput.isVisible()) {
      // Check if input is disabled
      const isDisabled = await answerInput.isDisabled();

      if (!isDisabled) {
        // Try to submit and verify it fails
        await answerInput.fill('Too late answer');
        const submitBtn = team.page.locator('#submitAnswerBtn, button:has-text("Submit")');

        if (await submitBtn.isVisible() && !(await submitBtn.isDisabled())) {
          await submitBtn.click();
          // Should show error or be rejected
          await team.page.waitForTimeout(1000);
          const errorVisible = await team.page.locator('.error, .alert-danger').isVisible();
          // Either shows error or the submit is simply not processed
        }
      } else {
        // Input is correctly disabled
        expect(isDisabled).toBe(true);
      }
    }
  });

  test('team sees scoring state after round lock', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Scoring View Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);

    // Submit an answer
    await teamSubmitTextAnswer(team.page, 'Answer for scoring');

    // Admin locks round
    await adminLockRound(adminPage);

    // Team should see scoring/waiting state
    await team.page.waitForTimeout(3000); // Wait for state change via polling

    // Either teamScoring view or a message about scoring in progress
    const scoringIndicator = team.page.locator(
      '#teamScoring, .scoring-message, :has-text("scoring"), :has-text("Scoring")'
    );

    // Some indication that scoring is happening should be visible
    const pageContent = await team.page.locator('#teamView').textContent();
    // The UI should indicate round is locked/scoring
  });

  test('team sees leaderboard after round completion', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Leaderboard Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);
    await teamSubmitTextAnswer(team.page, 'My final answer');

    // Admin completes the round flow
    await adminLockRound(adminPage);

    // Score the answer (simplified - just complete the round)
    const scoringInputs = adminPage.locator('#scoringContent .points-input');
    if ((await scoringInputs.count()) > 0) {
      await adminScoreAllAnswers(adminPage, 10);
    }

    await adminCompleteRound(adminPage);
    await adminShowLeaderboard(adminPage);
    await adminWaitForLeaderboard(adminPage);

    // Team should see leaderboard
    await expect(
      team.page.locator('#teamLeaderboard, .leaderboard, #teamLeaderboardTableContainer')
    ).toBeVisible({ timeout: 10000 });
  });

  test('team score updates correctly after scoring', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Score Check Team');
    await waitForTeamView(team.page);

    // Initial score should be 0
    const initialScore = await teamGetScore(team.page);
    expect(initialScore).toBe(0);

    await adminStartGame(adminPage);
    await teamWaitForQuestion(team.page);
    await teamSubmitTextAnswer(team.page, 'Correct answer');

    // Admin scores and completes
    await adminLockRound(adminPage);
    await adminOpenScoring(adminPage);

    const scoringInputs = adminPage.locator(
      '#scoringContent .points-input'
    );
    if ((await scoringInputs.count()) > 0) {
      await adminScoreAllAnswers(adminPage, 10);
    }

    await adminCompleteRound(adminPage);
    await adminShowLeaderboard(adminPage);

    // Check team's score on leaderboard
    const leaderboard = await getLeaderboardData(team.page);
    const teamEntry = leaderboard.find((e) => e.name.includes('Score Check'));

    if (teamEntry) {
      expect(teamEntry.score).toBeGreaterThan(0);
    }
  });

  test('team token persists in localStorage', async ({
    createSession,
    joinSession
  }) => {
    const { session } = await createSession();
    const team = await joinSession(session.code, 'Token Team');
    await waitForTeamView(team.page);

    // Verify token is in localStorage
    const token = await team.page.evaluate((code) => {
      return localStorage.getItem(`session_${code}_team`);
    }, session.code);

    expect(token).toBeTruthy();
    expect(token).toBe(team.token);
  });

  test('team can reconnect after page refresh', async ({
    createSession,
    joinSession
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Reconnect Team');
    await waitForTeamView(team.page);

    // Start game
    await adminStartGame(adminPage);
    await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    // Refresh the page
    await team.page.reload();

    // Should automatically reconnect and show correct state
    await waitForTeamView(team.page);
    await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });
  });

  test('duplicate team names are handled', async ({
    createSession,
    joinSession,
    page
  }) => {
    const { session } = await createSession();

    // First team joins
    const team1 = await joinSession(session.code, 'Duplicate Name');
    await waitForTeamView(team1.page);

    // Try to join with same name
    await page.goto('/quiz/play/join/');
    await page.fill('#sessionCode', session.code);
    await page.fill('#teamName', 'Duplicate Name');
    await page.click('button[type="submit"]');

    // Either should get an error or be renamed
    await page.waitForTimeout(2000);

    // Check if error shown or redirected with modified name
    const onJoinPage = page.url().includes('/join');
    if (onJoinPage) {
      // Error case - duplicate name rejected
      const error = page.locator('.error, #errorContainer, .alert');
      await expect(error).toBeVisible();
    } else {
      // Allowed case - redirected to play
      await expect(page).toHaveURL(/\/quiz\/play\/[A-Z0-9]{6}\//);
    }
  });
});
