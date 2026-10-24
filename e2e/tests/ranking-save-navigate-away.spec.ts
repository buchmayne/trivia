import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
  adminLockRound,
  teamWaitForQuestion,
} from '../helpers/session-helpers';

type Page = import('@playwright/test').Page;

/**
 * Regression test for a lost ranking submission:
 *
 * A team ranked a ranking question (drag & drop), then navigated to another
 * question within the 1.5s auto-save debounce window. The pending debounce
 * either never fired (page left / background-tab timer throttling) or fired
 * after the navigation and saved under the new question's id. Either way the
 * ranking question had no TeamAnswer at lock time, so the scoring view showed
 * "No answer" for every part.
 *
 * The fix (a) saves a ranking placement immediately, with question id and
 * order captured at drag time, and (b) snapshots question + answer when the
 * debounced save is scheduled, so a late-firing save can't be repointed.
 */

const RANKING_GAME = 'Game 14'; // example game; round 1 question 1 is Ranking

async function enableTeamNavigation(adminPage: Page, teamPage: Page) {
  await adminPage.locator('#toggleTeamNavBtn').click();
  await expect(teamPage.locator('#teamQuestionNav')).toBeVisible({ timeout: 10000 });
}

async function teamQuestionOptions(teamPage: Page): Promise<string[]> {
  return teamPage
    .locator('#teamQuestionSelector option')
    .evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value).filter(Boolean));
}

async function selectQuestionAndWait(teamPage: Page, questionId: string) {
  await teamPage.selectOption('#teamQuestionSelector', questionId);
  // The change handler renders the new question's inputs asynchronously.
  await teamPage.waitForTimeout(700);
}

/** Read the team's stored answer_text for a question straight from the server. */
async function readTeamAnswerFromServer(teamPage: Page, questionId: string) {
  return teamPage.evaluate(async (qid) => {
    const parts = window.location.pathname.split('/').filter(Boolean);
    const code = parts[parts.indexOf('play') + 1];
    const token = localStorage.getItem(`session_${code}_team`);
    const response = await fetch(`/quiz/api/sessions/${code}/team/answers/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    const match = (data.answers || []).find(
      (a: { question_id: number; answer_text: string }) => String(a.question_id) === qid
    );
    return match ? match.answer_text : null;
  }, questionId);
}

/**
 * Drag the first ranking item below the second one using real mouse events
 * (SortableJS runs with forceFallback, which listens to pointer events).
 * Returns the ranked answer-id order before and after the drag.
 */
async function dragFirstRankingItemDown(teamPage: Page) {
  const items = teamPage.locator('#rankingList .ranking-item');
  await expect(items.first()).toBeVisible({ timeout: 10000 });

  // Mouse events land at viewport coordinates, so the list must be on
  // screen or the drag silently hits whatever is under the given point.
  await items.nth(0).scrollIntoViewIfNeeded();
  await teamPage.waitForTimeout(300);

  const readOrder = () =>
    items.evaluateAll((els) =>
      els.map((el) => Number((el as HTMLElement).dataset.answerId))
    );

  const before = await readOrder();

  const src = await items.nth(0).boundingBox();
  const tgt = await items.nth(1).boundingBox();
  if (!src || !tgt) throw new Error('ranking items not rendered');

  await teamPage.mouse.move(src.x + 50, src.y + src.height / 2);
  await teamPage.mouse.down();
  await teamPage.waitForTimeout(120);
  // Travel in steps past SortableJS's 3px fallbackTolerance and across the
  // next item; slow, stepped moves let its live-reorder logic keep up.
  for (let step = 1; step <= 12; step++) {
    await teamPage.mouse.move(
      tgt.x + 50,
      src.y + src.height / 2 + ((tgt.y + tgt.height / 2) - (src.y + src.height / 2)) * (step / 12),
      { steps: 2 }
    );
    await teamPage.waitForTimeout(40);
  }
  await teamPage.mouse.up();

  const after = await readOrder();
  expect(JSON.stringify(after)).not.toBe(JSON.stringify(before));
  return { before, after };
}

test.describe('Ranking answers survive navigating away immediately', () => {
  test('drag save lands even when the team leaves the question at once', async ({
    createSession,
    joinSession,
  }) => {
    test.setTimeout(180000);

    const { page: adminPage, session } = await createSession(RANKING_GAME);
    await waitForAdminView(adminPage);
    const team = await joinSession(session.code, 'Ranking Team');
    await waitForTeamView(team.page);

    await adminStartGame(adminPage);
    await enableTeamNavigation(adminPage, team.page);

    // Round 1 opens with the host (and the team) on the Ranking question
    await teamWaitForQuestion(team.page);
    await expect(team.page.locator('#rankingList')).toBeVisible();

    const options = await teamQuestionOptions(team.page);
    expect(options.length).toBeGreaterThan(1);
    const rankingQuestionId = options[0];

    // Rank the items
    const { after: draggedIds } = await dragFirstRankingItemDown(team.page);

    // THE BUG SCENARIO: navigate away immediately, well inside the old
    // 1.5-second debounce window. Before the fix the pending timer was
    // repointed (or lost entirely) and this ranking never reached the server.
    const otherId = options.find((o) => o !== rankingQuestionId)!;
    await selectQuestionAndWait(team.page, otherId);

    // Wait out the old debounce window with margin, then check the server
    await team.page.waitForTimeout(2500);

    const savedRankingText = await readTeamAnswerFromServer(team.page, rankingQuestionId);
    expect(savedRankingText).not.toBeNull();
    expect(savedRankingText!.trim()).not.toBe('');
    expect(JSON.parse(savedRankingText!)).toEqual(draggedIds);

    // The drag must not have been repointed onto the question navigated to
    const otherText = await readTeamAnswerFromServer(team.page, otherId);
    if (otherText && otherText.trim() !== '') {
      expect(JSON.parse(otherText)).not.toEqual(draggedIds);
    }

    // Lock the round: the ranking submission must be split into per-part
    // rows holding 1-based positions. Before the fix these were all empty
    // placeholders ("No answer") because no submission existed at lock time.
    await adminLockRound(adminPage);

    const positions = await adminPage.evaluate(async (qid) => {
      const parts = window.location.pathname.split('/').filter(Boolean);
      const code = parts[parts.indexOf('play') + 1];
      const token = localStorage.getItem(`session_${code}_admin`);
      const response = await fetch(`/quiz/api/sessions/${code}/admin/scoring-data/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      const q = data.questions.find((x: { id: number }) => x.id === qid);
      return q.team_answers[0].parts.map((p: { answer_text: string }) => p.answer_text);
    }, Number(rankingQuestionId));

    expect(positions.filter((v: string) => v === '')).toHaveLength(0);
    expect(positions.map(Number).sort()).toEqual(
      Array.from({ length: draggedIds.length }, (_, i) => i + 1)
    );
  });
});
