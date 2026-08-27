import { Page, expect } from '@playwright/test';

/**
 * Log in as an existing (already-provisioned) Django user via the standard
 * email/password login form. Used for scenarios that require a session's
 * host_user to be set (e.g. My Games portal / host-recovery tests), since
 * the anonymous createSession fixture never sets host_user.
 */
export async function loginViaForm(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/accounts/login/');
  await page.fill('#id_login', email);
  await page.fill('#id_password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes('/accounts/login/'), { timeout: 10000 });
}

/**
 * Host a new session as the currently logged-in user on this page (so the
 * resulting GameSession.host_user is set). Mirrors the anonymous createSession
 * fixture's game-selection logic, but reuses the caller's already-authenticated
 * page/context instead of creating a new one.
 */
export async function hostSessionAsLoggedInUser(
  page: Page,
  adminName: string = 'Test Admin'
): Promise<{ code: string; adminToken: string }> {
  await page.goto('/quiz/play/host/');
  await page.fill('#adminName', adminName);

  const options = await page.locator('#gameSelect option').all();
  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value) {
      await page.selectOption('#gameSelect', value);
      break;
    }
  }

  const passwordGroup = page.locator('#passwordGroup');
  await page.waitForTimeout(100);
  if (await passwordGroup.isVisible()) {
    const password = await page.evaluate(() => {
      const select = document.getElementById('gameSelect') as HTMLSelectElement;
      const selectedOption = select.selectedOptions[0];
      return selectedOption?.dataset.password || '';
    });
    await page.fill('#gamePassword', password);
  }

  await page.click('button[type="submit"]');
  await page.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

  const url = page.url();
  const code = url.match(/\/quiz\/play\/([A-Z0-9]{6})\//)?.[1];
  if (!code) {
    throw new Error('Failed to extract session code from URL');
  }

  const adminToken = await page.evaluate((sessionCode) => {
    return localStorage.getItem(`session_${sessionCode}_admin`);
  }, code);
  if (!adminToken) {
    throw new Error('Failed to get admin token from localStorage');
  }

  return { code, adminToken };
}

/**
 * Wait for session state to reach a specific status
 */
export async function waitForSessionStatus(
  page: Page,
  expectedStatus: string,
  timeout: number = 10000
): Promise<void> {
  await expect(async () => {
    const statusBadge = page.locator('#statusBadge, .status-badge');
    const text = await statusBadge.textContent();
    expect(text?.toLowerCase()).toContain(expectedStatus.toLowerCase());
  }).toPass({ timeout });
}

/**
 * Wait for admin view to be visible
 */
export async function waitForAdminView(page: Page): Promise<void> {
  await expect(page.locator('#adminView')).toBeVisible({ timeout: 10000 });
}

/**
 * Wait for team view to be visible
 */
export async function waitForTeamView(page: Page): Promise<void> {
  await expect(page.locator('#teamView')).toBeVisible({ timeout: 10000 });
}

/**
 * Admin: Start the game from lobby
 */
export async function adminStartGame(page: Page): Promise<void> {
  await waitForAdminView(page);
  const startBtn = page.locator('#startGameBtn');
  await expect(startBtn).toBeVisible();
  await startBtn.click();

  // Wait for playing state
  await expect(page.locator('#playingState')).toBeVisible({ timeout: 10000 });
}

/**
 * Admin: Navigate to next question
 */
export async function adminNextQuestion(page: Page): Promise<void> {
  const nextBtn = page.locator('#nextQuestionBtn');
  if (await nextBtn.isEnabled()) {
    await nextBtn.click();
    // Wait for UI to update (polling interval is 2s)
    await page.waitForTimeout(500);
  }
}

/**
 * Admin: Navigate to previous question
 */
export async function adminPrevQuestion(page: Page): Promise<void> {
  const prevBtn = page.locator('#prevQuestionBtn');
  if (await prevBtn.isEnabled()) {
    await prevBtn.click();
    await page.waitForTimeout(500);
  }
}

/**
 * Admin: Set specific question by ID
 */
