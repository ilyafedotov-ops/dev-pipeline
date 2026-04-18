import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration for DevGodzilla Console.
 *
 * By default, tests connect to the dev server already running on port 3000.
 * Set PLAYWRIGHT_START_SERVER=1 to let Playwright start its own Next.js instance.
 */
const port = process.env.PLAYWRIGHT_START_SERVER ? 3107 : 3000;
const serverURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: serverURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  ...(process.env.PLAYWRIGHT_START_SERVER
    ? {
        webServer: {
          command: `pnpm exec next dev --hostname 127.0.0.1 --port ${port}`,
          url: `${serverURL}/console`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }
    : {}),
  outputDir: "test-results/playwright",
});
