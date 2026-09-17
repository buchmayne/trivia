import { test, expect } from '../fixtures/session';
import {
  waitForAdminView,
  waitForTeamView,
  adminStartGame,
} from '../helpers/session-helpers';

/**
 * E2E coverage for team recovery after losing a team token.
 *
 * The reported bug: a player navigated away mid-game, came back with no
 * credentials, and re-entered the same code and team name on the join page.
 * Joining rejected them with "Team name taken" and there was no route back
 * into their own team.
 *
 * These tests exercise all three recovery entry points:
 *   1. The join page, which now offers rejoin on a name collision.
 *   2. The dedicated rejoin page reached from the Host-or-Join page.
 *   3. The play page, which offers rejoin when it finds no credentials.
 */

/** Wipe every trace of the team's identity, as a cleared browser would. */
async function clearStoredCredentials(page: import('@playwright/test').Page) {
  await page.evaluate(() => localStorage.clear());
  await page.context().clearCookies();
}

/**
 * Clear only localStorage, leaving the HttpOnly cookie in place. This is the
 * common real-world loss: script-writable storage goes away (cleared data,
 * storage eviction) while cookies survive.
 */
async function clearLocalStorageOnly(page: import('@playwright/test').Page) {
  await page.evaluate(() => localStorage.clear());
}