export async function adminSetQuestion(page: Page, questionId: number): Promise<void> {
  const selector = page.locator('#questionSelector');
  await selector.selectOption(String(questionId));
  await page.waitForTimeout(500);
}

/**
 * Admin: Lock the current round
 */
export async function adminLockRound(page: Page): Promise<void> {
  const lockBtn = page.locator('#lockRoundBtn');
  await expect(lockBtn).toBeVisible();

  // Accept the confirmation dialog triggered by the lock button
  page.once('dialog', dialog => dialog.accept());

  await lockBtn.click();

  // Wait for state change via polling
  await page.waitForTimeout(1000);
}

/**
 * Admin: Open scoring view if required and wait for scoring UI
 */
export async function adminOpenScoring(page: Page): Promise<void> {
  const scoringBtn = page.locator('button:has-text("Score Answers"), #goToScoringBtn');
  if (await scoringBtn.isVisible().catch(() => false)) {
    await scoringBtn.click();
  }

  await expect
    .poll(async () => isStateVisible(page, 'scoring'), { timeout: 20000 })
    .toBe(true);

  // Wait for scoring content to actually be rendered (loaded asynchronously)
  await expect(page.locator('#scoringContent .points-input').first()).toBeVisible({ timeout: 20000 });
}

/**
 * Admin: Complete scoring and move to review
 */
export async function adminCompleteRound(page: Page): Promise<void> {
  const completeBtn = page.locator('#completeRoundBtn');

  // Wait for button to be visible (may need to wait for scoring to complete)
  await expect(completeBtn).toBeVisible({ timeout: 15000 });
  await completeBtn.click();

  // Wait for reviewing state
  await expect(page.locator('#reviewingState')).toBeVisible({ timeout: 15000 });
}

/**
 * Admin: Show leaderboard
 */
export async function adminShowLeaderboard(page: Page): Promise<void> {
  const leaderboardBtn = page.locator('#showLeaderboardBtn, button:has-text("Show Leaderboard")');
  await expect(leaderboardBtn).toBeVisible();
  await leaderboardBtn.click();

  // Wait for leaderboard state
  await expect(page.locator('#leaderboardState')).toBeVisible({ timeout: 10000 });
}

/**
 * Admin: Start next round
 */
export async function adminStartNextRound(page: Page): Promise<void> {
  const nextRoundBtn = page.locator('#startNextRoundBtn');
  await expect(nextRoundBtn).toBeVisible();
  await nextRoundBtn.click();

  // Wait for playing state
  await expect(page.locator('#playingState')).toBeVisible({ timeout: 10000 });
}

/**
 * Admin: Score an answer with specific points
 */
export async function adminScoreAnswer(
  page: Page,
  teamName: string,
  points: number
): Promise<void> {
  // Find the scoring row for this team
  const row = page.locator(`#scoringContent tr:has-text("${teamName}")`).first();

  // Find the points input in this row
  const pointsInput = row.locator('.points-input');
  await pointsInput.fill(String(points));

  // Find and click the score button
  const scoreBtn = row.locator('.score-btn');
  await scoreBtn.click();

  // Wait for update
  await page.waitForTimeout(500);
}

/**
 * Admin: Score all answers for current round with specified points.
 * Uses robust scoring via page.evaluate to ensure all answers get scored.
 */
