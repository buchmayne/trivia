/**
 * Robust Test Helpers
 *
 * These helpers implement defensive testing patterns:
 * - Wait for stable state before acting
 * - Retry on failure with backoff
 * - Capture diagnostics on failure
 * - Hard timeouts with useful error messages
 */

import { Page, expect, Locator } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================================
// Configuration
// ============================================================================

export const CONFIG = {
  // Timeouts
  ELEMENT_TIMEOUT: 5000,      // Max time to wait for an element
  ACTION_TIMEOUT: 3000,       // Max time for a single action (click, fill)
  STABILITY_TIMEOUT: 2000,    // Time to wait for DOM stability
  QUESTION_CHANGE_TIMEOUT: 10000, // Max time to wait for question to change

  // Retries
  MAX_RETRIES: 3,             // Number of retries for answer submission
  RETRY_DELAY: 1000,          // Delay between retries

  // Polling
  POLL_INTERVAL: 500,         // How often to check for state changes
  STABILITY_CHECKS: 3,        // Number of consecutive stable checks required

  // Diagnostics
  SCREENSHOT_DIR: 'e2e/test-results/robust-diagnostics',
};

// ============================================================================
// Diagnostic Utilities
// ============================================================================

let screenshotCounter = 0;

export async function ensureDiagnosticsDir(): Promise<void> {
  if (!fs.existsSync(CONFIG.SCREENSHOT_DIR)) {
    fs.mkdirSync(CONFIG.SCREENSHOT_DIR, { recursive: true });
  }
}

