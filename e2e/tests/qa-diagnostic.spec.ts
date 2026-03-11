/**
 * Diagnostic QA Test - Identifies why the visual QA test hangs
 *
 * This test adds extensive logging and screenshots to diagnose
 * where and why the test hangs at Question 3.
 *
 * Run with: make e2e-diagnose
 */

import { test as base, expect, Page, BrowserContext } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const STEP_DELAY = 1500;
const SHORT_DELAY = 800;

interface TeamData {
  name: string;
  token: string;
  page: Page;
  context: BrowserContext;
}

const test = base.extend({});

// Create screenshots directory
const SCREENSHOT_DIR = 'e2e/test-results/diagnostics';

async function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
}

/**
 * Capture screenshot with descriptive name
 */
async function captureScreenshot(page: Page, name: string) {
  await ensureScreenshotDir();
  const filename = `${SCREENSHOT_DIR}/${Date.now()}-${name}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`    [SCREENSHOT] ${filename}`);
}

/**
 * Log detailed element state
 */
async function logElementState(page: Page, selector: string, name: string) {
  const element = page.locator(selector);
  const count = await element.count();
  const visible = count > 0 ? await element.first().isVisible().catch(() => false) : false;
  const enabled = count > 0 && visible ? await element.first().isEnabled().catch(() => false) : false;

  console.log(`    [ELEMENT] ${name} (${selector}): count=${count}, visible=${visible}, enabled=${enabled}`);
  return { count, visible, enabled };
}

/**
 * Log all relevant elements on admin page
 */
async function logAdminState(page: Page) {
  console.log('\n    --- ADMIN PAGE STATE ---');
  await logElementState(page, '#playingState', 'Playing State');
  await logElementState(page, '#scoringState', 'Scoring State');
  await logElementState(page, '#reviewingState', 'Reviewing State');
  await logElementState(page, '#leaderboardState', 'Leaderboard State');
  await logElementState(page, '#nextQuestionBtn', 'Next Question Button');
  await logElementState(page, '#prevQuestionBtn', 'Prev Question Button');
  await logElementState(page, '#lockRoundBtn', 'Lock Round Button');
  await logElementState(page, '#startNextRoundBtn', 'Start Next Round Button');

  // Get current question info if visible
  const questionInfo = page.locator('.question-info, #currentQuestionInfo, .question-number');
  if (await questionInfo.first().isVisible().catch(() => false)) {
    const text = await questionInfo.first().textContent();
    console.log(`    [INFO] Question info text: "${text}"`);
  }
  console.log('    --- END ADMIN STATE ---\n');
}

/**
 * Log all relevant elements on team page
 */
async function logTeamState(page: Page, teamName: string) {
  console.log(`\n    --- ${teamName} PAGE STATE ---`);
  await logElementState(page, '#teamPlaying', 'Team Playing');
  await logElementState(page, '#teamQuestionDisplay', 'Question Display');
  await logElementState(page, '#answerInput', 'Single Answer Input');
  await logElementState(page, '.sub-answer-input', 'Sub-Answer Inputs');
  await logElementState(page, '.bank-option-btn', 'Matching Buttons');
  await logElementState(page, '#submitAnswerBtn', 'Submit Button');
  await logElementState(page, '#teamLeaderboard', 'Team Leaderboard');

  // Check for any error messages
  const errorMsg = page.locator('.error, .error-message, [class*="error"]');
  if (await errorMsg.first().isVisible().catch(() => false)) {
    const text = await errorMsg.first().textContent();
    console.log(`    [ERROR] Error message visible: "${text}"`);
  }
  console.log(`    --- END ${teamName} STATE ---\n`);
}

function logStep(step: string, detail?: string) {
  console.log('\n' + '='.repeat(60));
  console.log(`>>> ${step}`);
  if (detail) console.log(`    ${detail}`);
  console.log('='.repeat(60));
}

test.describe('Diagnostic Test - Find the hang point', () => {
  test.describe.configure({ mode: 'serial' });

  test('diagnose question 3 hang', async ({ browser }) => {
    test.setTimeout(300000); // 5 minutes max

    const teams: TeamData[] = [];

    // ========================================
    // SETUP: Create session and join teams
    // ========================================
    logStep('SETUP: Creating session');

    const adminContext = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const adminPage = await adminContext.newPage();

    await adminPage.goto('/quiz/play/host/');
    await adminPage.fill('#adminName', 'Diagnostic Admin');

    // Select first game
    const options = await adminPage.locator('#gameSelect option').all();
    for (const option of options) {
      const value = await option.getAttribute('value');
      if (value) {
        const label = await option.textContent();
        console.log(`    Selected game: ${label} (id=${value})`);
        await adminPage.selectOption('#gameSelect', value);
        break;
      }
    }

    // Handle password
    const passwordGroup = adminPage.locator('#passwordGroup');
    if (await passwordGroup.isVisible()) {
      const password = await adminPage.evaluate(() => {
        const select = document.getElementById('gameSelect') as HTMLSelectElement;
        return select.selectedOptions[0]?.dataset.password || '';
      });
      await adminPage.fill('#gamePassword', password);
    }

    await adminPage.click('button[type="submit"]');
    await adminPage.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

    const url = adminPage.url();
    const sessionCode = url.match(/\/quiz\/play\/([A-Z0-9]{6})\//)?.[1]!;
    console.log(`    Session code: ${sessionCode}`);

    // Join 2 teams (fewer teams = faster diagnosis)
    const teamNames = ['Team Alpha', 'Team Beta'];
    for (const teamName of teamNames) {
      const teamContext = await browser.newContext({ viewport: { width: 500, height: 800 } });
      const teamPage = await teamContext.newPage();
      await teamPage.goto('/quiz/play/join/');
      await teamPage.fill('#sessionCode', sessionCode);
      await teamPage.fill('#teamName', teamName);
      await teamPage.click('button[type="submit"]');
      await teamPage.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

      const teamToken = await teamPage.evaluate((code) => {
        return localStorage.getItem(`session_${code}_team`);
      }, sessionCode);

      teams.push({ name: teamName, token: teamToken || '', page: teamPage, context: teamContext });
      console.log(`    ${teamName} joined`);
    }

    // Start game
    logStep('SETUP: Starting game');
    await adminPage.locator('#startGameBtn').click();
    await expect(adminPage.locator('#playingState')).toBeVisible({ timeout: 10000 });

    await captureScreenshot(adminPage, 'game-started-admin');
    await captureScreenshot(teams[0].page, 'game-started-team');

    // ========================================
    // DIAGNOSTIC: Play through questions with detailed logging
    // ========================================
    let questionNum = 1;
    const MAX_DIAGNOSTIC_QUESTIONS = 5;

    while (questionNum <= MAX_DIAGNOSTIC_QUESTIONS) {
      logStep(`QUESTION ${questionNum}`, 'Diagnosing...');

      // Capture state BEFORE doing anything
      console.log('\n>>> BEFORE attempting question:');
      await logAdminState(adminPage);
      await logTeamState(teams[0].page, teams[0].name);
      await captureScreenshot(adminPage, `q${questionNum}-before-admin`);
      await captureScreenshot(teams[0].page, `q${questionNum}-before-team`);

      // Check if we should continue
      const teamPlaying = teams[0].page.locator('#teamPlaying');
      const questionDisplay = teams[0].page.locator('#teamQuestionDisplay');

      const isPlaying = await teamPlaying.isVisible().catch(() => false);
      const hasQuestion = await questionDisplay.isVisible().catch(() => false);

      console.log(`\n>>> State check: isPlaying=${isPlaying}, hasQuestion=${hasQuestion}`);

      if (!isPlaying) {
        console.log('>>> DIAGNOSIS: Team is not in playing state - checking what state they are in');
        await logTeamState(teams[0].page, teams[0].name);
        await captureScreenshot(teams[0].page, `q${questionNum}-not-playing`);
        break;
      }

      if (!hasQuestion) {
        console.log('>>> DIAGNOSIS: No question displayed - round may have ended');
        await captureScreenshot(teams[0].page, `q${questionNum}-no-question`);
        break;
      }

      // Try to submit answers
      for (const team of teams) {
        console.log(`\n>>> ${team.name} attempting to submit...`);

        const subAnswerInputs = team.page.locator('.sub-answer-input');
        const singleAnswerInput = team.page.locator('#answerInput');
        const matchingButtons = team.page.locator('.bank-option-btn');

        const subCount = await subAnswerInputs.count();
        const singleVisible = await singleAnswerInput.isVisible().catch(() => false);
        const matchingCount = await matchingButtons.count();

        console.log(`    Input types found: sub=${subCount}, single=${singleVisible}, matching=${matchingCount}`);

        if (matchingCount > 0) {
          console.log('    Using matching question handler...');
          const groups = team.page.locator('.answer-bank-buttons');
          const groupCount = await groups.count();
          console.log(`    Found ${groupCount} answer groups`);

          for (let j = 0; j < groupCount; j++) {
            const option = groups.nth(j).locator('.bank-option-btn').first();
            const optionVisible = await option.isVisible().catch(() => false);
            console.log(`    Group ${j}: option visible=${optionVisible}`);
            if (optionVisible) {
              await option.click();
              await team.page.waitForTimeout(300);
            }
          }
        } else if (subCount > 0) {
          console.log('    Using multi-part question handler...');
          for (let j = 0; j < subCount; j++) {
            const input = subAnswerInputs.nth(j);
            const inputVisible = await input.isVisible().catch(() => false);
            console.log(`    Part ${j}: visible=${inputVisible}`);
            if (inputVisible) {
              await input.fill(`${team.name} part ${j + 1}`);
              await team.page.waitForTimeout(200);
            }
          }
        } else if (singleVisible) {
          console.log('    Using single answer handler...');
          await singleAnswerInput.fill(`${team.name} Q${questionNum}`);
        } else {
          console.log('    WARNING: No input type matched!');
          await captureScreenshot(team.page, `q${questionNum}-no-input-${team.name}`);
        }

        // Submit
        const submitBtn = team.page.locator('#submitAnswerBtn');
        const submitVisible = await submitBtn.isVisible().catch(() => false);
        const submitEnabled = submitVisible ? await submitBtn.isEnabled().catch(() => false) : false;
        console.log(`    Submit button: visible=${submitVisible}, enabled=${submitEnabled}`);

        if (submitVisible && submitEnabled) {
          await submitBtn.click();
          await team.page.waitForTimeout(SHORT_DELAY);
          console.log(`    ${team.name} submitted successfully`);
        } else {
          console.log(`    WARNING: Cannot submit - button not available`);
          await captureScreenshot(team.page, `q${questionNum}-no-submit-${team.name}`);
        }
      }

      // Check state AFTER submissions
      console.log('\n>>> AFTER submissions:');
      await logAdminState(adminPage);
      await captureScreenshot(adminPage, `q${questionNum}-after-admin`);

      // Try to advance to next question
      const nextBtn = adminPage.locator('#nextQuestionBtn');
      const nextVisible = await nextBtn.isVisible().catch(() => false);
      const nextEnabled = nextVisible ? await nextBtn.isEnabled().catch(() => false) : false;

      console.log(`\n>>> Next button: visible=${nextVisible}, enabled=${nextEnabled}`);

      if (nextEnabled) {
        console.log('>>> Clicking next question...');
        await nextBtn.click();
        await adminPage.waitForTimeout(STEP_DELAY);
        questionNum++;
      } else {
        console.log('>>> No next button available - end of round');

        // Check what buttons ARE available
        const lockBtn = adminPage.locator('#lockRoundBtn');
        const lockVisible = await lockBtn.isVisible().catch(() => false);
        console.log(`>>> Lock button visible: ${lockVisible}`);

        if (lockVisible) {
          console.log('>>> DIAGNOSIS: Round is complete, lock button is available');
        }

        await captureScreenshot(adminPage, `q${questionNum}-end-of-round`);
        break;
      }
    }

    logStep('DIAGNOSTIC COMPLETE', 'Check screenshots in e2e/test-results/diagnostics/');
    console.log('\nScreenshots captured at each step. Review them to identify the issue.');

    // Keep browser open briefly for manual inspection
    await adminPage.waitForTimeout(30000);
  });
});
