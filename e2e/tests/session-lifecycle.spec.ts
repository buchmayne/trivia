import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  adminNextQuestion,
  adminLockRound,
  adminCompleteRound,
  adminShowLeaderboard,
  adminStartNextRound,
  teamSubmitTextAnswer,
  teamWaitForQuestion,
  getTeamCount,
  getLeaderboardData,
  isStateVisible
} from '../helpers/session-helpers';
import { Page } from '@playwright/test';

test.describe('Session Lifecycle - Full Game Flow', () => {
  test.describe.configure({ mode: 'serial' });

  test('complete game session with 3 teams through all rounds', async ({
    browser,
    createSession,
    joinSession
  }) => {
    test.setTimeout(90000);
    // Step 1: Host creates a session
    console.log('Step 1: Creating session...');
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    // Verify we're in lobby state
    await expect(adminPage.locator('#lobbyState')).toBeVisible();
    console.log(`Session created with code: ${session.code}`);

    // Step 2: Three teams join the session
    console.log('Step 2: Teams joining session...');
    const team1 = await joinSession(session.code, 'Alpha Squad');
    const team2 = await joinSession(session.code, 'Beta Force');
    const team3 = await joinSession(session.code, 'Gamma Team');

    // Verify all teams are in lobby
    await waitForTeamView(team1.page);
    await waitForTeamView(team2.page);
    await waitForTeamView(team3.page);

    // Verify admin sees all 3 teams
    await expect(async () => {
      const count = await getTeamCount(adminPage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    console.log('All 3 teams joined successfully');

    // Step 3: Admin starts the game
    console.log('Step 3: Starting game...');
    await adminStartGame(adminPage);

    // Verify all teams see the playing state
    await expect(team1.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });
    await expect(team2.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });
    await expect(team3.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    console.log('Game started, all teams in playing state');

    // Step 4: Play through the round - teams submit answers
    console.log('Step 4: Teams submitting answers...');

    // Wait for question to be displayed
    await teamWaitForQuestion(team1.page);
    await teamWaitForQuestion(team2.page);
    await teamWaitForQuestion(team3.page);

    // Each team submits an answer for the current question
    await teamSubmitTextAnswer(team1.page, 'Alpha answer for Q1');
    await teamSubmitTextAnswer(team2.page, 'Beta answer for Q1');
    await teamSubmitTextAnswer(team3.page, 'Gamma answer for Q1');

    console.log('All teams submitted answers for question 1');

    // Navigate through remaining questions in the round
    // Check if there's a next question available
    const nextBtn = adminPage.locator('#nextQuestionBtn');
    let questionCount = 1;

    while (await nextBtn.isEnabled()) {
      await adminNextQuestion(adminPage);
      questionCount++;

      // Wait for teams to see the new question
      await teamWaitForQuestion(team1.page);
      await teamWaitForQuestion(team2.page);
      await teamWaitForQuestion(team3.page);

      // Teams submit answers for this question
      await teamSubmitTextAnswer(team1.page, `Alpha answer for Q${questionCount}`);
      await teamSubmitTextAnswer(team2.page, `Beta answer for Q${questionCount}`);
      await teamSubmitTextAnswer(team3.page, `Gamma answer for Q${questionCount}`);

      console.log(`All teams submitted answers for question ${questionCount}`);

      // Check if we've reached the last question
      if (!(await nextBtn.isEnabled())) {
        break;
      }
    }

    console.log(`Round completed with ${questionCount} questions`);

    // Step 5: Admin locks the round
    console.log('Step 5: Locking round...');
    await adminLockRound(adminPage);

    // Verify round is locked - scoring state should be available
    await expect(adminPage.locator('#scoringState, #lockRoundBtn:disabled')).toBeVisible({
      timeout: 5000
    });

    console.log('Round locked');

    // Step 6: Admin scores answers
    console.log('Step 6: Scoring answers...');

    // Navigate to scoring - click on scoring tab or wait for scoring data
    const scoringBtn = adminPage.locator('button:has-text("Score Answers"), #goToScoringBtn');
    if (await scoringBtn.isVisible()) {
      await scoringBtn.click();
    }

    // Wait for scoring interface
    await expect(adminPage.locator('#scoringState, #scoringContent')).toBeVisible({
      timeout: 10000
    });

    // Score answers - look for scoring inputs with class .points-input
    const scoringInputs = adminPage.locator('#scoringContent .points-input');
    const inputCount = await scoringInputs.count();

    if (inputCount > 0) {
      // Score each answer with full points (10)
      for (let i = 0; i < inputCount; i++) {
        const input = scoringInputs.nth(i);
        await input.fill('10');

        // Look for associated score button in the same row
        const row = input.locator('xpath=ancestor::tr');
        const scoreBtn = row.locator('.score-btn');
        if (await scoreBtn.isVisible()) {
          await scoreBtn.click();
          await adminPage.waitForTimeout(300);
        }
      }
    }

    console.log('Answers scored');

    // Step 7: Complete round and show review
    console.log('Step 7: Completing round...');
    await adminCompleteRound(adminPage);

    // Verify reviewing state
    await expect(adminPage.locator('#reviewingState')).toBeVisible({ timeout: 10000 });

    console.log('Round completed, in review state');

    // Step 8: Show leaderboard
    console.log('Step 8: Showing leaderboard...');
    await adminShowLeaderboard(adminPage);

    // Verify leaderboard is visible for admin
    await expect(adminPage.locator('#leaderboardState')).toBeVisible({ timeout: 10000 });

    // Verify teams can see leaderboard
    await expect(team1.page.locator('#teamLeaderboard, .leaderboard')).toBeVisible({
      timeout: 10000
    });

    // Get leaderboard data
    const leaderboard = await getLeaderboardData(adminPage);
    console.log('Leaderboard:', leaderboard);

    // Verify all 3 teams are on the leaderboard
    expect(leaderboard.length).toBeGreaterThanOrEqual(3);

    console.log('Leaderboard displayed successfully');

    // Step 9: Check if there are more rounds
    const nextRoundBtn = adminPage.locator('#startNextRoundBtn');

    if (await nextRoundBtn.isVisible()) {
      console.log('Step 9: Starting next round...');
      await adminStartNextRound(adminPage);

      // Verify playing state resumed
      await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

      // Quick pass through next round
      await teamWaitForQuestion(team1.page);
      await teamSubmitTextAnswer(team1.page, 'Alpha round 2 answer');
      await teamSubmitTextAnswer(team2.page, 'Beta round 2 answer');
      await teamSubmitTextAnswer(team3.page, 'Gamma round 2 answer');

      // Lock and complete
      await adminLockRound(adminPage);

      // Score
      const round2Inputs = adminPage.locator('#scoringContent .points-input');
      const round2Count = await round2Inputs.count();
      for (let i = 0; i < round2Count; i++) {
        const input = round2Inputs.nth(i);
        await input.fill('10');
        const row = input.locator('xpath=ancestor::tr');
        const scoreBtn = row.locator('.score-btn');
        if (await scoreBtn.isVisible()) {
          await scoreBtn.click();
          await adminPage.waitForTimeout(300);
        }
      }

      // Complete and show leaderboard
      await adminCompleteRound(adminPage);
      await adminShowLeaderboard(adminPage);

      console.log('Second round completed');
    }

    // Step 10: Complete the game (if there's a complete game button)
    const completeGameBtn = adminPage.locator(
      '#completeGameBtn, button:has-text("End Game"), button:has-text("Complete Game")'
    );

    if (await completeGameBtn.isVisible()) {
      console.log('Step 10: Completing game...');
      await completeGameBtn.click();

      // Verify completed state
      await expect(adminPage.locator('#completedState')).toBeVisible({ timeout: 10000 });
    }

    // Final verification - teams should see final results
    const teamFinalResults = team1.page.locator('#teamResults, .final-results, #teamLeaderboard');
    await expect(teamFinalResults).toBeVisible({ timeout: 10000 });

    console.log('Game completed successfully!');
  });

  test('session handles team late join during gameplay', async ({
    browser,
    createSession,
    joinSession
  }) => {
    // Create session with 2 teams
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    // Two teams join initially
    const team1 = await joinSession(session.code, 'Early Bird');
    const team2 = await joinSession(session.code, 'Second Place');

    await waitForTeamView(team1.page);
    await waitForTeamView(team2.page);

    // Start the game
    await adminStartGame(adminPage);

    // Verify game is playing
    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

    // Late team joins after game started
    const lateTeam = await joinSession(session.code, 'Late Arrival');

    // Verify late team can see the game
    await waitForTeamView(lateTeam.page);
    await expect(lateTeam.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    // Verify late team can submit answers
    await teamWaitForQuestion(lateTeam.page);
    await teamSubmitTextAnswer(lateTeam.page, 'Late team answer');

    // Verify admin sees 3 teams
    await expect(async () => {
      const count = await getTeamCount(adminPage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    console.log('Late join test passed');
  });

  test('session persists across page refresh', async ({
    browser,
    createSession,
    joinSession
  }) => {
    // Create session
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    // Team joins
    const team1 = await joinSession(session.code, 'Persistent Team');
    await waitForTeamView(team1.page);

    // Start game
    await adminStartGame(adminPage);
    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

    // Team submits an answer
    await teamWaitForQuestion(team1.page);
    await teamSubmitTextAnswer(team1.page, 'Answer before refresh');

    // Refresh admin page
    await adminPage.reload();

    // Verify admin is still authenticated and sees correct state
    await waitForAdminView(adminPage);
    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

    // Refresh team page
    await team1.page.reload();

    // Verify team is still authenticated and sees correct state
    await waitForTeamView(team1.page);
    await expect(team1.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });

    console.log('Page refresh persistence test passed');
  });
});
