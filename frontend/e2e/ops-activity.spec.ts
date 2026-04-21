import { expect, test } from "@playwright/test";

const API_PREFIXES = ["**/api/v1", "**/mock-api"] as const;

function routeApi(
  page: import("@playwright/test").Page,
  path: string,
  handler: Parameters<typeof page.route>[1],
) {
  for (const prefix of API_PREFIXES) {
    page.route(`${prefix}${path}`, handler);
  }
}

function json(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json" as const,
    body: JSON.stringify(data),
  };
}

function mockConsoleBasics(page: import("@playwright/test").Page) {
  routeApi(page, "/auth/**", (route) =>
    route.fulfill(json({ user: null })),
  );
  routeApi(page, "/health", (route) =>
    route.fulfill(json({ status: "ok" })),
  );
  routeApi(page, "/features**", (route) =>
    route.fulfill(json({})),
  );
  routeApi(page, "/projects**", (route) =>
    route.fulfill(
      json([
        {
          id: 42,
          name: "Test Project",
          git_url: "https://github.com/test/project.git",
          base_branch: "main",
          status: "active",
          local_path: "/tmp/test-project",
          created_at: "2026-04-01T00:00:00Z",
          updated_at: "2026-04-01T00:00:00Z",
        },
        {
          id: 78,
          name: "test-pts",
          git_url: "https://github.com/test/pts.git",
          base_branch: "main",
          status: "active",
          local_path: "/tmp/test-pts",
          created_at: "2026-04-01T00:00:00Z",
          updated_at: "2026-04-01T00:00:00Z",
        },
      ]),
    ),
  );
}

function mockOpsLogsApis(page: import("@playwright/test").Page) {
  mockConsoleBasics(page);

  routeApi(page, "/runs**", (route) => route.fulfill(json([])));
  routeApi(page, "/logs/recent**", (route) =>
    route.fulfill(
      json({
        logs: [
          {
            id: 101,
            timestamp: "2026-04-21T10:00:00.000Z",
            level: "info",
            source: "devgodzilla.api",
            logger_name: "devgodzilla.api",
            module: "api",
            funcName: "load_config",
            lineno: 21,
            message: "Oldest startup log",
            metadata: { request_id: "req-old", status: "booting" },
          },
          {
            id: 102,
            timestamp: "2026-04-21T10:01:00.000Z",
            level: "error",
            source: "devgodzilla.worker",
            logger_name: "devgodzilla.worker",
            module: "worker",
            funcName: "execute_run",
            lineno: 88,
            message: "Mid execution failure",
            metadata: { request_id: "req-mid", error: "boom" },
          },
          {
            id: 103,
            timestamp: "2026-04-21T10:02:00.000Z",
            level: "warning",
            source: "devgodzilla.scheduler",
            logger_name: "devgodzilla.scheduler",
            module: "scheduler",
            funcName: "poll_queue",
            lineno: 144,
            message: "Latest queue warning",
            metadata: { request_id: "req-new", queue: "priority", lag_ms: 820 },
          },
        ],
      }),
    ),
  );
}

function mockOpsEventsApis(page: import("@playwright/test").Page) {
  mockConsoleBasics(page);

  routeApi(page, "/events/recent**", (route) =>
    route.fulfill(
      json({
        events: [
          {
            id: 401,
            protocol_run_id: 77,
            step_run_id: null,
            spec_run_id: null,
            event_type: "planning_started",
            message: "Initial planning event",
            metadata: { run_id: "run-old", status: "starting" },
            event_category: "planning",
            created_at: "2026-04-21T09:58:00.000Z",
            project_id: 42,
            project_name: "Test Project",
            protocol_name: "Legacy Flow",
          },
          {
            id: 402,
            protocol_run_id: 77,
            step_run_id: 12,
            spec_run_id: null,
            event_type: "step_completed",
            message: "Repository scan finished",
            metadata: { step_name: "Scan repo", duration_ms: 1800 },
            event_category: "execution",
            created_at: "2026-04-21T09:59:00.000Z",
            project_id: 42,
            project_name: "Test Project",
            protocol_name: "Legacy Flow",
          },
          {
            id: 403,
            protocol_run_id: 91,
            step_run_id: 19,
            spec_run_id: 301,
            event_type: "qa_failed",
            message: "Latest QA failure surfaced",
            metadata: { error: "Snapshot mismatch", score: 0.42, status: "failed" },
            event_category: "qa",
            created_at: "2026-04-21T10:00:00.000Z",
            project_id: 78,
            project_name: "test-pts",
            protocol_name: "Checkout Refresh",
          },
        ],
      }),
    ),
  );
}

test.describe("Ops activity pages", () => {
  test("logs page shows newest entries first and keeps details expandable", async ({ page }) => {
    mockOpsLogsApis(page);

    await page.goto("/console/ops/logs", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "System Logs" })).toBeVisible();
    await expect(page.getByText("Following latest")).toBeVisible();

    const rows = page.locator("tbody tr").filter({ has: page.locator("button.h-7.w-7") });
    await expect(rows.first()).toContainText("Latest queue warning");
    await expect(rows.nth(1)).toContainText("Mid execution failure");
    await expect(rows.nth(2)).toContainText("Oldest startup log");

    await page.getByRole("combobox").filter({ hasText: "Newest first" }).click();
    await page.getByRole("option", { name: "Oldest first" }).click();
    await expect(rows.first()).toContainText("Oldest startup log");

    await page.getByRole("combobox").filter({ hasText: "Oldest first" }).click();
    await page.getByRole("option", { name: "Newest first" }).click();
    await rows.first().getByRole("button").click();

    await expect(page.locator("pre").filter({ hasText: "Latest queue warning" })).toBeVisible();
    await expect(page.getByRole("definition").filter({ hasText: "poll_queue" })).toBeVisible();
    await expect(page.getByText("request_id")).toBeVisible();
    await expect(page.getByText('"req-new"')).toBeVisible();
  });

  test("events page shows newest entries first and renders inline context", async ({ page }) => {
    mockOpsEventsApis(page);

    await page.goto("/console/ops/events", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
    await expect(page.getByText("Following latest")).toBeVisible();

    const rows = page.locator("tbody tr").filter({ has: page.locator("button.h-7.w-7") });
    await expect(rows.first()).toContainText("Latest QA failure surfaced");
    await expect(rows.first()).toContainText("test-pts");
    await expect(rows.nth(1)).toContainText("Repository scan finished");
    await expect(rows.nth(2)).toContainText("Initial planning event");

    await rows.first().getByRole("button").click();
    await expect(page.getByText('"Snapshot mismatch"')).toBeVisible();
    await expect(page.getByRole("definition").filter({ hasText: "Checkout Refresh" })).toBeVisible();

    await page.getByRole("combobox").filter({ hasText: "Newest first" }).click();
    await page.getByRole("option", { name: "Project" }).click();
    await expect(rows.first()).toContainText("Repository scan finished");
    await expect(rows.nth(1)).toContainText("Initial planning event");
  });
});
