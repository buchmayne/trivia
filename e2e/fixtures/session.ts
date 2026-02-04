import { test as base, expect, Page, BrowserContext, Browser } from '@playwright/test';

/**
 * Session data returned after creating a session
 */
export interface SessionData {
  code: string;
  adminToken: string;
}

/**
 * Team data returned after joining a session
 */
export interface TeamData {
  name: string;
  token: string;
  page: Page;
  context: BrowserContext;
}

/**
 * Extended test fixtures for session testing
 */
export interface SessionFixtures {
  /** Create a new game session and return admin page with session data */
  createSession: (gameName?: string) => Promise<{ page: Page; session: SessionData }>;

  /** Join a session as a team and return team page with team data */
  joinSession: (code: string, teamName: string) => Promise<TeamData>;

  /** Create multiple team contexts for parallel testing */
  createTeamContexts: (count: number) => Promise<BrowserContext[]>;
}

/**
 * Custom test with session fixtures
 */
export const test = base.extend<SessionFixtures>({
  createSession: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];

    const createSession = async (gameName?: string) => {
      const context = await browser.newContext();
      contexts.push(context);
      const page = await context.newPage();

      // Navigate to host page
      await page.goto('/quiz/play/host/');

      // Fill in admin name
      await page.fill('#adminName', 'Test Admin');

      // Select game (use first available if not specified)
      if (gameName) {
        await page.selectOption('#gameSelect', { label: gameName });
      } else {
        // Select first non-empty option
        const options = await page.locator('#gameSelect option').all();
        for (const option of options) {
          const value = await option.getAttribute('value');
          if (value) {
            await page.selectOption('#gameSelect', value);
            break;
          }
        }
      }

      // Check if password is required and fill it in
      const passwordField = page.locator('#gamePassword');
      const passwordGroup = page.locator('#passwordGroup');

      // Wait a moment for the password field to show/hide based on game selection
      await page.waitForTimeout(100);

      if (await passwordGroup.isVisible()) {
        // Get the password from the selected option's data-password attribute
        const password = await page.evaluate(() => {
          const select = document.getElementById('gameSelect') as HTMLSelectElement;
          const selectedOption = select.selectedOptions[0];
          return selectedOption?.dataset.password || '';
        });

        await passwordField.fill(password);
      }

      // Submit form
      await page.click('button[type="submit"]');

      // Wait for redirect to play page
      await page.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

      // Extract session code from URL
      const url = page.url();
      const code = url.match(/\/quiz\/play\/([A-Z0-9]{6})\//)?.[1];
      if (!code) {
        throw new Error('Failed to extract session code from URL');
      }

      // Get admin token from localStorage
      const adminToken = await page.evaluate((sessionCode) => {
        return localStorage.getItem(`session_${sessionCode}_admin`);
      }, code);

      if (!adminToken) {
        throw new Error('Failed to get admin token from localStorage');
      }

      return {
        page,
        session: { code, adminToken }
      };
    };

    await use(createSession);

    // Cleanup contexts
    for (const context of contexts) {
      await context.close();
    }
  },

  joinSession: async ({ browser }, use) => {
    const teamData: TeamData[] = [];

    const joinSession = async (code: string, teamName: string) => {
      const context = await browser.newContext();
      const page = await context.newPage();

      // Navigate to join page
      await page.goto('/quiz/play/join/');

      // Fill in session code
      await page.fill('#sessionCode', code);

      // Fill in team name
      await page.fill('#teamName', teamName);

      // Submit form
      await page.click('button[type="submit"]');

      // Wait for redirect to play page
      await page.waitForURL(/\/quiz\/play\/[A-Z0-9]{6}\//);

      // Get team token from localStorage
      const teamToken = await page.evaluate((sessionCode) => {
        return localStorage.getItem(`session_${sessionCode}_team`);
      }, code);

      if (!teamToken) {
        throw new Error('Failed to get team token from localStorage');
      }

      const data: TeamData = {
        name: teamName,
        token: teamToken,
        page,
        context
      };

      teamData.push(data);
      return data;
    };

    await use(joinSession);

    // Cleanup contexts
    for (const data of teamData) {
      await data.context.close();
    }
  },

  createTeamContexts: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];

    const createTeamContexts = async (count: number) => {
      for (let i = 0; i < count; i++) {
        const context = await browser.newContext();
        contexts.push(context);
      }
      return contexts;
    };

    await use(createTeamContexts);

    // Cleanup contexts
    for (const context of contexts) {
      await context.close();
    }
  }
});

export { expect };
