/**
 * Playwright test helpers — comprehensive API mocking for DevGodzilla console.
 *
 * CRITICAL: ALL Playwright tests MUST mock /api/v1/auth/** to avoid React crash on 401.
 * Use mockAllProjectApis() for project detail pages — it covers all sub-resources.
 */

import { expect, Page, Route } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8080";

// ─── Legacy constants for navigation tests ────────────────────────────────

export const APP_BASE = "/console";

export const PAGE_HEADINGS: Record<string, string> = {
  "/": "Dashboard",
  "/projects": "Projects",
  "/protocols": "Protocols",
  "/runs": "Runs Explorer",
  "/settings": "Settings",
};

export const SIDEBAR_NAV_ITEMS = [
  { name: "Dashboard", href: "/" },
  { name: "Projects", href: "/projects" },
  { name: "Protocols", href: "/protocols" },
  { name: "Settings", href: "/settings" },
];

export const selectors = {
  sidebar: 'aside[data-sidebar="true"]',
  breadcrumbs: 'nav[aria-label="Breadcrumb"], [data-testid="breadcrumbs"]',
};

// ─── Empty state helpers ──────────────────────────────────────────────────

export const mockEmptyState = (page: Page) => {
  mockAuth(page);
  page.route("**/api/v1/projects**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  page.route("**/api/v1/protocols**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  page.route("**/api/v1/runs**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
};

export async function mockCreateProject(page: Page) {
  const fakeProject = {
    id: 99,
    name: "Test Project",
    git_url: "https://github.com/example/test-project",
    base_branch: "main",
    status: "active",
    local_path: "/repos/test-project",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  await page.route("**/api/v1/projects**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([fakeProject]) }),
  );
  return fakeProject;
}

// ─── Navigation ───────────────────────────────────────────────────────────

export async function goto(page: Page, path: string = "/") {
  // basePath is "/console" — all frontend routes need this prefix
  const fullPath = path.startsWith("/console") ? path : `/console${path}`;
  await page.goto(`${BASE_URL}${fullPath}`, { waitUntil: "domcontentloaded" });
}

// ─── Health ───────────────────────────────────────────────────────────────

export async function mockHealthOk(page: Page) {
  page.route("**/api/v1/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    }),
  );
}

// ─── Auth (MUST be mocked — 401 causes React crash) ──────────────────────

export function mockAuth(page: Page) {
  page.route("**/api/v1/auth/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user: null }),
    }),
  );
}

// ─── Project List ─────────────────────────────────────────────────────────

export const EMPTY_PROJECTS: any[] = [];

export function mockProjectsList(page: Page, projects: any[] = EMPTY_PROJECTS) {
  page.route("**/api/v1/projects$", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(projects),
    }),
  );
}

// ─── Full Project Detail Mocks (covers all sub-resources) ──────────────────