export async function adminScoreAllAnswers(page: Page, points: number): Promise<void> {
  await adminOpenScoring(page);

  // Wait for scoring content to load
  await page.waitForTimeout(500);

  // Fill all score inputs and click score buttons using page.evaluate for reliability
  await page.evaluate((pts) => {
    const inputs = document.querySelectorAll('#scoringContent .points-input') as NodeListOf<HTMLInputElement>;
    inputs.forEach((input) => {
      if (!input.disabled) {
        input.value = String(pts);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }, points);

  // Click all score buttons
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('#scoringContent .score-btn') as NodeListOf<HTMLButtonElement>;
    buttons.forEach((btn) => {
      if (!btn.disabled && btn.style.display !== 'none') {
        btn.click();
      }
    });
  });

  // Wait for scoring to complete (poll until no more unscored answers)
  const startTime = Date.now();
  const timeout = 30000;

  while (Date.now() - startTime < timeout) {
    // Check if all answers are scored via the API
    const allScored = await page.evaluate(async () => {
      try {
        const parts = window.location.pathname.split('/').filter(Boolean);
        const sessionsIndex = parts.indexOf('play');
        const code = sessionsIndex >= 0 ? parts[sessionsIndex + 1] : null;
        const token = code ? localStorage.getItem(`session_${code}_admin`) : null;

        if (!code || !token) return true; // Assume scored if can't check

        const response = await fetch(`/quiz/api/sessions/${code}/admin/scoring-data/`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) return true; // Assume scored if can't check

        const data = await response.json();
        const questions = Array.isArray(data?.questions) ? data.questions : [];

        for (const question of questions) {
          const teamAnswers = Array.isArray(question?.team_answers) ? question.team_answers : [];
          for (const teamAnswer of teamAnswers) {
            if (Array.isArray(teamAnswer?.parts)) {
              for (const part of teamAnswer.parts) {
                if (part?.points_awarded === null) return false;
              }
            } else if (teamAnswer?.points_awarded === null) {
              return false;
            }
          }
        }
        return true;
      } catch {
        return true; // Assume scored on error
      }
    });

    if (allScored) break;
    await page.waitForTimeout(500);
  }
}

/**
 * Team: Submit a text answer
 * Handles both single-input questions and multi-part questions
 */
export async function teamSubmitTextAnswer(page: Page, answerText: string): Promise<void> {
  await waitForTeamView(page);

  // Wait for playing state first
  await expect(page.locator('#teamPlaying')).toBeVisible({ timeout: 15000 });

  // Wait for category flash animation to complete (2.5s display + 0.3s fade)
  // and answer inputs to be rendered. Poll until at least one input type is available.
  const maxWaitTime = 15000;
  const pollInterval = 500;
  const startTime = Date.now();

  let subAnswerCount = 0;
  let matchingButtonCount = 0;
  let singleInputVisible = false;
  let rankingInputVisible = false;

  while (Date.now() - startTime < maxWaitTime) {
    const subAnswerInputs = page.locator('.sub-answer-input');
    const singleAnswerInput = page.locator('#answerInput');
    const matchingButtons = page.locator('.bank-option-btn');
    const rankingInput = page.locator('#rankingAnswerInput, .ranking-item');

    subAnswerCount = await subAnswerInputs.count().catch(() => 0);
    matchingButtonCount = await matchingButtons.count().catch(() => 0);
    singleInputVisible = await singleAnswerInput.isVisible().catch(() => false);
    rankingInputVisible = await rankingInput.first().isVisible().catch(() => false);

    // If any input type is available, we're ready
    if (subAnswerCount > 0 || matchingButtonCount > 0 || singleInputVisible || rankingInputVisible) {
      break;
    }

    await page.waitForTimeout(pollInterval);
  }

  // Reload locators after polling
  const subAnswerInputs = page.locator('.sub-answer-input');
  const singleAnswerInput = page.locator('#answerInput');
  const matchingButtons = page.locator('.bank-option-btn');

  // Update counts from fresh locators
  subAnswerCount = await subAnswerInputs.count().catch(() => 0);
  matchingButtonCount = await matchingButtons.count().catch(() => 0);
  const rankingInput = page.locator('#rankingAnswerInput, .ranking-item');
  const rankingCount = await rankingInput.count().catch(() => 0);

  // Check if we have ranking question
  if (rankingCount > 0) {
    // Ranking question - just submit the default order (acceptable for testing)
    // The submit button click is handled below
  } else if (matchingButtonCount > 0) {
    // Matching question - select an option for each part
    const hiddenInputs = page.locator('.matching-answer-input');
    const inputCount = await hiddenInputs.count();

    for (let i = 0; i < inputCount; i++) {
      // Find buttons for this specific sub-index
      const buttons = page.locator(`.bank-option-btn[data-sub-index="${i}"]`);
      const buttonCount = await buttons.count();

      if (buttonCount > 0) {
        // Click the first available button for this item
        let clicked = false;
        for (let j = 0; j < buttonCount && !clicked; j++) {
          const button = buttons.nth(j);
          const isVisible = await button.isVisible().catch(() => false);
          if (isVisible) {
            try {
              await button.click();
              clicked = true;
              await page.waitForTimeout(300); // Wait for UI update
            } catch {
              // Continue to next button
            }
          }
        }
      }
    }

    // Wait a moment for all values to be set
    await page.waitForTimeout(500);
  } else if (subAnswerCount > 0) {
    // Multi-part question - fill all sub-answer inputs
    for (let i = 0; i < subAnswerCount; i++) {
      const input = subAnswerInputs.nth(i);
      await input.fill(`${answerText} - part ${i + 1}`);
    }
  } else {
    // Single input question - use #answerInput
    await expect(singleAnswerInput).toBeVisible({ timeout: 10000 });
    await singleAnswerInput.fill(answerText);
  }

  // Click submit button
  const submitBtn = page.locator('#submitAnswerBtn');
  await expect(submitBtn).toBeVisible({ timeout: 5000 });
  await submitBtn.click();

  // Wait for submission confirmation
  await page.waitForTimeout(1000);
}

/**
 * Team: Submit a ranking answer by reordering items
 * @param order - Array of indices representing the desired order (0-based)
 */
export async function teamSubmitRankingAnswer(page: Page, order: number[]): Promise<void> {
  await waitForTeamView(page);

  // For ranking questions, we need to drag and drop items
  // This is complex with Sortable.js - for now just verify the ranking UI exists
  const rankingItems = page.locator('.ranking-item, .sortable-item');
  await expect(rankingItems.first()).toBeVisible();

  // Submit the current order
  const submitBtn = page.locator('#submitAnswerBtn, button:has-text("Submit")');
  await submitBtn.click();

  await page.waitForTimeout(1000);
}

/**
 * Team: Wait for question to be displayed and answer inputs to be ready
 */
export async function teamWaitForQuestion(page: Page): Promise<void> {
  await waitForTeamView(page);
  await expect(page.locator('#teamPlaying')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#teamQuestionDisplay')).toBeVisible({ timeout: 10000 });

  // Wait for answer inputs to be rendered (after category flash animation)
  const maxWaitTime = 10000;
  const pollInterval = 500;
  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitTime) {
    const singleInput = await page.locator('#answerInput').isVisible().catch(() => false);
    const multiInput = await page.locator('.sub-answer-input').count().catch(() => 0) > 0;
    const matchingInput = await page.locator('.bank-option-btn').count().catch(() => 0) > 0;
    const rankingInput = await page.locator('.ranking-item, #rankingAnswerInput').count().catch(() => 0) > 0;

    if (singleInput || multiInput || matchingInput || rankingInput) {
      return;
    }

    await page.waitForTimeout(pollInterval);
  }

  // If we get here, no inputs were found - throw an error for visibility
  throw new Error('Timed out waiting for answer inputs to be rendered');
}

/**
 * Team: Navigate to specific question (when team navigation is enabled)
 */
export async function teamNavigateToQuestion(page: Page, questionIndex: number): Promise<void> {
  const questionNav = page.locator('#teamQuestionNav, .team-question-nav');
  await expect(questionNav).toBeVisible();

  const navItems = await questionNav.locator('button, .nav-item').all();
  if (questionIndex < navItems.length) {
    await navItems[questionIndex].click();
    await page.waitForTimeout(500);
  }
}

/**
 * Get the current question text displayed to a team
 */
export async function teamGetCurrentQuestion(page: Page): Promise<string | null> {
  const questionDisplay = page.locator('#teamQuestionDisplay, .question-text');
  if (await questionDisplay.isVisible()) {
    return await questionDisplay.textContent();
  }
  return null;
}

/**
 * Get the team's current score from the UI
 */
export async function teamGetScore(page: Page): Promise<number> {
  const primaryScore = page.locator('#teamCurrentScore');
  if (await primaryScore.isVisible().catch(() => false)) {
    const text = await primaryScore.textContent();
    const match = text?.match(/\d+/);
    return match ? parseInt(match[0], 10) : 0;
  }

  const fallbackScore = page.locator('.team-score:has-text(/\\d+/)');
  if (await fallbackScore.first().isVisible().catch(() => false)) {
    const text = await fallbackScore.first().textContent();
    const match = text?.match(/\d+/);
    return match ? parseInt(match[0], 10) : 0;
  }

  return 0;
}

/**
 * Team: Wait for any answer input UI to be ready
 */
export async function teamWaitForAnswerInputs(page: Page): Promise<void> {
  await waitForTeamView(page);
  const subAnswerInputs = page.locator('.sub-answer-input');
  const singleAnswerInput = page.locator('#answerInput');

  await Promise.race([
    subAnswerInputs.first().waitFor({ state: 'visible', timeout: 10000 }),
    singleAnswerInput.waitFor({ state: 'visible', timeout: 10000 })
  ]).catch(() => {});
}

/**
 * Admin: Wait for scoring UI to be ready
 */
export async function adminWaitForScoring(page: Page): Promise<void> {
  const scoringContainer = page.locator('#scoringContent, #scoringState');
  await scoringContainer.first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});
}