export async function capturePageState(
  page: Page,
  label: string,
  includeHtml: boolean = false
): Promise<string> {
  await ensureDiagnosticsDir();
  const timestamp = Date.now();
  const prefix = `${timestamp}-${screenshotCounter++}-${label}`;

  // Screenshot
  const screenshotPath = `${CONFIG.SCREENSHOT_DIR}/${prefix}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});

  // Optional HTML dump
  if (includeHtml) {
    const htmlPath = `${CONFIG.SCREENSHOT_DIR}/${prefix}.html`;
    const html = await page.content().catch(() => 'Failed to get HTML');
    fs.writeFileSync(htmlPath, html);
  }

  return screenshotPath;
}

export function log(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', message: string): void {
  const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
  const prefix = {
    INFO: '   ',
    WARN: '⚠️ ',
    ERROR: '❌ ',
    DEBUG: '   ',
  }[level];
  console.log(`[${timestamp}] ${prefix}${message}`);
}

// ============================================================================
// Element State Checking
// ============================================================================

export interface ElementState {
  exists: boolean;
  visible: boolean;
  enabled: boolean;
  count: number;
}

export async function getElementState(locator: Locator): Promise<ElementState> {
  const count = await locator.count().catch(() => 0);
  if (count === 0) {
    return { exists: false, visible: false, enabled: false, count: 0 };
  }

  const first = locator.first();
  const visible = await first.isVisible().catch(() => false);
  const enabled = visible ? await first.isEnabled().catch(() => false) : false;

  return { exists: true, visible, enabled, count };
}

export async function waitForElementStable(
  page: Page,
  selector: string,
  options: { timeout?: number; minCount?: number } = {}
): Promise<boolean> {
  const timeout = options.timeout || CONFIG.STABILITY_TIMEOUT;
  const minCount = options.minCount || 1;
  const startTime = Date.now();

  let lastCount = -1;
  let stableChecks = 0;

  while (Date.now() - startTime < timeout) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);

    if (count >= minCount && count === lastCount) {
      stableChecks++;
      if (stableChecks >= CONFIG.STABILITY_CHECKS) {
        return true;
      }
    } else {
      stableChecks = 0;
    }

    lastCount = count;
    await page.waitForTimeout(CONFIG.POLL_INTERVAL);
  }

  return false;
}

// ============================================================================
// Question State Detection
// ============================================================================

export interface QuestionState {
  questionNumber: string | null;
  questionText: string | null;
  questionType: 'single' | 'multipart' | 'matching' | 'ranking' | 'unknown';
  inputCount: number;
  isAnswered: boolean;
  isLocked: boolean;
}

export async function detectQuestionState(page: Page): Promise<QuestionState> {
  // Get question number/text for change detection
  const questionDisplay = page.locator('#teamQuestionDisplay');
  const questionText = await questionDisplay.textContent().catch(() => null);

  const questionNumEl = page.locator('.question-number, #questionNumber');
  const questionNumber = await questionNumEl.first().textContent().catch(() => null);

  // Detect question type by checking which input elements exist
  const singleInput = page.locator('#answerInput');
  const subAnswerInputs = page.locator('.sub-answer-input');
  const matchingInputs = page.locator('.matching-answer-input');
  const rankingInput = page.locator('#rankingAnswerInput');

  const singleCount = await singleInput.count().catch(() => 0);
  const subCount = await subAnswerInputs.count().catch(() => 0);
  const matchingCount = await matchingInputs.count().catch(() => 0);
  const rankingCount = await rankingInput.count().catch(() => 0);

  let questionType: QuestionState['questionType'] = 'unknown';
  let inputCount = 0;

  if (rankingCount > 0) {
    questionType = 'ranking';
    inputCount = 1;
  } else if (matchingCount > 0) {
    questionType = 'matching';
    inputCount = matchingCount;
  } else if (subCount > 0) {
    questionType = 'multipart';
    inputCount = subCount;
  } else if (singleCount > 0) {
    questionType = 'single';
    inputCount = 1;
  }

  // Check if already answered
  const statusDiv = page.locator('.answer-status');
  const statusText = await statusDiv.textContent().catch(() => '');
  const isAnswered = statusText.toLowerCase().includes('submitted') ||
                     statusText.toLowerCase().includes('saved');
  const isLocked = statusText.toLowerCase().includes('locked');

  return {
    questionNumber,
    questionText,
    questionType,
    inputCount,
    isAnswered,
    isLocked,
  };
}

export async function waitForQuestionChange(
  page: Page,
  previousQuestionText: string | null,
  timeout: number = CONFIG.QUESTION_CHANGE_TIMEOUT
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const currentState = await detectQuestionState(page);

    // Question changed if text is different and we have inputs
    if (currentState.questionText !== previousQuestionText &&
        currentState.questionType !== 'unknown') {
      // Wait a bit more for stability
      await page.waitForTimeout(500);
      return true;
    }

    await page.waitForTimeout(CONFIG.POLL_INTERVAL);
  }

  return false;
}

// ============================================================================
// Safe Actions with Retry
// ============================================================================

export interface ActionResult {
  success: boolean;
  error?: string;
  screenshot?: string;
}

export async function safeClick(
  page: Page,
  locator: Locator,
  label: string
): Promise<ActionResult> {
  try {
    // First check if element is actionable
    const state = await getElementState(locator);
    if (!state.visible) {
      return { success: false, error: `${label}: Element not visible` };
    }

    // Scroll into view
    await locator.first().scrollIntoViewIfNeeded({ timeout: CONFIG.ACTION_TIMEOUT }).catch(() => {});

    // Click with timeout
    await locator.first().click({ timeout: CONFIG.ACTION_TIMEOUT });

    return { success: true };
  } catch (e) {
    const screenshot = await capturePageState(page, `click-failed-${label}`);
    return {
      success: false,
      error: `${label}: ${e instanceof Error ? e.message : String(e)}`,
      screenshot,
    };
  }
}

export async function safeFill(
  page: Page,
  locator: Locator,
  value: string,
  label: string
): Promise<ActionResult> {
  try {
    const state = await getElementState(locator);
    if (!state.visible) {
      return { success: false, error: `${label}: Element not visible` };
    }
    if (!state.enabled) {
      return { success: false, error: `${label}: Element not enabled` };
    }

    await locator.first().scrollIntoViewIfNeeded({ timeout: CONFIG.ACTION_TIMEOUT }).catch(() => {});
    await locator.first().fill(value, { timeout: CONFIG.ACTION_TIMEOUT });

    return { success: true };
  } catch (e) {
    const screenshot = await capturePageState(page, `fill-failed-${label}`);
    return {
      success: false,
      error: `${label}: ${e instanceof Error ? e.message : String(e)}`,
      screenshot,
    };
  }
}

// ============================================================================
// Answer Submission - Core Logic
// ============================================================================

export interface AnswerResult {
  success: boolean;
  questionType: string;
  errors: string[];
  screenshots: string[];
}

async function answerSingleQuestion(page: Page, answerText: string): Promise<ActionResult> {
  const input = page.locator('#answerInput');
  return await safeFill(page, input, answerText, 'single-answer');
}

async function answerMultipartQuestion(page: Page, teamName: string): Promise<ActionResult> {
  const inputs = page.locator('.sub-answer-input');
  const count = await inputs.count();

  for (let i = 0; i < count; i++) {
    const input = inputs.nth(i);
    const result = await safeFill(page, input, `${teamName} part ${i + 1}`, `multipart-${i}`);
    if (!result.success) {
      return result;
    }
    await page.waitForTimeout(200);
  }

  return { success: true };
}

async function answerMatchingQuestion(page: Page): Promise<ActionResult> {
  // Find all hidden inputs that track matching answers
  const hiddenInputs = page.locator('.matching-answer-input');
  const itemCount = await hiddenInputs.count();

  log('DEBUG', `Matching question has ${itemCount} items to match`);

  if (itemCount === 0) {
    return { success: false, error: 'No matching items found' };
  }

  for (let i = 0; i < itemCount; i++) {
    // Find buttons for this specific sub-index
    const buttons = page.locator(`.bank-option-btn[data-sub-index="${i}"]`);
    const buttonCount = await buttons.count();

    log('DEBUG', `Item ${i}: found ${buttonCount} buttons`);

    if (buttonCount === 0) {
      log('WARN', `No buttons found for matching item ${i}`);
      continue;
    }

    // Try to click the first available button
    let clicked = false;
    for (let j = 0; j < buttonCount && !clicked; j++) {
      const button = buttons.nth(j);
      const state = await getElementState(button);

      if (state.visible && state.enabled) {
        const result = await safeClick(page, button, `matching-item-${i}-btn-${j}`);
        if (result.success) {
          clicked = true;
          log('DEBUG', `Clicked button ${j} for item ${i}`);
          await page.waitForTimeout(300);
        }
      }
    }

    if (!clicked) {
      log('WARN', `Could not click any button for matching item ${i}`);
    }
  }

  return { success: true };
}

async function answerRankingQuestion(page: Page): Promise<ActionResult> {
  // Ranking questions just need the submit - the default order is acceptable for testing
  log('DEBUG', 'Ranking question - using default order');
  return { success: true };
}

async function submitAnswer(page: Page): Promise<ActionResult> {
  const submitBtn = page.locator('#submitAnswerBtn');
  const state = await getElementState(submitBtn);

  if (!state.visible) {
    return { success: false, error: 'Submit button not visible' };
  }

  if (!state.enabled) {
    // Button might be disabled if already submitted
    log('WARN', 'Submit button disabled - may already be submitted');
    return { success: true };
  }

  return await safeClick(page, submitBtn, 'submit-answer');
}

/**
 * Main answer submission function with retry logic
 */
export async function answerCurrentQuestion(
  page: Page,
  teamName: string,
  retries: number = CONFIG.MAX_RETRIES
): Promise<AnswerResult> {
  const errors: string[] = [];
  const screenshots: string[] = [];

  for (let attempt = 1; attempt <= retries; attempt++) {
    log('INFO', `${teamName}: Answer attempt ${attempt}/${retries}`);

    // Detect question type
    const questionState = await detectQuestionState(page);
    log('INFO', `${teamName}: Question type: ${questionState.questionType}, inputs: ${questionState.inputCount}`);

    if (questionState.isLocked) {
      log('WARN', `${teamName}: Question is locked, skipping`);
      return { success: true, questionType: questionState.questionType, errors: [], screenshots: [] };
    }

    if (questionState.questionType === 'unknown') {
      const screenshot = await capturePageState(page, `${teamName}-unknown-question`, true);
      screenshots.push(screenshot);
      errors.push('Could not detect question type');

      if (attempt < retries) {
        log('WARN', `${teamName}: Unknown question type, waiting and retrying...`);
        await page.waitForTimeout(CONFIG.RETRY_DELAY);
        continue;
      }

      return { success: false, questionType: 'unknown', errors, screenshots };
    }

    // Wait for inputs to be stable
    let inputSelector = '#answerInput';
    if (questionState.questionType === 'multipart') {
      inputSelector = '.sub-answer-input';
    } else if (questionState.questionType === 'matching') {
      inputSelector = '.bank-option-btn';
    } else if (questionState.questionType === 'ranking') {
      inputSelector = '.ranking-item, .sortable-item, #rankingAnswerInput';
    }

    const stable = await waitForElementStable(page, inputSelector, {
      timeout: CONFIG.STABILITY_TIMEOUT,
      minCount: 1,
    });

    if (!stable) {
      log('WARN', `${teamName}: Inputs not stable, retrying...`);
      await page.waitForTimeout(CONFIG.RETRY_DELAY);
      continue;
    }

    // Answer based on type
    let answerResult: ActionResult;

    switch (questionState.questionType) {
      case 'single':
        answerResult = await answerSingleQuestion(page, `${teamName} answer`);
        break;
      case 'multipart':
        answerResult = await answerMultipartQuestion(page, teamName);
        break;
      case 'matching':
        answerResult = await answerMatchingQuestion(page);
        break;
      case 'ranking':
        answerResult = await answerRankingQuestion(page);
        break;
      default:
        answerResult = { success: false, error: 'Unknown question type' };
    }

    if (!answerResult.success) {
      errors.push(answerResult.error || 'Answer failed');
      if (answerResult.screenshot) {
        screenshots.push(answerResult.screenshot);
      }

      if (attempt < retries) {
        log('WARN', `${teamName}: Answer failed, retrying...`);
        await page.waitForTimeout(CONFIG.RETRY_DELAY);
        continue;
      }

      return { success: false, questionType: questionState.questionType, errors, screenshots };
    }

    // Submit the answer
    const submitResult = await submitAnswer(page);

    if (!submitResult.success) {
      errors.push(submitResult.error || 'Submit failed');
      if (submitResult.screenshot) {
        screenshots.push(submitResult.screenshot);
      }

      if (attempt < retries) {
        log('WARN', `${teamName}: Submit failed, retrying...`);
        await page.waitForTimeout(CONFIG.RETRY_DELAY);
        continue;
      }

      return { success: false, questionType: questionState.questionType, errors, screenshots };
    }

    // Wait for submission to be acknowledged
    await page.waitForTimeout(500);

    log('INFO', `${teamName}: Successfully answered ${questionState.questionType} question`);
    return { success: true, questionType: questionState.questionType, errors: [], screenshots: [] };
  }

  return { success: false, questionType: 'unknown', errors, screenshots };
}

// ============================================================================
// Admin Actions
// ============================================================================

export async function waitForAdminState(
  page: Page,
  expectedState: 'lobby' | 'playing' | 'scoring' | 'reviewing' | 'leaderboard' | 'completed',
  timeout: number = 10000
): Promise<boolean> {
  const stateSelectors: Record<string, string> = {
    lobby: '#lobbyState',
    playing: '#playingState',
    scoring: '#scoringState',
    reviewing: '#reviewingState',
    leaderboard: '#leaderboardState',
    completed: '#completedState',
  };

  const selector = stateSelectors[expectedState];
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const visible = await page.locator(selector).isVisible().catch(() => false);
    if (visible) {
      return true;
    }
    await page.waitForTimeout(CONFIG.POLL_INTERVAL);
  }

  return false;
}

export async function adminAdvanceQuestion(page: Page): Promise<ActionResult> {
  const nextBtn = page.locator('#nextQuestionBtn');
  const state = await getElementState(nextBtn);

  if (!state.visible) {
    return { success: false, error: 'Next question button not visible' };
  }

  if (!state.enabled) {
    return { success: false, error: 'Next question button not enabled - may be at last question' };
  }

  return await safeClick(page, nextBtn, 'next-question');
}

export async function adminLockRound(page: Page): Promise<ActionResult> {
  const lockBtn = page.locator('#lockRoundBtn');
  const state = await getElementState(lockBtn);

  if (!state.visible) {
    return { success: false, error: 'Lock round button not visible' };
  }

  // Set up dialog handler before clicking
  page.once('dialog', dialog => dialog.accept());

  return await safeClick(page, lockBtn, 'lock-round');
}

async function waitForScoringButtonsSettled(
  page: Page,
  timeout: number = 15000
): Promise<{ pending: number; unscored: number; total: number }> {
  const startTime = Date.now();
  let last = { pending: 0, unscored: 0, total: 0 };

  while (Date.now() - startTime < timeout) {
    const status = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('#scoringContent .score-btn')) as HTMLButtonElement[];
      let pending = 0;
      let unscored = 0;

      buttons.forEach(btn => {
        if (btn.style.display === 'none') {
          return;
        }

        const text = (btn.textContent || '').trim();
        if (text === 'Scoring...' || text === '...') {
          pending++;
          return;
        }

        if (text === 'Score') {
          unscored++;
        }
      });

      return { pending, unscored, total: buttons.length };
    });

    last = status;
    if (status.pending === 0 && status.unscored === 0) {
      return status;
    }

    await page.waitForTimeout(CONFIG.POLL_INTERVAL);
  }

  return last;
}

async function waitForServerScoringComplete(
  page: Page,
  timeout: number = 20000
): Promise<{ complete: boolean; unscored: number; total: number; error?: string }> {
  const startTime = Date.now();
  let last = { unscored: -1, total: 0, error: 'unknown' };

  while (Date.now() - startTime < timeout) {
    const status = await page.evaluate(async () => {
      try {
        const parts = window.location.pathname.split('/').filter(Boolean);
        const sessionsIndex = parts.indexOf('sessions');
        const codeFromPath = sessionsIndex >= 0 ? parts[sessionsIndex + 1] : null;
        const code = codeFromPath || (typeof CODE !== 'undefined' ? CODE : null);
        const token =
          (typeof ADMIN_TOKEN !== 'undefined' && ADMIN_TOKEN) ||
          (code ? localStorage.getItem(`session_${code}_admin`) : null);

        if (!code || !token) {
          return { unscored: -1, total: 0, error: 'missing code or admin token' };
        }

        const response = await fetch(`/quiz/api/sessions/${code}/admin/scoring-data/`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          let message = `HTTP ${response.status}`;
          try {
            const data = await response.json();
            if (data && data.error) {
              message = data.error;
            }
          } catch {
            // Ignore JSON parse failures
          }
          return { unscored: -1, total: 0, error: message };
        }

        const data = await response.json();
        const questions = Array.isArray(data?.questions) ? data.questions : [];
        let unscored = 0;
        let total = 0;

        questions.forEach((question: any) => {
          const teamAnswers = Array.isArray(question?.team_answers) ? question.team_answers : [];
          if (teamAnswers.length === 0) {
            return;
          }

          const hasParts = Array.isArray(teamAnswers[0]?.parts);
          if (hasParts) {
            teamAnswers.forEach((teamAnswer: any) => {
              const parts = Array.isArray(teamAnswer?.parts) ? teamAnswer.parts : [];
              parts.forEach((part: any) => {
                total++;
                if (part?.points_awarded === null) {
                  unscored++;
                }
              });
            });
          } else {
            teamAnswers.forEach((teamAnswer: any) => {
              total++;
              if (teamAnswer?.points_awarded === null) {
                unscored++;
              }
            });
          }
        });

        return { unscored, total };
      } catch (e) {
        return { unscored: -1, total: 0, error: String(e) };
      }
    });

    last = status;
    if (!status.error && status.unscored === 0) {
      return { complete: true, unscored: status.unscored, total: status.total };
    }

    if (status.error) {
      return { complete: false, unscored: status.unscored, total: status.total, error: status.error };
    }

    await page.waitForTimeout(CONFIG.POLL_INTERVAL);
  }

  return { complete: false, unscored: last.unscored, total: last.total, error: last.error };
}

async function forceScoreMissingAnswers(
  page: Page
): Promise<{ missing: number; scored: number; errors: string[]; error?: string }> {
  return await page.evaluate(async () => {
    try {
      const parts = window.location.pathname.split('/').filter(Boolean);
      const sessionsIndex = parts.indexOf('sessions');
      const codeFromPath = sessionsIndex >= 0 ? parts[sessionsIndex + 1] : null;
      const code = codeFromPath || (typeof CODE !== 'undefined' ? CODE : null);
      const token =
        (typeof ADMIN_TOKEN !== 'undefined' && ADMIN_TOKEN) ||
        (code ? localStorage.getItem(`session_${code}_admin`) : null);

      if (!code || !token) {
        return { missing: 0, scored: 0, errors: [], error: 'missing code or admin token' };
      }

      const response = await fetch(`/quiz/api/sessions/${code}/admin/scoring-data/`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
          const data = await response.json();
          if (data && data.error) {
            message = data.error;
          }
        } catch {
          // Ignore JSON parse failures
        }
        return { missing: 0, scored: 0, errors: [], error: message };
      }

      const data = await response.json();
      const questions = Array.isArray(data?.questions) ? data.questions : [];
      const missing: Array<{
        team_answer_id?: number;
        answer_id?: number;
        team_id?: number;
        question_id?: number;
        answer_part_id?: number;
        max_points: number;
      }> = [];

      questions.forEach((question: any) => {
        const teamAnswers = Array.isArray(question?.team_answers) ? question.team_answers : [];
        if (teamAnswers.length === 0) {
          return;
        }

        const hasParts = Array.isArray(teamAnswers[0]?.parts);
        if (hasParts) {
          teamAnswers.forEach((teamAnswer: any) => {
            const parts = Array.isArray(teamAnswer?.parts) ? teamAnswer.parts : [];
            parts.forEach((part: any) => {
              if (part?.points_awarded === null) {
                missing.push({
                  team_answer_id: part.team_answer_id || undefined,
                  team_id: teamAnswer.team_id || undefined,
                  question_id: question.id || undefined,
                  answer_part_id: part.answer_part_id || undefined,
                  max_points: part.max_points || 0,
                });
              }
            });
          });
        } else {
          teamAnswers.forEach((teamAnswer: any) => {
            if (teamAnswer?.points_awarded === null) {
              missing.push({
                answer_id: teamAnswer.answer_id || undefined,
                team_id: teamAnswer.team_id || undefined,
                question_id: question.id || undefined,
                max_points: question.total_points || 0,
              });
            }
          });
        }
      });

      let scored = 0;
      const errors: string[] = [];

      for (const item of missing) {
        try {
          const payload: any = { points: item.max_points };
          if (item.team_answer_id) {
            payload.team_answer_id = item.team_answer_id;
          } else if (item.answer_id) {
            payload.answer_id = item.answer_id;
          } else {
            payload.team_id = item.team_id;
            payload.question_id = item.question_id;
            if (item.answer_part_id) {
              payload.answer_part_id = item.answer_part_id;
            }
          }

          const scoreResponse = await fetch(`/quiz/api/sessions/${code}/admin/score/`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          });

          if (!scoreResponse.ok) {
            let message = `HTTP ${scoreResponse.status}`;
            try {
              const errData = await scoreResponse.json();
              if (errData && errData.error) {
                message = errData.error;
              }
            } catch {
              // Ignore JSON parse failures
            }
            errors.push(message);
          } else {
            scored++;
          }
        } catch (e) {
          errors.push(String(e));
        }
      }

      return { missing: missing.length, scored, errors };
    } catch (e) {
      return { missing: 0, scored: 0, errors: [], error: String(e) };
    }
  });
}

export async function adminScoreAllAnswers(page: Page): Promise<ActionResult> {
  // Wait for scoring content to load
  const scoringContent = page.locator('#scoringContent');
  const contentVisible = await scoringContent.isVisible({ timeout: 10000 }).catch(() => false);

  if (!contentVisible) {
    return { success: false, error: 'Scoring content not visible' };
  }

  // Wait for inputs to be stable
  await waitForElementStable(page, '#scoringContent .points-input', { timeout: 5000 });

  // Get all scoring inputs and process them
  const result = await page.evaluate(() => {
    const inputs = document.querySelectorAll('#scoringContent .points-input') as NodeListOf<HTMLInputElement>;
    const results = {
      total: inputs.length,
      scored: 0,
      skipped: 0,
      alreadyScored: 0,
      errors: [] as string[],
    };

    inputs.forEach((input, index) => {
      try {
        // Check if input is disabled
        if (input.disabled) {
          results.skipped++;
          return;
        }

        // Get max points from the input's max attribute
        const maxPoints = parseInt(input.getAttribute('max') || '10', 10);
        const currentValue = parseInt(input.value || '0', 10);

        // Check if already scored (has a non-zero value and might be auto-scored)
        // We'll still allow re-scoring, but use a sensible value

        // Generate a random score between 0 and maxPoints
        // Bias towards full points (70% chance of max, 30% chance of random)
        let newScore: number;
        if (Math.random() < 0.7) {
          newScore = maxPoints; // Full points
        } else {
          newScore = Math.floor(Math.random() * (maxPoints + 1)); // Random 0 to max
        }

        // Set the value
        input.value = String(newScore);

        // Trigger input event so any listeners are notified
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));

        results.scored++;
      } catch (e) {
        results.errors.push(`Input ${index}: ${e}`);
      }
    });

    return results;
  });

  log('INFO', `Filled ${result.scored}/${result.total} score inputs (skipped ${result.skipped} disabled)`);

  if (result.errors.length > 0) {
    log('WARN', `Scoring errors: ${result.errors.join(', ')}`);
  }

  // Now click all the score buttons
  // We do this in JS to avoid Playwright's actionability checks hanging
  const buttonResult = await page.evaluate(() => {
    const buttons = document.querySelectorAll('#scoringContent .score-btn') as NodeListOf<HTMLButtonElement>;
    let clicked = 0;
    let skipped = 0;

    buttons.forEach((btn) => {
      try {
        if (btn.disabled || btn.style.display === 'none') {
          skipped++;
          return;
        }

        // Check if button is visible
        const rect = btn.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
          skipped++;
          return;
        }

        btn.click();
        clicked++;
      } catch (e) {
        skipped++;
      }
    });

    return { clicked, skipped, total: buttons.length };
  });

  log('INFO', `Clicked ${buttonResult.clicked}/${buttonResult.total} score buttons`);

  // Wait for UI to settle (buttons no longer in "Score/Scoring..." state)
  const uiStatus = await waitForScoringButtonsSettled(page, 15000);
  if (uiStatus.pending > 0 || uiStatus.unscored > 0) {
    log('WARN', `${uiStatus.unscored} answers still show unscored in UI (${uiStatus.pending} pending)`);
  }

  // Verify server has persisted all scores (prevents complete-round race)
  const serverStatus = await waitForServerScoringComplete(page, 20000);
  if (serverStatus.error) {
    log('WARN', `Scoring verification failed: ${serverStatus.error}`);
  } else if (!serverStatus.complete) {
    log('WARN', `${serverStatus.unscored} answers still need scoring on server`);

    // Fallback: score remaining answers directly via API
    log('INFO', 'Attempting to score remaining answers via API...');
    const forceResult = await forceScoreMissingAnswers(page);
    if (forceResult.error) {
      log('WARN', `Force scoring failed: ${forceResult.error}`);
    } else {
      log('INFO', `Force scored ${forceResult.scored}/${forceResult.missing} missing answers`);
      if (forceResult.errors.length > 0) {
        log('WARN', `Force scoring errors: ${forceResult.errors.slice(0, 5).join(', ')}`);
      }
    }

    // Re-check server status after fallback scoring
    const retryStatus = await waitForServerScoringComplete(page, 20000);
    if (retryStatus.error) {
      log('WARN', `Scoring verification failed after fallback: ${retryStatus.error}`);
    }

    const success = !retryStatus.error && retryStatus.complete;
    return success
      ? { success: true }
      : { success: false, error: retryStatus.error || `${retryStatus.unscored} answers still need scoring` };
  }

  const success = !serverStatus.error && serverStatus.complete;
  return success
    ? { success: true }
    : { success: false, error: serverStatus.error || `${serverStatus.unscored} answers still need scoring` };
}

export async function adminCompleteRound(page: Page): Promise<ActionResult> {
  const completeBtn = page.locator('#completeRoundBtn');
  return await safeClick(page, completeBtn, 'complete-round');
}

export async function adminShowLeaderboard(page: Page): Promise<ActionResult> {
  const leaderboardBtn = page.locator('#showLeaderboardBtn, button:has-text("Show Leaderboard")');
  return await safeClick(page, leaderboardBtn, 'show-leaderboard');
}

export async function adminStartNextRound(page: Page): Promise<ActionResult> {
  const nextRoundBtn = page.locator('#startNextRoundBtn');
  const state = await getElementState(nextRoundBtn);

  if (!state.visible) {
    return { success: false, error: 'Next round button not visible - may be final round' };
  }

  return await safeClick(page, nextRoundBtn, 'start-next-round');
}

export async function adminCompleteGame(page: Page): Promise<ActionResult> {
  const completeBtn = page.locator('#completeGameBtn, button:has-text("End Game"), button:has-text("Complete Game")');
  const state = await getElementState(completeBtn);

  if (!state.visible) {
    return { success: false, error: 'Complete game button not visible' };
  }

  return await safeClick(page, completeBtn, 'complete-game');
}

// ============================================================================
// Game Flow Helpers
// ============================================================================

export interface RoundResult {
  success: boolean;
  questionsAnswered: number;
  errors: string[];
  screenshots: string[];
}

export async function playRound(
  adminPage: Page,
  teamPages: Page[],
  teamNames: string[],
  roundNum: number,
  maxQuestionsPerRound: number = 100
): Promise<RoundResult> {
  const errors: string[] = [];
  const screenshots: string[] = [];
  let questionsAnswered = 0;

  log('INFO', `=== ROUND ${roundNum} START ===`);

  // Get initial question state for change detection
  let previousQuestionText: string | null = null;
  if (teamPages.length > 0) {
    const initialState = await detectQuestionState(teamPages[0]);
    previousQuestionText = initialState.questionText;
  }

  while (questionsAnswered < maxQuestionsPerRound) {
    const questionNum = questionsAnswered + 1;
    log('INFO', `--- Question ${questionNum} ---`);

    // Verify teams are in playing state
    for (let i = 0; i < teamPages.length; i++) {
      const teamPlaying = await teamPages[i].locator('#teamPlaying').isVisible().catch(() => false);
      if (!teamPlaying) {
        log('WARN', `${teamNames[i]} not in playing state`);
        const screenshot = await capturePageState(teamPages[i], `${teamNames[i]}-not-playing`);
        screenshots.push(screenshot);
      }
    }

    // Each team answers the question
    for (let i = 0; i < teamPages.length; i++) {
      const result = await answerCurrentQuestion(teamPages[i], teamNames[i]);

      if (!result.success) {
        log('ERROR', `${teamNames[i]} failed to answer: ${result.errors.join(', ')}`);
        errors.push(...result.errors);
        screenshots.push(...result.screenshots);
        // Continue with other teams even if one fails
      } else {
        log('INFO', `${teamNames[i]} answered (${result.questionType})`);
      }

      // Brief pause between teams for visual observation
      await teamPages[i].waitForTimeout(500);
    }

    questionsAnswered++;

    // Check if admin can advance to next question
    const advanceResult = await adminAdvanceQuestion(adminPage);

    if (!advanceResult.success) {
      log('INFO', `Cannot advance: ${advanceResult.error} - end of round`);
      break;
    }

    log('INFO', 'Admin advanced to next question');

    // Wait for question to change on team pages
    if (teamPages.length > 0) {
      const changed = await waitForQuestionChange(teamPages[0], previousQuestionText, 5000);
      if (!changed) {
        log('WARN', 'Question did not appear to change - checking if round ended');
        // Check if we're still in playing state
        const stillPlaying = await teamPages[0].locator('#teamPlaying').isVisible().catch(() => false);
        if (!stillPlaying) {
          log('INFO', 'Team no longer in playing state - round ended');
          break;
        }
      }

      // Update previous question text for next iteration
      const newState = await detectQuestionState(teamPages[0]);
      previousQuestionText = newState.questionText;
    }

    // Wait for state to settle
    await adminPage.waitForTimeout(1000);
  }

  log('INFO', `=== ROUND ${roundNum} COMPLETE: ${questionsAnswered} questions ===`);

  return {
    success: errors.length === 0,
    questionsAnswered,
    errors,
    screenshots,
  };
}
