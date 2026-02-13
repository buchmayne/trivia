/**
 * Robust Visual QA Test
 *
 * This test implements defensive testing patterns to reliably play through
 * an entire trivia game. It will either complete successfully or provide
 * detailed diagnostics about what failed and why.
 *
 * Key features:
 * - Waits for stable state before acting
 * - Retries failed operations
 * - Captures screenshots on failure
 * - Detects question type dynamically
 * - Handles all question types (single, multipart, matching, ranking)
 *
 * Run with: make e2e-robust
 */

import { test as base, expect, Page, BrowserContext } from '@playwright/test';
import {
  CONFIG,
  log,
  capturePageState,
  ensureDiagnosticsDir,
  detectQuestionState,
  waitForAdminState,
  answerCurrentQuestion,
  adminAdvanceQuestion,
  adminLockRound,
  adminScoreAllAnswers,
  adminCompleteRound,
  adminShowLeaderboard,
  adminStartNextRound,
  adminCompleteGame,
  playRound,
  getElementState,
  ActionResult,
  safeClick,
} from '../helpers/robust-helpers';

// ============================================================================
// Test Configuration
// ============================================================================

interface TeamData {
  name: string;
  page: Page;
  context: BrowserContext;
}

interface SessionData {
  code: string;
  adminToken: string;
}

// ============================================================================
// Test Setup Helpers
// ============================================================================

async function createSession(browser: any): Promise<{ adminPage: Page; adminContext: BrowserContext; session: SessionData }> {
  log('INFO', 'Creating game session...');

  const adminContext = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  const adminPage = await adminContext.newPage();

  await adminPage.goto('/quiz/play/host/');
  await adminPage.waitForLoadState('networkidle');

  // Fill admin name
  await adminPage.fill('#adminName', 'Robust Test Admin');

  // Select first available game
  const gameSelect = adminPage.locator('#gameSelect');
  const options = await gameSelect.locator('option').all();

  let selectedGame = '';
  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value) {
      selectedGame = await option.textContent() || value;
      await gameSelect.selectOption(value);
      break;
    }
  }
  log('INFO', `Selected game: ${selectedGame}`);

  // Handle password if required
  const passwordGroup = adminPage.locator('#passwordGroup');
  const passwordVisible = await passwordGroup.isVisible().catch(() => false);

  if (passwordVisible) {
    const password = await adminPage.evaluate(() => {
      const select = document.getElementById('gameSelect') as HTMLSelectElement;
      return select.selectedOptions[0]?.dataset.password || '';
    });
    await adminPage.fill('#gamePassword', password);
    log('INFO', 'Entered game password');
  }

  // Submit form
  await adminPage.click('button[type="submit"]');

  // Wait for redirect to session page
  await adminPage.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//, { timeout: 10000 });

  // Extract session code
  const url = adminPage.url();
  const codeMatch = url.match(/\/quiz\/play\/([A-Z0-9]{6})\//);
  if (!codeMatch) {
    throw new Error('Failed to extract session code from URL');
  }
  const code = codeMatch[1];

  // Get admin token
  const adminToken = await adminPage.evaluate((sessionCode) => {
    return localStorage.getItem(`session_${sessionCode}_admin`);
  }, code);

  if (!adminToken) {
    throw new Error('Failed to get admin token');
  }

  log('INFO', `Session created: ${code}`);

  return {
    adminPage,
    adminContext,
    session: { code, adminToken },
  };
}

async function joinTeam(
  browser: any,
  sessionCode: string,
  teamName: string
): Promise<TeamData> {
  log('INFO', `${teamName} joining session ${sessionCode}...`);

  const context = await browser.newContext({
    viewport: { width: 500, height: 800 },
  });
  const page = await context.newPage();

  await page.goto('/quiz/play/join/');
  await page.waitForLoadState('networkidle');

  await page.fill('#sessionCode', sessionCode);
  await page.fill('#teamName', teamName);
  await page.click('button[type="submit"]');

  await page.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//, { timeout: 10000 });

  log('INFO', `${teamName} joined successfully`);

  return { name: teamName, page, context };
}

// ============================================================================
// Main Test
// ============================================================================

const test = base.extend({});