export const MOCK_PROJECT = {
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

export const MOCK_ONBOARDING = {
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

export const MOCK_PROTOCOLS = [
  { id: 1, protocol_name: "auth-flow", project_id: 42, status: "running", base_branch: "main", created_at: "2026-04-10T12:00:00Z", updated_at: "2026-04-19T12:00:00Z" },
  { id: 2, protocol_name: "payment-integration", project_id: 42, status: "completed", base_branch: "main", created_at: "2026-04-05T12:00:00Z", updated_at: "2026-04-15T12:00:00Z" },
];

export const MOCK_TASK_CYCLE = [
  { id: 101, step_run_id: 1, status: "in_progress", review_status: "pending", qa_status: "pending", title: "Implement login page", description: "Create the login UI component" },
  { id: 102, step_run_id: 2, status: "done", review_status: "approved", qa_status: "passed", title: "Setup auth middleware", description: "Configure authentication middleware" },
];

export const MOCK_SPRINTS = [
  { id: 1, name: "Sprint 1 - Auth", status: "active", project_id: 42, start_date: "2026-04-01", end_date: "2026-04-14", tasks: [
    { id: 1, title: "Login page", status: "done" },
    { id: 2, title: "Auth API", status: "in_progress" },
    { id: 3, title: "User model", status: "todo" },
  ]},
];

/**
 * Mock ALL API endpoints needed for the project detail page.
 * Without this, unmocked endpoints (commits, pulls, speckit, etc.) return 404
 * and cause React crash ("Application error").
 *
 * @param page Playwright page
 * @param projectId Project ID to mock (default: 42)
 * @param overrides Optional partial overrides for mock data
 */
export function mockAllProjectApis(page: Page, projectId: number = 42, overrides?: {
  project?: any;
  onboarding?: any;
  protocols?: any[];
  taskCycle?: any;
  sprints?: any[];
}) {
  const p = `/api/v1/projects/${projectId}`;

  const project = { ...MOCK_PROJECT, id: projectId, ...(overrides?.project ?? {}) };
  const onboarding = overrides?.onboarding ?? MOCK_ONBOARDING;
  const protocols = overrides?.protocols ?? MOCK_PROTOCOLS;
  const taskCycle = overrides?.taskCycle ?? MOCK_TASK_CYCLE;
  const sprints = overrides?.sprints ?? MOCK_SPRINTS;

  // Helper for JSON responses
  const json = (data: any) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(data),
  });

  // Sub-resource routes (specific first, then generic)
  page.route(new RegExp(`${p}/onboarding/?`), (r) => r.fulfill(json(onboarding)));
  page.route(new RegExp(`${p}/protocols/?`), (r) => r.fulfill(json(protocols)));
  page.route(new RegExp(`${p}/task-cycle/?`), (r) => r.fulfill(json(taskCycle)));
  page.route(new RegExp(`${p}/sprints/?`), (r) => r.fulfill(json(sprints)));
  page.route(new RegExp(`${p}/agents/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/specifications/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/policy/?`), (r) => r.fulfill(json({})));
  page.route(new RegExp(`${p}/policy/findings/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/clarifications/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/branches/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/workflow/?`), (r) => r.fulfill(json({ nodes: [], edges: [] })));
  // GitHub integrations — these return 404 without mocks and crash React
  page.route(new RegExp(`${p}/commits/?`), (r) => r.fulfill(json([])));
  page.route(new RegExp(`${p}/pulls/?`), (r) => r.fulfill(json([])));

  // SpecKit endpoints (also cause 404 crash)
  page.route(new RegExp(`/api/v1/speckit/status/${projectId}`), (r) => r.fulfill(json({ status: "not_started" })));
  page.route(new RegExp(`/api/v1/speckit/specs/${projectId}`), (r) => r.fulfill(json([])));

  // Project detail — exact match (must be last to not override sub-routes)
  page.route(new RegExp(`${p}$`), (r) => r.fulfill(json(project)));
}

/**
 * Set up all mocks needed for a typical console page test.
 * Includes: health, auth, projects list, and optional project detail.
 */
export function mockConsoleBasics(page: Page) {
  mockHealthOk(page);
  mockAuth(page);
  mockProjectsList(page, [
    { ...MOCK_PROJECT },
    { id: 78, name: "test-pts", git_url: "https://g.c/r2", base_branch: "main", status: "active", local_path: "/tmp/t", created_at: "2026-04-01T00:00:00Z", updated_at: "2026-04-01T00:00:00Z" },
  ]);
}

/** Mock the protocols list endpoint — /api/v1/protocols */
export function mockProtocols(page: Page, protocols: any[] = []) {
  mockAuth(page);
  page.route("**/api/v1/protocols**", (route) => {
    // Single protocol detail request
    const url = route.request().url();
    const match = url.match(/\/protocols\/(\d+)/);
    if (match) {
      const id = parseInt(match[1]);
      const proto = protocols.find((p) => p.id === id);
      return route.fulfill({
        status: proto ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(proto || { detail: "Not found" }),
      });
    }
    // List request
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(protocols),
    });
  });
}
