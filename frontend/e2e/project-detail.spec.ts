import { expect, test } from "@playwright/test";

import { goto, mockAllProjectApis,mockAuth, mockHealthOk } from "./helpers";

test.describe("Project Detail Page", () => {
  test.beforeEach(async ({ page }) => {
    mockAuth(page);
    await mockHealthOk(page);
    mockAllProjectApis(page, 42);
  });

  test("Shows project header with name, branch, and path", async ({ page }) => {
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("main").first()).toBeVisible({ timeout: 10_000 });
  });

  test("Shows onboarding wizard steps", async ({ page }) => {
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const onboardingTab = page.getByRole("button", { name: /Onboarding/ });
    await expect(onboardingTab).toBeVisible({ timeout: 10_000 });
    await onboardingTab.click();
    await expect(page.getByText("Repository Analysis").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Specification Generation").first()).toBeVisible();
    await expect(page.getByText("Architecture Design").first()).toBeVisible();
    await expect(page.getByText("Implementation Setup").first()).toBeVisible();
  });

  test("Tab switching: Overview is default tab", async ({ page }) => {
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const overviewTab = page.getByRole("button", { name: /Overview/ });
    await expect(overviewTab).toBeVisible({ timeout: 10_000 });
  });

  test("Tab switching: navigate to Specifications tab", async ({ page }) => {
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    // Use exact name — "Specifications" and "Specifications Technical" both match /Spec/
    const specTab = page.locator("aside").getByRole("button", { name: "Specifications", exact: true });
    await specTab.click();
    await expect(specTab).toBeVisible({ timeout: 10_000 });
  });

  test("Sprints tab shows sprint info", async ({ page }) => {
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const sprintTab = page.locator("aside").getByRole("button", { name: /Sprints/ });
    await expect(sprintTab).toBeVisible({ timeout: 10_000 });
    await sprintTab.click();
    await expect(page.getByText("Sprint 1 - Auth").first()).toBeVisible({ timeout: 15_000 });
  });

  test("Task Cycle tab shows work items when present", async ({ page }) => {
    mockAllProjectApis(page, 42, {
      features: { task_cycle_enabled: true },
      taskCycle: [
        {
          id: 101,
          project_id: 42,
          protocol_run_id: 1,
          title: "Implement login page",
          status: "in_progress",
          context_status: "ready",
          review_status: "pending",
          qa_status: "pending",
          owner_agent: "dev",
          helper_agents: [],
          helper_agent_summary: null,
          task_dir: "/tmp/work-item-101",
          artifact_refs: {},
          artifact_availability: {
            context_pack_md: true,
            review_report_md: false,
            test_report_md: false,
            rework_pack_json: false,
          },
          depends_on: [],
          pr_ready: false,
          blocking_clarifications: 0,
          blocking_policy_findings: 0,
          iteration_count: 0,
          max_iterations: 5,
          summary: "Create the login UI component",
        },
        {
          id: 102,
          project_id: 42,
          protocol_run_id: 1,
          title: "Setup auth middleware",
          status: "done",
          context_status: "ready",
          review_status: "passed",
          qa_status: "passed",
          owner_agent: "dev",
          helper_agents: [],
          helper_agent_summary: null,
          task_dir: "/tmp/work-item-102",
          artifact_refs: {},
          artifact_availability: {
            context_pack_md: true,
            review_report_md: true,
            test_report_md: true,
            rework_pack_json: false,
          },
          depends_on: [],
          pr_ready: false,
          blocking_clarifications: 0,
          blocking_policy_findings: 0,
          iteration_count: 0,
          max_iterations: 5,
          summary: "Configure authentication middleware",
        },
      ],
    });
    await goto(page, "/projects/42?tab=task_cycle");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const taskCycleTab = page.locator("aside").getByRole("button", { name: /Task Cycle/ });
    await expect(taskCycleTab).toBeVisible({ timeout: 10_000 });
    await taskCycleTab.click();
    // Wait for work items to load (React Query fetch + render)
    await expect(page.getByText("Implement login page").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Setup auth middleware").first()).toBeVisible({ timeout: 10_000 });
  });

  test("Task Cycle tab shows helper summary, task dir, and artifact preview actions", async ({ page }) => {
    mockAllProjectApis(page, 42, {
      features: { task_cycle_enabled: true },
      taskCycle: [
        {
          id: 501,
          project_id: 42,
          protocol_run_id: 1,
          title: "Implement login page",
          status: "context_ready",
          context_status: "needs_clarification",
          review_status: "pending",
          qa_status: "pending",
          owner_agent: "codex",
          helper_agents: ["trace", "tests"],
          helper_agent_summary: "2 helpers under the owner: 2 completed",
          task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/1/work-items/501",
          artifact_refs: {
            task_dir: "/tmp/repo/.devgodzilla/task-cycle/protocols/1/work-items/501",
            context_pack_json: "/tmp/context_pack.json",
            context_pack_md: "/tmp/context_pack.md",
            review_input_json: "/tmp/review_input.json",
            review_input_md: "/tmp/review_input.md",
            review_report_json: "/tmp/review_report.json",
            review_report_md: "/tmp/review_report.md",
            test_report_json: "/tmp/test_report.json",
            test_report_md: "/tmp/test_report.md",
            rework_pack_json: "/tmp/rework_pack.json",
            step_artifacts_dir: "/tmp/step-artifacts",
          },
          artifact_availability: {
            context_pack_md: true,
            review_report_md: true,
            test_report_md: true,
            rework_pack_json: false,
          },
          depends_on: [],
          pr_ready: false,
          blocking_clarifications: 2,
          blocking_policy_findings: 1,
          iteration_count: 1,
          max_iterations: 5,
          summary: "Waiting for repo entry points",
        },
      ],
    });
    await page.route("**/api/v1/work-items/501/artifacts/context_pack_md/content", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "context_pack_md",
          name: "context_pack.md",
          type: "text",
          content: "# Context Pack\n\nHelper-ready context",
          truncated: false,
        }),
      }),
    );

    await goto(page, "/projects/42?tab=task_cycle");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const taskCycleTab = page.locator("aside").getByRole("button", { name: /Task Cycle/ });
    await expect(taskCycleTab).toBeVisible({ timeout: 10_000 });
    await taskCycleTab.click();

    await expect(page.getByText("Helpers: trace, tests").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Helper activity: 2 helpers under the owner: 2 completed").first()).toBeVisible();
    await expect(page.getByText("PR Ready: no").first()).toBeVisible();
    await expect(
      page.getByText("/tmp/repo/.devgodzilla/task-cycle/protocols/1/work-items/501").first()
    ).toBeVisible();
    await expect(
      page.getByText("Implementation is blocked until context is ready and blocking clarifications are resolved.").first()
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "View Context" })).toBeVisible();
    await expect(page.getByRole("button", { name: "View Review" })).toBeVisible();
    await expect(page.getByRole("button", { name: "View QA" })).toBeVisible();
    await expect(page.getByRole("button", { name: "View Rework" })).toBeVisible();

    await page.getByRole("button", { name: "View Context" }).click();
    await expect(page.getByRole("heading", { name: "Context Pack" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Helper-ready context")).toBeVisible();
  });
});
