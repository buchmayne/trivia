import { Page, expect } from '@playwright/test';

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
  await expect(completeBtn).toBeVisible();
  await completeBtn.click();

  // Wait for reviewing state
  await expect(page.locator('#reviewingState')).toBeVisible({ timeout: 10000 });
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
 * Admin: Score all answers for current question with full points.
 * Handles both simple questions (table rows) and multi-part questions (div-based layout).
 */
export async function adminScoreAllAnswers(page: Page, points: number): Promise<void> {
  await adminOpenScoring(page);
  const pointsInputs = await page.locator('#scoringContent .points-input').all();

  for (const pointsInput of pointsInputs) {
    if (!(await pointsInput.isVisible()) || await pointsInput.isDisabled()) {
      continue;
    }
    await pointsInput.fill(String(points));
    // Find score button in the closest container - either a <tr> or a <div class="part-row">
    const row = pointsInput.locator('xpath=ancestor::tr | ancestor::div[contains(@class, "part-row")]').first();
    const scoreBtn = row.locator('.score-btn');
    if (await scoreBtn.isVisible()) {
      await scoreBtn.click();
      await page.waitForTimeout(300);
    }
  }
}

/**
 * Team: Submit a text answer
 * Handles both single-input questions and multi-part questions
 */
export async function teamSubmitTextAnswer(page: Page, answerText: string): Promise<void> {
  await waitForTeamView(page);

  // Wait for either multi-part or single-input answer UI to appear
  const subAnswerInputs = page.locator('.sub-answer-input');
  const singleAnswerInput = page.locator('#answerInput');
  const matchingButtons = page.locator('.bank-option-btn');
  await Promise.race([
    subAnswerInputs.first().waitFor({ state: 'visible', timeout: 10000 }),
    singleAnswerInput.waitFor({ state: 'visible', timeout: 10000 }),
    matchingButtons.first().waitFor({ state: 'visible', timeout: 10000 })
  ]).catch(() => {});

  const subAnswerCount = await subAnswerInputs.count();
  const matchingButtonCount = await matchingButtons.count();

  if (matchingButtonCount > 0) {
    // Matching question - select the first option for each part
    const groups = page.locator('.answer-bank-buttons');
    const groupCount = await groups.count();
    for (let i = 0; i < groupCount; i++) {
      const group = groups.nth(i);
      const option = group.locator('.bank-option-btn').first();
      const selectedValue = (await option.getAttribute('data-option')) || '';

      let clicked = false;
      for (let attempt = 0; attempt < 3 && !clicked; attempt++) {
        try {
          await option.click();
          clicked = true;
        } catch {
          await page.waitForTimeout(300);
        }
      }

      const hiddenInput = page.locator(`.matching-answer-input[data-sub-index="${i}"]`);
      if (selectedValue) {
        await expect(hiddenInput).toHaveValue(selectedValue, { timeout: 5000 });
      } else {
        await expect(hiddenInput).not.toHaveValue('', { timeout: 5000 });
      }
    }
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
 * Team: Wait for question to be displayed
 */
export async function teamWaitForQuestion(page: Page): Promise<void> {
  await waitForTeamView(page);
  await expect(page.locator('#teamPlaying')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('#teamQuestionDisplay')).toBeVisible();
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
 * Count the number of teams in the lobby
 */
export async function getTeamCount(page: Page): Promise<number> {
  // Teams are displayed in #lobbyTeams as .team-card elements
  const teamCards = page.locator('#lobbyTeams .team-card');
  return await teamCards.count();
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
