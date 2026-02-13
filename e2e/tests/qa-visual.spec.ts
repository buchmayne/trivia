/**
 * Visual QA Test - Designed for Human Observation
 *
 * This test runs a complete game session at human-readable speed with:
 * - Sequential actions (no parallel execution)
 * - Long pauses between actions for observation
 * - Console logging of each step
 * - Video recording of the entire session
 *
 * Run with: make e2e-qa
 */

import { test as base, expect, Page, BrowserContext } from '@playwright/test';

// Configuration for visual QA
const STEP_DELAY = 2000; // 2 seconds between major actions
const SHORT_DELAY = 1000; // 1 second for minor transitions
const OBSERVE_DELAY = 3000; // 3 seconds for important states to observe

interface SessionData {
  code: string;
  adminToken: string;
}

interface TeamData {
  name: string;
  token: string;
  page: Page;
  context: BrowserContext;
}

// Custom test that doesn't auto-close browsers
const test = base.extend<{
  adminPage: Page;
  adminContext: BrowserContext;
}>({
  adminContext: async ({ browser }, use) => {
    const context = await browser.newContext({
      viewport: { width: 1200, height: 900 },
    });
    await use(context);
    // Don't close - let user inspect
  },
  adminPage: async ({ adminContext }, use) => {
    const page = await adminContext.newPage();
    await use(page);
  },
});

/**
 * Log a step with visual separator
 */
function logStep(step: string, detail?: string) {
  console.log('\n' + '='.repeat(60));
  console.log(`>>> ${step}`);
  if (detail) console.log(`    ${detail}`);
  console.log('='.repeat(60));
}

/**
 * Pause with countdown for observation
 */
async function observePause(page: Page, seconds: number, reason: string) {
  console.log(`\n    [Pausing ${seconds}s: ${reason}]`);
  await page.waitForTimeout(seconds * 1000);
}