test.describe('Team rejoin after losing credentials', () => {
  test('join page offers rejoin instead of dead-ending on a taken name', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Comeback Kids');
    await waitForTeamView(team.page);
    const originalToken = team.token;

    // Game is under way when the player drops out - this is the reported case.
    await adminStartGame(adminPage);

    // The player loses their credentials and returns to the join page.
    await clearStoredCredentials(team.page);
    await team.page.goto('/quiz/play/join/');
    await team.page.fill('#sessionCode', session.code);
    await team.page.fill('#teamName', 'Comeback Kids');
    await team.page.click('#joinForm button[type="submit"]');

    // Instead of a bare "Team name taken" error, they get an offer.
    const offer = team.page.locator('#rejoinOffer');
    await expect(offer).toBeVisible({ timeout: 10000 });
    await expect(team.page.locator('#rejoinOfferText')).toContainText('Comeback Kids');

    await team.page.click('#rejoinOfferBtn');

    // Back in the game, on the same team.
    await team.page.waitForURL(new RegExp(`/quiz/play/${session.code}/`));
    await waitForTeamView(team.page);

    const recoveredToken = await team.page.evaluate(
      (code) => localStorage.getItem(`session_${code}_team`),
      session.code
    );
    expect(recoveredToken).toBe(originalToken);
  });

  test('join page offers rejoin with the team name as originally spelled', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Quiz Wizards');
    await waitForTeamView(team.page);

    await clearStoredCredentials(team.page);
    await team.page.goto('/quiz/play/join/');
    await team.page.fill('#sessionCode', session.code);
    // Players don't remember their own capitalisation.
    await team.page.fill('#teamName', 'quiz wizards');
    await team.page.click('#joinForm button[type="submit"]');

    await expect(team.page.locator('#rejoinOfferText')).toContainText('Quiz Wizards', {
      timeout: 10000,
    });
  });

  test('a genuinely new team name still joins normally', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'First Team');
    await waitForTeamView(team.page);

    // A different browser joining under a different name sees no offer.
    await clearStoredCredentials(team.page);
    await team.page.goto('/quiz/play/join/');
    await team.page.fill('#sessionCode', session.code);
    await team.page.fill('#teamName', 'Second Team');
    await team.page.click('#joinForm button[type="submit"]');

    await team.page.waitForURL(new RegExp(`/quiz/play/${session.code}/`));
    await waitForTeamView(team.page);
    await expect(team.page.locator('#rejoinOffer')).toBeHidden();
  });

  test('rejoin page recovers a team from code and name alone', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Lost Sheep');
    await waitForTeamView(team.page);
    const originalToken = team.token;

    await adminStartGame(adminPage);

    // Everything is gone - all they have is the code and their team name.
    await clearStoredCredentials(team.page);
    await team.page.goto('/quiz/play/rejoin/');

    // With no stored tokens there is nothing to resume in one tap.
    await expect(team.page.locator('#resumeSection')).toBeHidden();

    await team.page.fill('#sessionCode', session.code);
    await team.page.fill('#teamName', 'Lost Sheep');
    await team.page.click('#rejoinForm button[type="submit"]');

    await team.page.waitForURL(new RegExp(`/quiz/play/${session.code}/`));
    await waitForTeamView(team.page);

    const recoveredToken = await team.page.evaluate(
      (code) => localStorage.getItem(`session_${code}_team`),
      session.code
    );
    expect(recoveredToken).toBe(originalToken);
  });

  test('rejoin page offers one-tap resume when the token is still stored', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Still Here');
    await waitForTeamView(team.page);

    // Token intact - the player just lost track of the URL.
    await team.page.goto('/quiz/play/rejoin/');

    const resumeSection = team.page.locator('#resumeSection');
    await expect(resumeSection).toBeVisible({ timeout: 10000 });
    await expect(resumeSection).toContainText('Still Here');
    await expect(resumeSection).toContainText(session.code);

    await resumeSection.locator('a').first().click();

    await team.page.waitForURL(new RegExp(`/quiz/play/${session.code}/`));
    await waitForTeamView(team.page);
  });

  test('rejoin page reports an unknown team name', async ({ createSession }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const context = await adminPage.context().browser()!.newContext();
    const page = await context.newPage();

    await page.goto('/quiz/play/rejoin/');
    await page.fill('#sessionCode', session.code);
    await page.fill('#teamName', 'Never Existed');
    await page.click('#rejoinForm button[type="submit"]');

    const error = page.locator('#error');
    await expect(error).toBeVisible({ timeout: 10000 });
    await expect(error).toContainText('Never Existed');

    await context.close();
  });

  test('play page offers rejoin when it finds no credentials', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Ghost Team');
    await waitForTeamView(team.page);
    const originalToken = team.token;

    // Land directly on the play URL with nothing stored - previously this
    // showed only host/join links, with no way back into the team.
    await clearStoredCredentials(team.page);
    await team.page.goto(`/quiz/play/${session.code}/`);

    const rejoinForm = team.page.locator('#rejoinForm');
    await expect(rejoinForm).toBeVisible({ timeout: 10000 });

    await team.page.fill('#rejoinTeamName', 'Ghost Team');
    await rejoinForm.locator('button[type="submit"]').click();

    await waitForTeamView(team.page);

    const recoveredToken = await team.page.evaluate(
      (code) => localStorage.getItem(`session_${code}_team`),
      session.code
    );
    expect(recoveredToken).toBe(originalToken);
  });

  test('cookie puts a team straight back in with nothing typed', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Cookie Crew');
    await waitForTeamView(team.page);
    const originalToken = team.token;

    await adminStartGame(adminPage);

    // localStorage is gone but the HttpOnly cookie survives.
    await clearLocalStorageOnly(team.page);
    await team.page.goto(`/quiz/play/${session.code}/`);

    // No rejoin form, no typing - straight back onto the team.
    await waitForTeamView(team.page);
    await expect(team.page.locator('#rejoinForm')).toBeHidden();

    // And localStorage is re-seeded from the cookie for subsequent calls.
    const recoveredToken = await team.page.evaluate(
      (code) => localStorage.getItem(`session_${code}_team`),
      session.code
    );
    expect(recoveredToken).toBe(originalToken);
  });

  test('cookie is HttpOnly and not readable from JS', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Hidden Token');
    await waitForTeamView(team.page);

    const cookies = await team.page.context().cookies();
    const tokenCookie = cookies.find((cookie) => cookie.name === 'tw_team_tokens');
    expect(tokenCookie).toBeTruthy();
    expect(tokenCookie!.httpOnly).toBe(true);
    expect(tokenCookie!.path).toBe('/quiz/');

    // Not visible to page scripts
    const visibleToJs = await team.page.evaluate(() =>
      document.cookie.includes('tw_team_tokens')
    );
    expect(visibleToJs).toBe(false);
  });

  test('rejoin page lists remembered sessions server-side', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Remembered Team');
    await waitForTeamView(team.page);

    // Storage cleared, cookie intact: the list comes from the server.
    await clearLocalStorageOnly(team.page);
    await team.page.goto('/quiz/play/rejoin/');

    const resumeSection = team.page.locator('#resumeSection');
    await expect(resumeSection).toBeVisible();
    await expect(resumeSection).toContainText('Remembered Team');
    await expect(resumeSection).toContainText(session.code);

    // Rendered server-side, so it needs no JS validation round trip
    await expect(
      resumeSection.locator(`a[data-code="${session.code}"]`)
    ).toHaveCount(1);

    await resumeSection.locator('a').first().click();
    await team.page.waitForURL(new RegExp(`/quiz/play/${session.code}/`));
    await waitForTeamView(team.page);
  });

  test('a team is not offered a resume for someone else session', async ({
    createSession,
    joinSession,
  }) => {
    const { page: adminPage, session } = await createSession();
    await waitForAdminView(adminPage);

    const team = await joinSession(session.code, 'Owner Team');
    await waitForTeamView(team.page);

    // A different browser has no cookie for this session.
    const strangerContext = await adminPage.context().browser()!.newContext();
    const strangerPage = await strangerContext.newPage();
    await strangerPage.goto('/quiz/play/rejoin/');

    await expect(strangerPage.locator('#resumeSection')).toBeHidden();

    // And landing on the play URL gives them no seat.
    await strangerPage.goto(`/quiz/play/${session.code}/`);
    await expect(strangerPage.locator('#rejoinForm')).toBeVisible({ timeout: 10000 });
    await expect(strangerPage.locator('#teamView')).toBeHidden();

    await strangerContext.close();
  });

  test('host landing page links to the rejoin page', async ({ createSession }) => {
    const { page } = await createSession();
    await waitForAdminView(page);

    await page.goto('/quiz/play/');
    const rejoinLink = page.locator('a[href="/quiz/play/rejoin/"]');
    await expect(rejoinLink).toBeVisible();
    await expect(rejoinLink).toContainText('Rejoin a Game');
  });
});
