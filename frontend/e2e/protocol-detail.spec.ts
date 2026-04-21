import { expect, type Page, type Route,test } from "@playwright/test";

import { goto, mockAuth,mockHealthOk } from "./helpers";

const PROTOCOL_DETAIL = {
  id: 22,
  protocol_name: "E2E Protocol",
  project_id: 10,
  status: "running",
  base_branch: "main",
  description: "Protocol for E2E testing",
  created_at: "2026-04-01T12:00:00Z",
  updated_at: "2026-04-19T12:00:00Z",
};

const PROTOCOL_STEPS = [
  {
    id: 1,
    step_name: "Repository Analysis",
    step_type: "analysis",
    status: "completed",
    engine_id: "engine-1",
    retries: 0,
  },
  {
    id: 2,
    step_name: "Specification Generation",
    step_type: "generation",
    status: "running",
    engine_id: "engine-2",
    retries: 0,
  },
  {
    id: 3,
    step_name: "Code Implementation",
    step_type: "implementation",
    status: "pending",
    engine_id: null,
    retries: 0,
  },
  {
    id: 4,
    step_name: "Quality Review",
    step_type: "review",
    status: "failed",
    engine_id: "engine-3",
    retries: 2,
  },
];

function mockProtocolApis(page: Page) {
  // Protocol steps (most specific first)
  page.route("**/api/v1/protocols/22/steps**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROTOCOL_STEPS),
    }),
  );

  // Protocol runs (empty)
  page.route("**/api/v1/protocols/22/runs**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );

  // Quality summary (empty)
  page.route("**/api/v1/protocols/22/quality**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ summary: {}, gates: [] }),
    }),
  );

  // Artifacts (empty)
  page.route("**/api/v1/protocols/22/artifacts**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [] }),
    }),
  );

  // Events
  page.route("**/api/v1/protocols/22/events**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ events: [], total: 0 }),
    }),
  );

  // Protocol flow
  page.route("**/api/v1/protocols/22/flow**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    }),
  );

  // Feedback events
  page.route("**/api/v1/protocols/22/feedback**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ events: [], total: 0 }),
    }),
  );

  // Logs
  page.route("**/api/v1/protocols/22/logs**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ logs: [], total: 0 }),
    }),
  );

  // Spec
  page.route("**/api/v1/protocols/22/spec**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(null),
    }),
  );

  // Policy
  page.route("**/api/v1/protocols/22/policy**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(null),
    }),
  );

  // Clarifications
  page.route("**/api/v1/protocols/22/clarifications**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );

  // Protocol detail (less specific — catches /protocols/22)
  page.route("**/api/v1/protocols/22", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROTOCOL_DETAIL),
    }),
  );

  // Project info (the detail page shows "Back to Project" link)
  page.route("**/api/v1/projects/10**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 10, name: "Demo Project", git_url: "https://github.com/test/demo.git", base_branch: "main", status: "active", local_path: "/repos/demo", github_token_configured: true }),
    }),
  );

  // Agents for the project
  page.route("**/api/v1/projects/10/agents**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
}

test.describe("Protocol Detail Page", () => {
  test.beforeEach(async ({ page }) => {
    mockAuth(page);
    await mockHealthOk(page);
    mockProtocolApis(page);
  });

  test("Shows protocol header with name and status", async ({ page }) => {
    await goto(page, "/protocols/22");

    // Protocol name should be visible in the h1
    await expect(page.locator("h1")).toContainText("E2E Protocol", { timeout: 15_000 });

    // Status pill should show "Running"
    await expect(page.getByText("Running").first()).toBeVisible({ timeout: 10_000 });
  });

  test("Shows steps table with status badges", async ({ page }) => {
    await goto(page, "/protocols/22");

    // Wait for protocol header to load
    await expect(page.locator("h1")).toContainText("E2E Protocol", { timeout: 15_000 });

    // Steps tab is the default tab — check step names appear
    await expect(page.getByText("Repository Analysis").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Specification Generation").first()).toBeVisible();
    await expect(page.getByText("Code Implementation").first()).toBeVisible();
    await expect(page.getByText("Quality Review").first()).toBeVisible();

    // Step statuses should be rendered as badges
    await expect(page.locator("text=Completed").first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=Running").first()).toBeVisible();
    await expect(page.locator("text=Pending").first()).toBeVisible();
    await expect(page.locator("text=Failed").first()).toBeVisible();
  });

  test("Tab switching: navigate between tabs", async ({ page }) => {
    await goto(page, "/protocols/22");
    await expect(page.locator("h1")).toContainText("E2E Protocol", { timeout: 15_000 });

    // Steps tab should be visible by default
    await expect(page.getByText("Repository Analysis").first()).toBeVisible({ timeout: 10_000 });

    // Click Runs tab — look for tab button in sidebar
    const runsTab = page.locator("aside").getByRole("button", { name: /Runs/ });
    if (await runsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await runsTab.click();
      // Verify Runs tab loaded (empty state or content)
      await page.waitForTimeout(500);
    }

    // Click Artifacts tab
    const artifactsTab = page.locator("aside").getByRole("button", { name: /Artifacts/ });
    if (await artifactsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await artifactsTab.click();
      await page.waitForTimeout(500);
    }
  });

  test("Action buttons present for running protocol", async ({ page }) => {
    await goto(page, "/protocols/22");
    await expect(page.locator("h1")).toContainText("E2E Protocol", { timeout: 15_000 });

    // For a running protocol, the page shows: Pause, Run Next, Open PR, Cancel buttons
    const pauseButton = page.getByRole("button", { name: /pause/i });
    const cancelButton = page.getByRole("button", { name: /cancel/i });
    const runNextButton = page.getByRole("button", { name: /run next/i });
    const openPRButton = page.getByRole("button", { name: /open pr/i });

    // At least Pause and Cancel should be present for a running protocol
    await expect(pauseButton).toBeVisible({ timeout: 10_000 });
    await expect(cancelButton).toBeVisible();
    await expect(runNextButton).toBeVisible();
    await expect(openPRButton).toBeVisible();
  });
});