test.describe('Visual QA - Full Game Playthrough', () => {
  // Disable parallel execution and increase timeout significantly
  test.describe.configure({ mode: 'serial' });

  test('complete trivia game - watch the full experience', async ({ browser }) => {
    // Very long timeout for manual observation
    test.setTimeout(600000); // 10 minutes

    const teams: TeamData[] = [];

    // ========================================
    // STEP 1: Admin creates a session
    // ========================================
    logStep('STEP 1: Admin creates a new game session');

    const adminContext = await browser.newContext({
      viewport: { width: 1400, height: 900 },
    });
    const adminPage = await adminContext.newPage();

    await adminPage.goto('/quiz/play/host/');
    await observePause(adminPage, 2, 'Viewing host page');

    // Fill admin name
    await adminPage.fill('#adminName', 'QA Test Admin');
    await adminPage.waitForTimeout(SHORT_DELAY);

    // Select first available game
    const options = await adminPage.locator('#gameSelect option').all();
    for (const option of options) {
      const value = await option.getAttribute('value');
      if (value) {
        await adminPage.selectOption('#gameSelect', value);
        break;
      }
    }
    await adminPage.waitForTimeout(SHORT_DELAY);

    // Handle password if required
    const passwordGroup = adminPage.locator('#passwordGroup');
    if (await passwordGroup.isVisible()) {
      const password = await adminPage.evaluate(() => {
        const select = document.getElementById('gameSelect') as HTMLSelectElement;
        return select.selectedOptions[0]?.dataset.password || '';
      });
      await adminPage.fill('#gamePassword', password);
    }

    await observePause(adminPage, 2, 'Form filled - about to submit');

    // Submit and create session
    await adminPage.click('button[type="submit"]');
    await adminPage.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

    // Extract session info
    const url = adminPage.url();
    const sessionCode = url.match(/\/quiz\/play\/([A-Z0-9]{6})\//)?.[1];
    if (!sessionCode) throw new Error('Failed to get session code');

    const adminToken = await adminPage.evaluate((code) => {
      return localStorage.getItem(`session_${code}_admin`);
    }, sessionCode);

    logStep('Session Created!', `Code: ${sessionCode}`);
    await observePause(adminPage, 3, 'Admin is now in the lobby - waiting for teams');

    // ========================================
    // STEP 2: Teams join one by one
    // ========================================
    const teamNames = ['The Brainiacs', 'Quiz Masters', 'Trivia Titans'];

    for (let i = 0; i < teamNames.length; i++) {
      const teamName = teamNames[i];
      logStep(`STEP 2.${i + 1}: Team "${teamName}" joins the game`);

      const teamContext = await browser.newContext({
        viewport: { width: 500, height: 800 },
      });
      const teamPage = await teamContext.newPage();

      // Navigate to join page
      await teamPage.goto('/quiz/play/join/');
      await teamPage.waitForTimeout(SHORT_DELAY);

      // Fill in details
      await teamPage.fill('#sessionCode', sessionCode);
      await teamPage.waitForTimeout(500);
      await teamPage.fill('#teamName', teamName);
      await teamPage.waitForTimeout(SHORT_DELAY);

      await observePause(teamPage, 2, `${teamName} about to join`);

      // Submit
      await teamPage.click('button[type="submit"]');
      await teamPage.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

      // Get team token
      const teamToken = await teamPage.evaluate((code) => {
        return localStorage.getItem(`session_${code}_team`);
      }, sessionCode);

      teams.push({
        name: teamName,
        token: teamToken || '',
        page: teamPage,
        context: teamContext,
      });

      console.log(`    ${teamName} has joined!`);
      await observePause(adminPage, 2, `Check admin view - ${teamName} should appear in lobby`);
    }

    logStep('All teams have joined!', `${teams.length} teams in lobby`);
    await observePause(adminPage, 3, 'Review the lobby state before starting');

    // ========================================
    // STEP 3: Admin starts the game
    // ========================================
    logStep('STEP 3: Admin starts the game');

    const startBtn = adminPage.locator('#startGameBtn');
    await expect(startBtn).toBeVisible();
    await observePause(adminPage, 2, 'About to click Start Game');

    await startBtn.click();
    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

    logStep('Game Started!', 'All teams should now see the first question');
    await observePause(adminPage, 3, 'Observe admin playing state');

    // Check each team sees the game
    for (const team of teams) {
      await expect(team.page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });
      console.log(`    ${team.name} is ready to play`);
    }

    await observePause(teams[0].page, 3, 'Observe team playing view');

    // ========================================
    // GAME LOOP: Play through ALL rounds
    // ========================================
    let roundNum = 1;
    let gameComplete = false;

    while (!gameComplete) {
      logStep(`ROUND ${roundNum}`, 'Starting round');

      // ========================================
      // Play through ALL questions in this round
      // ========================================
      let questionNum = 1;
      let moreQuestions = true;

      while (moreQuestions) {
        logStep(`ROUND ${roundNum} - Question ${questionNum}`, 'Teams submit answers');

        // Check if teams are still in playing state with a question displayed
        const teamPlaying = teams[0].page.locator('#teamPlaying');
        const questionDisplay = teams[0].page.locator('#teamQuestionDisplay');

        // Wait briefly for state to settle
        await teams[0].page.waitForTimeout(500);

        // Check if we're still in playing mode with questions
        const isPlaying = await teamPlaying.isVisible().catch(() => false);
        const hasQuestion = await questionDisplay.isVisible().catch(() => false);

        if (!isPlaying || !hasQuestion) {
          console.log(`    Round appears to have ended (playing: ${isPlaying}, question: ${hasQuestion})`);
          break;
        }

        await observePause(teams[0].page, 3, 'Teams are viewing the question');

        // Each team submits an answer (sequentially for observation)
        for (const team of teams) {
          console.log(`    ${team.name} is submitting their answer...`);

          // Handle different question types
          const subAnswerInputs = team.page.locator('.sub-answer-input');
          const singleAnswerInput = team.page.locator('#answerInput');
          const matchingButtons = team.page.locator('.bank-option-btn');

          await Promise.race([
            subAnswerInputs.first().waitFor({ state: 'visible', timeout: 5000 }),
            singleAnswerInput.waitFor({ state: 'visible', timeout: 5000 }),
            matchingButtons.first().waitFor({ state: 'visible', timeout: 5000 }),
          ]).catch(() => {});

          const matchingCount = await matchingButtons.count();
          const subCount = await subAnswerInputs.count();

          if (matchingCount > 0) {
            // Matching question - use hidden inputs to find how many items need matching
            const hiddenInputs = team.page.locator('.matching-answer-input');
            const itemCount = await hiddenInputs.count();
            console.log(`      Matching question with ${itemCount} items to match`);

            for (let j = 0; j < itemCount; j++) {
              // Find a button for this sub-index and click it
              const buttons = team.page.locator(`.bank-option-btn[data-sub-index="${j}"]`);
              const buttonCount = await buttons.count();
              console.log(`      Item ${j}: found ${buttonCount} option buttons`);

              if (buttonCount > 0) {
                try {
                  // Click the first available button for this item
                  await buttons.first().click({ timeout: 3000 });
                  await team.page.waitForTimeout(300);
                } catch (e) {
                  console.log(`      Failed to click button for item ${j}, skipping`);
                }
              }
            }
          } else if (subCount > 0) {
            // Multi-part question
            for (let j = 0; j < subCount; j++) {
              await subAnswerInputs.nth(j).fill(`${team.name} answer part ${j + 1}`);
              await team.page.waitForTimeout(200);
            }
          } else if (await singleAnswerInput.isVisible()) {
            // Single answer
            await singleAnswerInput.fill(`${team.name}'s answer to R${roundNum}Q${questionNum}`);
          }

          // Submit
          const submitBtn = team.page.locator('#submitAnswerBtn');
          if (await submitBtn.isVisible()) {
            await submitBtn.click();
            await team.page.waitForTimeout(SHORT_DELAY);
          }

          await observePause(team.page, 1, `${team.name} submitted`);
        }

        console.log(`    Question ${questionNum} complete - all teams answered`);
        await observePause(adminPage, 2, 'Check admin view - team submissions');

        // Check if there's a next question available
        const nextBtn = adminPage.locator('#nextQuestionBtn');
        const nextBtnVisible = await nextBtn.isVisible().catch(() => false);
        const nextBtnEnabled = nextBtnVisible && await nextBtn.isEnabled().catch(() => false);

        if (nextBtnEnabled) {
          console.log('    Admin advancing to next question...');
          await nextBtn.click();
          await adminPage.waitForTimeout(STEP_DELAY);
          questionNum++;
        } else {
          console.log('    No more questions in this round');
          moreQuestions = false;
        }
      }

      logStep(`ROUND ${roundNum} Complete`, `Finished ${questionNum} question(s)`);

      // ========================================
      // Lock the round
      // ========================================
      logStep(`ROUND ${roundNum} - Locking`, 'No more submissions allowed');

      await observePause(adminPage, 2, 'About to lock round');

      const lockBtn = adminPage.locator('#lockRoundBtn');
      if (await lockBtn.isVisible()) {
        adminPage.once('dialog', (dialog) => dialog.accept());
        await lockBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);
      }

      logStep('Round Locked!', 'Moving to scoring phase');
      await observePause(adminPage, 3, 'Observe the scoring interface');

      // ========================================
      // Score all answers
      // ========================================
      logStep(`ROUND ${roundNum} - Scoring`, 'Admin scores team answers');

      // Wait for scoring state
      await expect(adminPage.locator('#scoringState')).toBeVisible({ timeout: 10000 });

      // Wait for scoring content to load
      const scoringContent = adminPage.locator('#scoringContent');
      await expect(scoringContent).toBeVisible({ timeout: 10000 });

      await observePause(adminPage, 3, 'Review answers before scoring');

      // Score each answer
      const pointsInputs = await adminPage.locator('#scoringContent .points-input').all();
      console.log(`    Found ${pointsInputs.length} answers to score`);

      for (let i = 0; i < pointsInputs.length; i++) {
        const input = pointsInputs[i];
        if (await input.isVisible() && !(await input.isDisabled())) {
          const points = Math.floor(Math.random() * 10) + 1; // Random 1-10 points
          await input.fill(String(points));

          const row = input.locator('xpath=ancestor::tr | ancestor::div[contains(@class, "part-row")]').first();
          const scoreBtn = row.locator('.score-btn');
          if (await scoreBtn.isVisible()) {
            await scoreBtn.click();
            console.log(`    Scored answer ${i + 1}: ${points} points`);
            await adminPage.waitForTimeout(500);
          }
        }
      }

      logStep('Scoring Complete!');
      await observePause(adminPage, 3, 'Review scored answers');

      // ========================================
      // Complete round and show review
      // ========================================
      logStep(`ROUND ${roundNum} - Review`, 'Admin completes the round');

      const completeBtn = adminPage.locator('#completeRoundBtn');
      if (await completeBtn.isVisible()) {
        await completeBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);
      }

      await expect(adminPage.locator('#reviewingState')).toBeVisible({ timeout: 10000 });
      logStep('In Review State');
      await observePause(adminPage, 3, 'Teams can review their scores');

      // ========================================
      // Show leaderboard
      // ========================================
      logStep(`ROUND ${roundNum} - Leaderboard`, 'Showing standings');

      const leaderboardBtn = adminPage.locator('#showLeaderboardBtn, button:has-text("Show Leaderboard")');
      if (await leaderboardBtn.isVisible()) {
        await leaderboardBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);
      }

      await expect(adminPage.locator('#leaderboardState')).toBeVisible({ timeout: 10000 });

      logStep('LEADERBOARD', `Round ${roundNum} standings`);
      await observePause(adminPage, 5, 'Observe the leaderboard');

      // Check teams can see leaderboard
      for (const team of teams) {
        const teamLeaderboard = team.page.locator('#teamLeaderboard, .leaderboard');
        if (await teamLeaderboard.isVisible({ timeout: 5000 }).catch(() => false)) {
          console.log(`    ${team.name} can see the leaderboard`);
        }
      }

      // ========================================
      // Check for more rounds or game complete
      // ========================================
      const nextRoundBtn = adminPage.locator('#startNextRoundBtn');
      const completeGameBtn = adminPage.locator('#completeGameBtn, button:has-text("End Game"), button:has-text("Complete Game")');

      const hasNextRound = await nextRoundBtn.isVisible().catch(() => false);
      const canCompleteGame = await completeGameBtn.isVisible().catch(() => false);

      if (hasNextRound) {
        logStep('Next Round Available', 'Starting next round...');
        await observePause(adminPage, 3, 'About to start next round');
        await nextRoundBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);

        // Wait for playing state
        await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });
        roundNum++;
      } else if (canCompleteGame) {
        logStep('Final Round Complete', 'Ending the game');
        await completeGameBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);
        gameComplete = true;
      } else {
        // No next round button and no complete button - game is done
        logStep('Game Complete', 'No more rounds');
        gameComplete = true;
      }
    }

    logStep('GAME FINISHED', `Completed ${roundNum} round(s)`);

    // Verify final state for teams
    for (const team of teams) {
      const teamResults = team.page.locator('#teamResults, .final-results, #teamLeaderboard');
      if (await teamResults.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log(`    ${team.name} can see final results`);
      }
    }

    // ========================================
    // FINAL: Keep browsers open for inspection
    // ========================================
    logStep('TEST COMPLETE', 'Browsers will remain open for inspection');
    console.log('\n');
    console.log('='.repeat(60));
    console.log('  VISUAL QA SESSION COMPLETE');
    console.log('  ');
    console.log('  The browsers will remain open.');
    console.log('  Inspect the UI, check for bugs, review the experience.');
    console.log('  ');
    console.log('  Press Ctrl+C in the terminal to close when done.');
    console.log('='.repeat(60));
    console.log('\n');

    // Keep test alive for inspection (5 minutes)
    await adminPage.waitForTimeout(300000);
  });
});
