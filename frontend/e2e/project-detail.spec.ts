import { expect, test } from "@playwright/test";

import { goto, mockHealthOk } from "./helpers";

const PROJECT = {
  id: 42,
  name: "Test Project",
  description: "A project for e2e testing",
  git_url: "https://github.com/test/project.git",
  local_path: "/home/user/repos/test-project",
  github_token_configured: true,
  base_branch: "main",
  project_classification: "web-application",
  status: "active",
  policy_pack_key: null,
  policy_pack_version: null,
  policy_overrides: null,
  policy_repo_local_enabled: null,
  policy_effective_hash: null,
  policy_enforcement_mode: null,
  constitution_version: null,
  created_at: "2026-04-01T12:00:00Z",
  updated_at: "2026-04-19T12:00:00Z",
};

const ONBOARDING = {
  project_id: 42,
  status: "completed",
  stages: [
    { name: "repository_analysis", status: "completed", started_at: "2026-04-01T12:00:00Z", completed_at: "2026-04-01T13:00:00Z" },
    { name: "specification_generation", status: "completed", started_at: "2026-04-01T13:00:00Z", completed_at: "2026-04-01T14:00:00Z" },
    { name: "architecture_design", status: "running", started_at: "2026-04-01T14:00:00Z", completed_at: null },
    { name: "implementation_setup", status: "pending", started_at: null, completed_at: null },
  ],
  events: [],
  blocking_clarifications: 0,
};

const PROTOCOLS = [
  {
    id: 1,
    protocol_name: "auth-flow",
    project_id: 42,
    status: "running",
    base_branch: "main",
    created_at: "2026-04-10T12:00:00Z",
    updated_at: "2026-04-19T12:00:00Z",
  },
  {
    id: 2,
    protocol_name: "payment-integration",
    project_id: 42,
    status: "completed",
    base_branch: "main",
    created_at: "2026-04-05T12:00:00Z",
    updated_at: "2026-04-15T12:00:00Z",
  },
];

const TASK_CYCLE = {
  work_items: [
    {
      id: 101,
      step_run_id: 1,
      status: "in_progress",
      review_status: "pending",
      qa_status: "pending",
      title: "Implement login page",
      description: "Create the login UI component",
    },
    {
      id: 102,
      step_run_id: 2,
      status: "done",
      review_status: "approved",
      qa_status: "passed",
      title: "Setup auth middleware",
      description: "Configure authentication middleware",
    },
  ],
};

const SPRINTS = [
  {
    id: 1,
    name: "Sprint 1 - Auth",
    status: "active",
    project_id: 42,
    start_date: "2026-04-01",
    end_date: "2026-04-14",
    tasks: [
      { id: 1, title: "Login page", status: "done" },
      { id: 2, title: "Auth API", status: "in_progress" },
      { id: 3, title: "User model", status: "todo" },
    ],
  },
];

function mockProjectApis(page) {
  // Project detail — specific routes first (more specific patterns before general ones)
  page.route("**/api/v1/projects/42/onboarding**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ONBOARDING),
    }),
  );
  page.route("**/api/v1/projects/42/protocols**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROTOCOLS),
    }),
  );
  page.route("**/api/v1/projects/42/task-cycle**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TASK_CYCLE),
    }),
  );
  page.route("**/api/v1/projects/42/sprints**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SPRINTS),
    }),
  );
  page.route("**/api/v1/projects/42/agents**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
  page.route("**/api/v1/projects/42/specifications**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
  page.route("**/api/v1/projects/42/policy**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    }),
  );
  page.route("**/api/v1/projects/42/clarifications**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
  page.route("**/api/v1/projects/42/branches**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
  page.route("**/api/v1/projects/42/workflow**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ nodes: [], edges: [] }),
    }),
  );

  // Generic project detail (catches /api/v1/projects/42 but not sub-routes)
  // This MUST come AFTER all the more specific routes
  page.route("**/api/v1/projects/42", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROJECT),
    }),
  );

  // Catch-all for any other project API calls that aren't mocked
  page.route("**/api/v1/projects/42/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
}

test.describe("Project Detail Page", () => {
  test.beforeEach(async ({ page }) => {
    await mockHealthOk(page);
    mockProjectApis(page);
  });

  test("Shows project header with name, branch, and path", async ({ page }) => {
    await goto(page, "/projects/42");

    // The project detail page should show the project name
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // Branch info should be visible
    await expect(page.getByText("main").first()).toBeVisible({ timeout: 10_000 });
  });

  test("Shows onboarding wizard steps", async ({ page }) => {
    await goto(page, "/projects/42");

    // Wait for project to load
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // Click the Onboarding nav item in the sidebar
    const onboardingNav = page.getByText("Onboarding").first();
    await onboardingNav.click();

    // Check onboarding stage names are visible
    await expect(page.getByText("Repository Analysis").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Specification Generation").first()).toBeVisible();
    await expect(page.getByText("Architecture Design").first()).toBeVisible();
    await expect(page.getByText("Implementation Setup").first()).toBeVisible();
  });

  test("Tab switching: Overview is default tab", async ({ page }) => {
    await goto(page, "/projects/42");

    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // The Overview nav item should be visible in the sidebar
    const overviewNavItem = page.getByText("Overview").first();
    await expect(overviewNavItem).toBeVisible({ timeout: 10_000 });
  });

  test("Tab switching: navigate to Specifications tab", async ({ page }) => {
    await goto(page, "/projects/42");

    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // Click Specifications in sidebar
    const specNavItem = page.getByText("Specifications").first();
    await specNavItem.click();
    await expect(specNavItem).toBeVisible({ timeout: 10_000 });
  });

  test("Sprints tab shows sprint info", async ({ page }) => {
    await goto(page, "/projects/42");

    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // Click the Sprint tab in sidebar
    const sprintNav = page.getByText("Sprint").first();
    await sprintNav.click();

    // Should show sprint info
    await expect(page.getByText("Sprint 1 - Auth").first()).toBeVisible({ timeout: 10_000 });
  });

  test("Task Cycle tab shows work items when present", async ({ page }) => {
    await goto(page, "/projects/42");

    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });

    // Click Task Cycle in sidebar
    const taskCycleNav = page.getByText("Task Cycle").first();
    await taskCycleNav.click();

    // Should show work items
    await expect(page.getByText("Implement login page").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Setup auth middleware").first()).toBeVisible();
  });
});
