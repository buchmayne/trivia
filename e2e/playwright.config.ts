import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'html',

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    launchOptions: {
      slowMo: process.env.SLOW_MO ? parseInt(process.env.SLOW_MO) : 0,
    },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 13'] },
    },
    {
      name: 'qa-visual',
      testMatch: 'qa-visual.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        video: 'on',
        trace: 'on',
        launchOptions: {
          slowMo: 100,
        },
      },
    },
    {
      name: 'qa-robust',
      testMatch: 'qa-robust.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        video: 'on',
        trace: 'on',
        screenshot: 'on',
      },
    },
  ],

  webServer: process.env.CI ? undefined : {
    command: 'cd .. && uv run manage.py runserver',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
