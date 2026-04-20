import { expect, test } from "@playwright/test";

import { goto, mockAuth, mockConsoleBasics } from "./helpers";

// ─── Shared mock data ──────────────────────────────────────────────────

const PROTOCOL_ID = 23;

const PROTOCOL_DETAIL = {
  id: PROTOCOL_ID,
  protocol_name: "SubPage Test Protocol",
  project_id: 10,
  status: "running",
  base_branch: "main",
  description: "Protocol for sub-page E2E testing",
  created_at: "2026-04-01T12:00:00Z",
  updated_at: "2026-04-19T12:00:00Z",
};

const PROJECT_DETAIL = {
  id: 10,
  name: "SubPage Test Project",
  git_url: "https://github.com/test/subpage.git",
  base_branch: "main",
  status: "active",
  local_path: "/repos/subpage",
  github_token_configured: true,
};

const STEP_RUN = {
  id: 1,
  run_id: "abc123def456",
  protocol_run_id: 100,
  step_name: "Repository Analysis",
  step_type: "analysis",
  status: "completed",
  step_index: 0,
  engine_id: "engine-1",
  assigned_agent: "opencode",
  retries: 0,
  model: "glm-5",
};

const CODEx_RUN = {
  run_id: "codex-run-001",
  protocol_run_id: 100,
  run_kind: "codex",
  status: "completed",
  attempt: 1,
  cost_tokens: 500,
  started_at: "2026-04-10T10:00:00Z",
  created_at: "2026-04-10T10:00:00Z",
};

// ─── Protocol sub-page mocks ───────────────────────────────────────────