test.describe('Robust QA - Full Game Playthrough', () => {
  test.describe.configure({ mode: 'serial' });

  test('complete trivia game with comprehensive error handling', async ({ browser }) => {
    // Long timeout for full game
    test.setTimeout(900000); // 15 minutes

    await ensureDiagnosticsDir();

    const teams: TeamData[] = [];
    let adminPage: Page;
    let adminContext: BrowserContext;
    let session: SessionData;

    // ========================================
    // PHASE 1: Setup
    // ========================================
    log('INFO', '========================================');
    log('INFO', 'PHASE 1: SETUP');
    log('INFO', '========================================');

    try {
      const setupResult = await createSession(browser);
      adminPage = setupResult.adminPage;
      adminContext = setupResult.adminContext;
      session = setupResult.session;
    } catch (e) {
      log('ERROR', `Session creation failed: ${e}`);
      throw e;
    }

    // Wait for lobby state
    const inLobby = await waitForAdminState(adminPage, 'lobby', 10000);
    if (!inLobby) {
      await capturePageState(adminPage, 'not-in-lobby', true);
      throw new Error('Admin not in lobby state after session creation');
    }

    await capturePageState(adminPage, 'lobby-ready');

    // Join teams
    const teamNames = ['Alpha Team', 'Beta Team', 'Gamma Team'];

    for (const teamName of teamNames) {
      try {
        const team = await joinTeam(browser, session.code, teamName);
        teams.push(team);

        // Wait for team to be in lobby/waiting state
        await team.page.waitForTimeout(1000);
        await capturePageState(team.page, `${teamName}-joined`);
      } catch (e) {
        log('ERROR', `${teamName} failed to join: ${e}`);
        // Continue with remaining teams
      }
    }

    if (teams.length === 0) {
      throw new Error('No teams were able to join');
    }

    log('INFO', `${teams.length} teams joined successfully`);

    // Verify admin sees teams
    await adminPage.waitForTimeout(2000); // Wait for poll
    await capturePageState(adminPage, 'teams-in-lobby');

    // ========================================
    // PHASE 2: Start Game
    // ========================================
    log('INFO', '========================================');
    log('INFO', 'PHASE 2: START GAME');
    log('INFO', '========================================');

    const startBtn = adminPage.locator('#startGameBtn');
    const startResult = await safeClick(adminPage, startBtn, 'start-game');

    if (!startResult.success) {
      await capturePageState(adminPage, 'start-game-failed', true);
      throw new Error(`Failed to start game: ${startResult.error}`);
    }

    // Wait for playing state
    const inPlaying = await waitForAdminState(adminPage, 'playing', 10000);
    if (!inPlaying) {
      await capturePageState(adminPage, 'not-in-playing', true);
      throw new Error('Admin not in playing state after starting game');
    }

    log('INFO', 'Game started successfully');
    await capturePageState(adminPage, 'game-started-admin');

    // Wait for teams to receive the update
    await adminPage.waitForTimeout(3000);

    // Verify teams are in playing state
    for (const team of teams) {
      const teamPlaying = await team.page.locator('#teamPlaying').isVisible({ timeout: 10000 }).catch(() => false);
      if (!teamPlaying) {
        log('WARN', `${team.name} may not be in playing state`);
        await capturePageState(team.page, `${team.name}-not-playing`);
      } else {
        log('INFO', `${team.name} is in playing state`);
      }
    }

    await capturePageState(teams[0].page, 'team-playing-view');

    // ========================================
    // PHASE 3: Play Through All Rounds
    // ========================================
    log('INFO', '========================================');
    log('INFO', 'PHASE 3: PLAY ROUNDS');
    log('INFO', '========================================');

    let roundNum = 1;
    let gameComplete = false;
    const allErrors: string[] = [];
    const allScreenshots: string[] = [];

    while (!gameComplete) {
      log('INFO', `\n>>> STARTING ROUND ${roundNum}`);

      // Play through all questions in this round
      const roundResult = await playRound(
        adminPage,
        teams.map(t => t.page),
        teams.map(t => t.name),
        roundNum
      );

      allErrors.push(...roundResult.errors);
      allScreenshots.push(...roundResult.screenshots);

      log('INFO', `Round ${roundNum}: ${roundResult.questionsAnswered} questions answered`);

      if (roundResult.errors.length > 0) {
        log('WARN', `Round ${roundNum} had ${roundResult.errors.length} errors`);
      }

      // ========================================
      // Lock Round
      // ========================================
      log('INFO', 'Locking round...');

      const lockResult = await adminLockRound(adminPage);
      if (!lockResult.success) {
        log('WARN', `Lock round failed: ${lockResult.error}`);
        // Try to continue anyway
      }

      // Wait for scoring state
      const inScoring = await waitForAdminState(adminPage, 'scoring', 15000);
      if (!inScoring) {
        log('WARN', 'Not in scoring state - checking current state');
        await capturePageState(adminPage, `round-${roundNum}-not-scoring`, true);
      }

      await capturePageState(adminPage, `round-${roundNum}-scoring`);

      // ========================================
      // Score Answers (with timeout protection)
      // ========================================
      log('INFO', 'Scoring answers...');

      // Wait for scoring UI to load
      await adminPage.waitForTimeout(2000);

      // Wrap scoring in a timeout to prevent hanging
      const scoringTimeout = 60000; // 60 seconds max for scoring
      const scorePromise = adminScoreAllAnswers(adminPage);
      const timeoutPromise = new Promise<ActionResult>((_, reject) =>
        setTimeout(() => reject(new Error('Scoring timed out after 60s')), scoringTimeout)
      );

      try {
        const scoreResult = await Promise.race([scorePromise, timeoutPromise]);
        if (!scoreResult.success) {
          log('WARN', `Scoring failed: ${scoreResult.error}`);
        }
      } catch (e) {
        log('ERROR', `Scoring error: ${e instanceof Error ? e.message : String(e)}`);
        await capturePageState(adminPage, `round-${roundNum}-scoring-timeout`, true);
      }

      await capturePageState(adminPage, `round-${roundNum}-scored`);

      // ========================================
      // Complete Round
      // ========================================
      log('INFO', 'Completing round...');

      const completeResult = await adminCompleteRound(adminPage);
      if (!completeResult.success) {
        log('WARN', `Complete round failed: ${completeResult.error}`);
      }

      // Wait for reviewing state
      const inReviewing = await waitForAdminState(adminPage, 'reviewing', 10000);
      if (!inReviewing) {
        log('WARN', 'Not in reviewing state');
        await capturePageState(adminPage, `round-${roundNum}-not-reviewing`);
      }

      // ========================================
      // Show Leaderboard
      // ========================================
      log('INFO', 'Showing leaderboard...');

      const leaderboardResult = await adminShowLeaderboard(adminPage);
      if (!leaderboardResult.success) {
        log('WARN', `Show leaderboard failed: ${leaderboardResult.error}`);
      }

      // Wait for leaderboard state
      const inLeaderboard = await waitForAdminState(adminPage, 'leaderboard', 10000);
      if (!inLeaderboard) {
        log('WARN', 'Not in leaderboard state');
        await capturePageState(adminPage, `round-${roundNum}-not-leaderboard`);
      }

      await capturePageState(adminPage, `round-${roundNum}-leaderboard`);

      // Check if teams can see leaderboard
      for (const team of teams) {
        const teamLeaderboard = team.page.locator('#teamLeaderboard, .leaderboard');
        const visible = await teamLeaderboard.isVisible({ timeout: 5000 }).catch(() => false);
        if (visible) {
          log('INFO', `${team.name} can see leaderboard`);
        }
      }

      // ========================================
      // Check for Next Round or Game Complete
      // ========================================
      const nextRoundBtn = adminPage.locator('#startNextRoundBtn');
      const completeGameBtn = adminPage.locator('#completeGameBtn, button:has-text("End Game"), button:has-text("Complete Game")');

      const hasNextRound = await getElementState(nextRoundBtn);
      const hasCompleteGame = await getElementState(completeGameBtn);

      log('INFO', `Next round button: visible=${hasNextRound.visible}, enabled=${hasNextRound.enabled}`);
      log('INFO', `Complete game button: visible=${hasCompleteGame.visible}, enabled=${hasCompleteGame.enabled}`);

      if (hasNextRound.visible && hasNextRound.enabled) {
        log('INFO', 'Starting next round...');
        const nextRoundResult = await adminStartNextRound(adminPage);

        if (nextRoundResult.success) {
          // Wait for playing state
          await waitForAdminState(adminPage, 'playing', 10000);
          roundNum++;

          // Wait for teams to receive update
          await adminPage.waitForTimeout(3000);
        } else {
          log('ERROR', `Failed to start next round: ${nextRoundResult.error}`);
          gameComplete = true;
        }
      } else if (hasCompleteGame.visible) {
        log('INFO', 'Completing game...');
        const completeGameResult = await adminCompleteGame(adminPage);

        if (!completeGameResult.success) {
          log('WARN', `Complete game failed: ${completeGameResult.error}`);
        }

        gameComplete = true;
      } else {
        log('INFO', 'No next round or complete button - game appears complete');
        gameComplete = true;
      }
    }

    // ========================================
    // PHASE 4: Final Summary
    // ========================================
    log('INFO', '========================================');
    log('INFO', 'PHASE 4: FINAL SUMMARY');
    log('INFO', '========================================');

    await capturePageState(adminPage, 'game-complete-admin');

    for (const team of teams) {
      await capturePageState(team.page, `game-complete-${team.name}`);
    }

    log('INFO', `Game completed: ${roundNum} round(s)`);
    log('INFO', `Total errors: ${allErrors.length}`);
    log('INFO', `Screenshots captured: ${allScreenshots.length}`);

    if (allErrors.length > 0) {
      log('WARN', 'Errors encountered during game:');
      allErrors.forEach((err, i) => log('WARN', `  ${i + 1}. ${err}`));
    }

    log('INFO', `\nDiagnostics saved to: ${CONFIG.SCREENSHOT_DIR}`);

    // Keep browsers open for inspection
    log('INFO', '\n========================================');
    log('INFO', 'TEST COMPLETE');
    log('INFO', 'Browsers will remain open for 2 minutes');
    log('INFO', 'Press Ctrl+C to exit early');
    log('INFO', '========================================\n');

    await adminPage.waitForTimeout(120000);
  });
});