/**
 * Admin: Wait for leaderboard UI to be ready
 */
export async function adminWaitForLeaderboard(page: Page): Promise<void> {
  const leaderboard = page.locator('#leaderboardState, #leaderboardTableContainer');
  await leaderboard.first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});
}

/**
 * Get leaderboard data from the page
 */
export async function getLeaderboardData(
  page: Page
): Promise<Array<{ name: string; score: number; rank: number }>> {
  const results: Array<{ name: string; score: number; rank: number }> = [];

  // Wait for leaderboard table to be visible
  const tableContainer = page.locator('#leaderboardTableContainer, #teamLeaderboardTableContainer');
  await tableContainer.first().waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});

  const rows = await page.locator(
    '#leaderboardTableContainer tbody tr, #teamLeaderboardTableContainer tbody tr'
  ).all();

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const cells = await row.locator('td').all();
    if (cells.length >= 2) {
      const name = await cells[0].textContent();
      const scoreText = await cells[1].textContent();
      const score = parseInt(scoreText?.replace(/\D/g, '') || '0', 10);
      results.push({
        name: name?.trim() || '',
        score,
        rank: i + 1
      });
    }
  }

  return results;
}

/**
 * Count the number of teams (works in both lobby and playing states)
 */
export async function getTeamCount(page: Page): Promise<number> {
  // Check which state is visible and count teams from the appropriate container
  const lobbyVisible = await page.locator('#lobbyState').isVisible().catch(() => false);
  const playingVisible = await page.locator('#playingState').isVisible().catch(() => false);

  if (lobbyVisible) {
    const lobbyCards = page.locator('#lobbyTeams .team-card');
    return await lobbyCards.count().catch(() => 0);
  }

  if (playingVisible) {
    const statusCards = page.locator('#teamStatus .team-card');
    return await statusCards.count().catch(() => 0);
  }

  // Fallback: check both containers
  const lobbyCards = page.locator('#lobbyTeams .team-card');
  const statusCards = page.locator('#teamStatus .team-card');
  const lobbyCount = await lobbyCards.count().catch(() => 0);
  const statusCount = await statusCards.count().catch(() => 0);
  return Math.max(lobbyCount, statusCount);
}

/**
 * Check if a specific state section is visible
 */
export async function isStateVisible(
  page: Page,
  state: 'lobby' | 'playing' | 'scoring' | 'reviewing' | 'leaderboard' | 'completed'
): Promise<boolean> {
  const stateIds: Record<string, string> = {
    lobby: '#lobbyState',
    playing: '#playingState',
    scoring: '#scoringState',
    reviewing: '#reviewingState',
    leaderboard: '#leaderboardState',
    completed: '#completedState'
  };

  const selector = stateIds[state];
  return await page.locator(selector).isVisible();
}
