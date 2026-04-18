import { type Page, type Route } from "@playwright/test";

// ── Common constants ──────────────────────────────────────────────────

/** Base path for the Next.js app (basePath in next.config) */
export const APP_BASE = "/console";

/** All top-level sidebar nav items we want to exercise */
export const SIDEBAR_NAV_ITEMS = [
  { name: "Dashboard", href: "/" },
  { name: "Projects", href: "/projects" },
  { name: "Runs", href: "/runs" },
  { name: "Protocols", href: "/protocols" },
  { name: "Settings", href: "/settings" },
] as const;

/** Headings expected on each page (keyed by href) */
export const PAGE_HEADINGS: Record<string, string> = {
  "/": "Dashboard",
  "/projects": "Projects",
  "/runs": "Runs",
  "/protocols": "Protocols",
  "/settings": "Settings",
};

// ── Selectors ─────────────────────────────────────────────────────────

export const selectors = {
  sidebar: "[data-sidebar]",
  breadcrumbs: "[data-breadcrumbs]",
  h1: "h1",
  newProjectButton: "button:has-text('New Project')",
  createProjectButton: "button:has-text('Create Project')",
  emptyState: "[data-empty-state], .text-muted-foreground:has-text('No projects yet')",
} as const;

// ── API intercept helpers ─────────────────────────────────────────────

/** Mock the health endpoint to always return OK. */
export async function mockHealthOk(page: Page) {
  await page.route("**/api/v1/health**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", version: "0.1.0", service: "devgodzilla" }),
    }),
  );
}

/** Mock the projects list endpoint. */
export async function mockProjects(
  page: Page,
  projects: Array<Record<string, unknown>> = [],
) {
  await page.route("**/api/v1/projects**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(projects),
    }),
  );
}

/** Mock the protocols list endpoint. */
export async function mockProtocols(
  page: Page,
  protocols: Array<Record<string, unknown>> = [],
) {
  await page.route("**/api/v1/protocols**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(protocols),
    }),
  );
}

/** Mock the runs list endpoint. */
export async function mockRuns(
  page: Page,
  runs: Array<Record<string, unknown>> = [],
) {
  await page.route("**/api/v1/runs**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(runs),
    }),
  );
}

/**
 * Intercept a create-project POST and return a fake project.
 * Returns a promise that resolves with the request body so the caller can
 * assert the payload.
 */
export async function mockCreateProject(
  page: Page,
  response?: Record<string, unknown>,
) {
  const fakeProject = response ?? {
    id: 1,
    name: "Test Project",
    git_url: "https://github.com/example/test",
    base_branch: "main",
    status: "active",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  await page.route("**/api/v1/projects**", async (route: Route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(fakeProject),
      });
    } else {
      // GET – return empty list (no projects)
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    }
  });

  return fakeProject;
}

/**
 * Setup all common mocks for an "empty" state:
 * no projects, no protocols, no runs, health OK.
 */
export async function mockEmptyState(page: Page) {
  await Promise.all([
    mockHealthOk(page),
    mockProjects(page),
    mockProtocols(page),
    mockRuns(page),
  ]);
}

// ── Navigation helpers ────────────────────────────────────────────────

/** Navigate to a path relative to APP_BASE (no leading slash needed). */
export async function goto(page: Page, path: string = "/") {
  const fullPath = `${APP_BASE}${path === "/" ? "" : path}`;
  return page.goto(fullPath, { waitUntil: "domcontentloaded" });
}