function mockProtocolSubPageApis(page: import("@playwright/test").Page) {
  const json = (data: unknown, status = 200) => ({
    status,
    contentType: "application/json" as const,
    body: JSON.stringify(data),
  });

  // Protocol detail — most specific routes first
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/events**`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/policy/findings**`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/policy/snapshot**`, (r) => r.fulfill(json({ hash: "abc", policy: {} })));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/policy**`, (r) => r.fulfill(json(null)));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/runs**`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/spec**`, (r) => r.fulfill(json(null)));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/steps**`, (r) => r.fulfill(json([STEP_RUN])));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/artifacts**`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/quality**`, (r) => r.fulfill(json({ summary: {}, gates: [] })));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/flow**`, (r) => r.fulfill(json({})));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/feedback**`, (r) => r.fulfill(json({ events: [], total: 0 })));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/logs**`, (r) => r.fulfill(json({ logs: [], total: 0 })));
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}/clarifications**`, (r) => r.fulfill(json([])));

  // Protocol detail — exact catch (less specific)
  page.route(`**/api/v1/protocols/${PROTOCOL_ID}`, (r) => r.fulfill(json(PROTOCOL_DETAIL)));

  // Project info for "Back to Project" links
  page.route("**/api/v1/projects/10**", (r) => r.fulfill(json(PROJECT_DETAIL)));
  page.route("**/api/v1/projects/10/agents**", (r) => r.fulfill(json([])));
}

// ─── Step sub-page mocks ───────────────────────────────────────────────

const STEP_ID = 98;

function mockStepSubPageApis(page: import("@playwright/test").Page) {
  const json = (data: unknown) => ({
    status: 200,
    contentType: "application/json" as const,
    body: JSON.stringify(data),
  });

  // Step endpoints — exact URL matches (no trailing **)
  page.route(`**/api/v1/steps/${STEP_ID}/runs`, (r) =>
    r.fulfill(json([CODEx_RUN])),
  );
  page.route(`**/api/v1/steps/${STEP_ID}/policy/findings`, (r) =>
    r.fulfill(json([])),
  );
  page.route(`**/api/v1/steps/${STEP_ID}/artifacts`, (r) =>
    r.fulfill(json([])),
  );
  page.route(`**/api/v1/steps/${STEP_ID}/quality`, (r) =>
    r.fulfill(json(null)),
  );
  page.route(`**/api/v1/steps/${STEP_ID}/feedback`, (r) =>
    r.fulfill(json([])),
  );

  // Protocol sub-resources for protocol_run_id=100 (exact URL, no trailing **)
  page.route("**/api/v1/protocols/100/steps", (r) =>
    r.fulfill(json([STEP_RUN])),
  );
  page.route("**/api/v1/protocols/100/runs", (r) =>
    r.fulfill(json([CODEx_RUN])),
  );

  // Protocol detail — regex for exact match
  page.route(new RegExp("/api/v1/protocols/100$"), (r) =>
    r.fulfill(json(PROTOCOL_DETAIL)),
  );

  // Project detail — regex for exact match (protocol has project_id: 10)
  page.route(new RegExp("/api/v1/projects/10$"), (r) =>
    r.fulfill(json(PROJECT_DETAIL)),
  );
}

// ─── Sprint board mocks ────────────────────────────────────────────────

const SPRINT_PROJECT_ID = 78;

function mockSprintBoardApis(page: import("@playwright/test").Page) {
  const json = (data: unknown) => ({
    status: 200,
    contentType: "application/json" as const,
    body: JSON.stringify(data),
  });

  const project = {
    id: SPRINT_PROJECT_ID,
    name: "Sprint Board Project",
    git_url: "https://github.com/test/sprint.git",
    base_branch: "main",
    status: "active",
    local_path: "/repos/sprint",
    github_token_configured: true,
  };

  // Project detail and sub-resources
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/onboarding/?`, (r) =>
    r.fulfill(json({ project_id: SPRINT_PROJECT_ID, status: "completed", stages: [], events: [], blocking_clarifications: 0 })),
  );
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/protocols/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/task-cycle/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/sprints/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/agents/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/specifications/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/policy/?`, (r) => r.fulfill(json({})));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/policy/findings/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/clarifications/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/branches/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/workflow/?`, (r) => r.fulfill(json({ nodes: [], edges: [] })));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/commits/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/projects/${SPRINT_PROJECT_ID}/pulls/?`, (r) => r.fulfill(json([])));
  page.route(`**/api/v1/speckit/status/${SPRINT_PROJECT_ID}`, (r) => r.fulfill(json({ status: "not_started" })));
  page.route(`**/api/v1/speckit/specs/${SPRINT_PROJECT_ID}`, (r) => r.fulfill(json([])));
  page.route(new RegExp(`/api/v1/projects/${SPRINT_PROJECT_ID}$`), (r) => r.fulfill(json(project)));

  // Execution page may need runs
  page.route("**/api/v1/runs**", (r) => r.fulfill(json([])));
}

// ═══════════════════════════════════════════════════════════════════════
// Test suites
// ═══════════════════════════════════════════════════════════════════════

test.describe("Protocol sub-pages", () => {
  test.beforeEach(async ({ page }) => {
    mockAuth(page);
    mockConsoleBasics(page);
    mockProtocolSubPageApis(page);
  });

  test("Protocol events sub-page renders", async ({ page }) => {
    await goto(page, `/protocols/${PROTOCOL_ID}/events`);

    // Page should NOT show "Protocol not found"
    await expect(page.getByText("Protocol not found")).not.toBeVisible();

    // Should show protocol name and Events header
    await expect(page.locator("h1")).toContainText("SubPage Test Protocol - Events", { timeout: 15_000 });
  });

  test("Protocol policy sub-page renders", async ({ page }) => {
    await goto(page, `/protocols/${PROTOCOL_ID}/policy`);

    await expect(page.getByText("Protocol not found")).not.toBeVisible();
    await expect(page.locator("h1")).toContainText("SubPage Test Protocol - Policy", { timeout: 15_000 });
  });

  test("Protocol runs sub-page renders", async ({ page }) => {
    await goto(page, `/protocols/${PROTOCOL_ID}/runs`);

    await expect(page.getByText("Protocol not found")).not.toBeVisible();
    await expect(page.locator("h1")).toContainText("SubPage Test Protocol - Runs", { timeout: 15_000 });
  });

  test("Protocol spec sub-page renders", async ({ page }) => {
    await goto(page, `/protocols/${PROTOCOL_ID}/spec`);

    await expect(page.getByText("Protocol not found")).not.toBeVisible();
    await expect(page.locator("h1")).toContainText("SubPage Test Protocol - Spec", { timeout: 15_000 });
  });

  test("Protocol steps sub-page renders", async ({ page }) => {
    await goto(page, `/protocols/${PROTOCOL_ID}/steps`);

    await expect(page.getByText("Protocol not found")).not.toBeVisible();
    await expect(page.locator("h1")).toContainText("SubPage Test Protocol - Steps", { timeout: 15_000 });
  });
});

test.describe("Step sub-pages", () => {
  test.beforeEach(async ({ page }) => {
    mockAuth(page);
    mockConsoleBasics(page);
    mockStepSubPageApis(page);
  });

  test("Step policy sub-page renders", async ({ page }) => {
    await goto(page, `/steps/${STEP_ID}/policy`);

    // Header should contain a valid step ID, not NaN
    const headerText = await page.locator("h1").textContent({ timeout: 15_000 });
    expect(headerText).not.toContain("NaN");
    expect(headerText).toContain("Step Policy Findings");
  });

  test("Step runs sub-page renders", async ({ page }) => {
    await goto(page, `/steps/${STEP_ID}/runs`);

    const bodyText = await page.locator("body").textContent({ timeout: 15_000 });
    expect(bodyText).not.toContain("NaN");
    await expect(page.locator("h1")).toContainText("Step Runs", { timeout: 15_000 });
  });
});

test.describe("Sprint board", () => {
  test("Sprint board renders without NaN links", async ({ page }) => {
    mockAuth(page);
    mockConsoleBasics(page);
    mockSprintBoardApis(page);

    // Sprint board redirects to /projects/:id/execution
    await goto(page, `/projects/${SPRINT_PROJECT_ID}/sprint-board`);

    // Wait for the page to settle (may redirect to execution)
    await page.waitForTimeout(2000);

    // Check no NaN or undefined in links
    const links = page.locator("a[href]");
    const count = await links.count();
    for (let i = 0; i < count; i++) {
      const href = await links.nth(i).getAttribute("href");
      expect(href).not.toContain("NaN");
      expect(href).not.toContain("undefined");
    }
  });
});

test.describe("Step detail navigation", () => {
  test("Steps page has Back to Project link", async ({ page }) => {
    mockAuth(page);
    mockConsoleBasics(page);
    mockStepSubPageApis(page);

    await goto(page, `/steps/${STEP_ID}`);

    // The step detail page shows "Back to Project" link when protocol is loaded
    const backLink = page.locator("a", { hasText: "Back to Project" });
    await expect(backLink).toBeVisible({ timeout: 15_000 });

    const href = await backLink.getAttribute("href");
    expect(href).toContain("/projects/");
    expect(href).not.toContain("NaN");
    expect(href).not.toContain("undefined");
  });
});
