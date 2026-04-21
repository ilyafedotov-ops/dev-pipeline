import { expect, type Page, type Route,test } from "@playwright/test";

const PROJECT_ID = 9;
const SPEC_RUN_ID = 77;
const APP_BASE_PATH = "/console";
const SPEC_PATH = "specs/001-auth-flow/spec.md";
const PLAN_PATH = "specs/001-auth-flow/plan.md";
const TASKS_PATH = "specs/001-auth-flow/tasks.md";
const IMPLEMENT_PATH = "specs/001-auth-flow/_runtime";
const IMPLEMENT_METADATA_PATH = "specs/001-auth-flow/_runtime/implement-bootstrap.json";

interface MockSpec {
  id: number;
  name: string;
  path: string;
  spec_path: string | null;
  plan_path: string | null;
  tasks_path: string | null;
  checklist_path: string | null;
  analysis_path: string | null;
  implement_path: string | null;
  has_spec: boolean;
  has_plan: boolean;
  has_tasks: boolean;
  status: string;
  spec_run_id: number;
  worktree_path: string;
  branch_name: string;
  base_branch: string;
  spec_number: number;
  feature_name: string;
}

interface MockState {
  initialized: boolean;
  specs: MockSpec[];
  protocols: Array<Record<string, unknown>>;
  requests: {
    createProtocol: Array<Record<string, unknown>>;
    init: Array<Record<string, unknown>>;
    workflow: Array<Record<string, unknown>>;
    specify: Array<Record<string, unknown>>;
    plan: Array<Record<string, unknown>>;
    tasks: Array<Record<string, unknown>>;
    checklist: Array<Record<string, unknown>>;
    analyze: Array<Record<string, unknown>>;
    implement: Array<Record<string, unknown>>;
  };
}

function requestBody(route: Route): Record<string, unknown> {
  const raw = route.request().postData();
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function buildProjectSpec(spec: MockSpec) {
  return {
    id: spec.id,
    spec_run_id: spec.spec_run_id,
    path: spec.path,
    spec_path: spec.spec_path,
    plan_path: spec.plan_path,
    tasks_path: spec.tasks_path,
    checklist_path: spec.checklist_path,
    analysis_path: spec.analysis_path,
    implement_path: spec.implement_path,
    title: spec.feature_name,
    project_id: PROJECT_ID,
    project_name: "Demo Project",
    status: spec.status,
    created_at: "2026-03-08T12:00:00Z",
    worktree_path: spec.worktree_path,
    branch_name: spec.branch_name,
    base_branch: spec.base_branch,
    feature_name: spec.feature_name,
    spec_number: spec.spec_number,
    tasks_generated: spec.has_tasks,
    has_plan: spec.has_plan,
    has_tasks: spec.has_tasks,
    protocol_id: spec.implement_path ? 42 : null,
    sprint_id: spec.implement_path ? 5 : null,
    sprint_name: spec.implement_path ? "Sprint 5" : null,
    linked_tasks: spec.has_tasks ? 3 : 0,
    completed_tasks: 0,
    story_points: spec.has_tasks ? 8 : 0,
  };
}

function appPath(path: string) {
  return `${APP_BASE_PATH}${path}`;
}

async function installApiMocks(page: Page) {
  const state: MockState = {
    initialized: false,
    specs: [],
    protocols: [],
    requests: {
      createProtocol: [],
      init: [],
      workflow: [],
      specify: [],
      plan: [],
      tasks: [],
      checklist: [],
      analyze: [],
      implement: [],
    },
  };

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname, searchParams } = url;

    // Pass through non-API requests
    if (!pathname.startsWith("/api/v1/")) {
      await route.continue();
      return;
    }

    // Strip /api/v1 prefix for matching
    const p = pathname.replace("/api/v1", "");

    // Auth — must mock to prevent React crash
    if (p === "/auth/me") {
      await json(route, { id: 1, email: "test@test.com", name: "Test User" });
      return;
    }

    // Health
    if (p === "/health") {
      await json(route, { status: "ok" });
      return;
    }

    if (request.method() === "GET" && p === `/projects/${PROJECT_ID}`) {
      await json(route, {
        id: PROJECT_ID,
        name: "Demo Project",
        git_url: "https://github.com/example/demo-project",
        local_path: "/tmp/demo-project",
        base_branch: "main",
        project_classification: null,
        created_at: "2026-03-08T12:00:00Z",
        updated_at: "2026-03-08T12:00:00Z",
        policy_pack_key: null,
        policy_pack_version: null,
        policy_overrides: null,
        policy_repo_local_enabled: true,
        policy_effective_hash: null,
        policy_enforcement_mode: null,
        status: "active",
        constitution_version: state.initialized ? "1" : null,
      });
      return;
    }

    if (request.method() === "GET" && p === `/projects/${PROJECT_ID}/onboarding`) {
      await json(route, {
        project_id: PROJECT_ID,
        status: "completed",
        stages: [],
        events: [],
        blocking_clarifications: 0,
      });
      return;
    }

    if (request.method() === "GET" && p === `/projects/${PROJECT_ID}/protocols`) {
      await json(route, state.protocols);
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/protocols`) {
      const body = requestBody(route);
      state.requests.createProtocol.push(body);
      const createdProtocol = {
        id: 142,
        project_id: PROJECT_ID,
        protocol_name: body.protocol_name ?? "auth-flow",
        status: "pending",
        base_branch: body.base_branch ?? "main",
        worktree_path: null,
        protocol_root: null,
        description: body.description ?? null,
        template_config: body.template_config ?? null,
        template_source: body.template_source ?? null,
        summary: null,
        windmill_flow_id: null,
        speckit_metadata: null,
        policy_pack_key: null,
        policy_pack_version: null,
        policy_effective_hash: null,
        policy_effective_json: null,
        linked_sprint_id: null,
        created_at: "2026-03-09T12:00:00Z",
        updated_at: "2026-03-09T12:00:00Z",
      };
      state.protocols = [createdProtocol, ...state.protocols];
      await json(route, createdProtocol);
      return;
    }

    if (request.method() === "GET" && p === `/projects/${PROJECT_ID}/sprints`) {
      await json(route, []);
      return;
    }

    if (request.method() === "GET" && p === `/speckit/status/${PROJECT_ID}`) {
      await json(route, {
        initialized: state.initialized,
        constitution_hash: state.initialized ? "constitution-hash" : null,
        constitution_version: state.initialized ? "1" : null,
        spec_count: state.specs.length,
        specs: state.specs,
      });
      return;
    }

    if (request.method() === "GET" && p === `/speckit/specs/${PROJECT_ID}`) {
      await json(route, state.specs);
      return;
    }

    if (request.method() === "GET" && p === "/specifications" && searchParams.get("project_id") === String(PROJECT_ID)) {
      const specs = state.specs.map(buildProjectSpec);
      await json(route, {
        items: specs,
        total: specs.length,
        filters_applied: { project_id: PROJECT_ID },
      });
      return;
    }

    if (request.method() === "GET" && p === "/specifications/1") {
      await json(route, buildProjectSpec(state.specs[0]));
      return;
    }

    if (request.method() === "GET" && p === "/specifications/1/content") {
      const spec = state.specs[0];
      await json(route, {
        id: spec.id,
        path: spec.path,
        title: spec.feature_name,
        spec_content: spec.spec_path ? "# Spec\n\nAuth flow" : null,
        plan_content: spec.plan_path ? "# Plan\n\nReuse auth tables." : null,
        tasks_content: spec.tasks_path ? "# Tasks\n\n- Build auth flow" : null,
        checklist_content: spec.checklist_path ? "# Checklist\n\n- [x] Review inputs" : null,
        analysis_content: spec.analysis_path
          ? "# Analysis\n\nImplementation review is ready."
          : null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/init`) {
      const body = requestBody(route);
      state.requests.init.push(body);
      state.initialized = true;
      await json(route, {
        success: true,
        path: "/tmp/demo-project/.specify",
        constitution_hash: "constitution-hash",
        error: null,
        warnings: [],
      });
      return;
    }

    if (request.method() === "POST" && p === "/speckit/workflow") {
      const body = requestBody(route);
      state.requests.workflow.push(body);
      state.initialized = true;
      state.specs = [
        {
          id: 1,
          name: "001-auth-flow",
          path: "specs/001-auth-flow",
          spec_path: SPEC_PATH,
          plan_path: PLAN_PATH,
          tasks_path: TASKS_PATH,
          checklist_path: null,
          analysis_path: null,
          implement_path: null,
          has_spec: true,
          has_plan: true,
          has_tasks: true,
          status: "completed",
          spec_run_id: SPEC_RUN_ID,
          worktree_path: "/tmp/demo-project",
          branch_name: "spec/001-auth-flow",
          base_branch: "main",
          spec_number: 1,
          feature_name: "Auth Flow",
        },
      ];
      await json(route, {
        success: true,
        spec_path: SPEC_PATH,
        plan_path: PLAN_PATH,
        tasks_path: TASKS_PATH,
        task_count: 5,
        parallelizable_count: 2,
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        steps: [
          { step: "spec", success: true, path: SPEC_PATH, error: null, skipped: false },
          { step: "plan", success: true, path: PLAN_PATH, error: null, skipped: false },
          { step: "tasks", success: true, path: TASKS_PATH, error: null, skipped: false },
        ],
        stopped_after: null,
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/specify`) {
      const body = requestBody(route);
      state.requests.specify.push(body);
      state.initialized = true;
      state.specs = [
        {
          id: 1,
          name: "001-auth-flow",
          path: "specs/001-auth-flow",
          spec_path: SPEC_PATH,
          plan_path: null,
          tasks_path: null,
          checklist_path: null,
          analysis_path: null,
          implement_path: null,
          has_spec: true,
          has_plan: false,
          has_tasks: false,
          status: "specified",
          spec_run_id: SPEC_RUN_ID,
          worktree_path: "/tmp/demo-project",
          branch_name: "spec/001-auth-flow",
          base_branch: "main",
          spec_number: 1,
          feature_name: "Auth Flow",
        },
      ];
      await json(route, {
        success: true,
        spec_path: SPEC_PATH,
        spec_number: 1,
        feature_name: "Auth Flow",
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        branch_name: "spec/001-auth-flow",
        base_branch: "main",
        spec_root: "specs/001-auth-flow",
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/plan`) {
      const body = requestBody(route);
      state.requests.plan.push(body);
      state.specs = state.specs.map((spec) => ({
        ...spec,
        plan_path: PLAN_PATH,
        has_plan: true,
        status: "planned",
      }));
      await json(route, {
        success: true,
        plan_path: PLAN_PATH,
        data_model_path: "specs/001-auth-flow/data-model.md",
        contracts_path: "specs/001-auth-flow/contracts",
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/tasks`) {
      const body = requestBody(route);
      state.requests.tasks.push(body);
      state.specs = state.specs.map((spec) => ({
        ...spec,
        tasks_path: TASKS_PATH,
        has_tasks: true,
        status: "tasks",
      }));
      await json(route, {
        success: true,
        tasks_path: TASKS_PATH,
        task_count: 3,
        parallelizable_count: 1,
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/checklist`) {
      const body = requestBody(route);
      state.requests.checklist.push(body);
      state.specs = state.specs.map((spec) => ({
        ...spec,
        checklist_path: "specs/001-auth-flow/checklist.md",
      }));
      await json(route, {
        success: true,
        checklist_path: "specs/001-auth-flow/checklist.md",
        item_count: 4,
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/analyze`) {
      const body = requestBody(route);
      state.requests.analyze.push(body);
      state.specs = state.specs.map((spec) => ({
        ...spec,
        analysis_path: "specs/001-auth-flow/analysis.md",
      }));
      await json(route, {
        success: true,
        report_path: "specs/001-auth-flow/analysis.md",
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        error: null,
      });
      return;
    }

    if (request.method() === "POST" && p === `/projects/${PROJECT_ID}/speckit/implement`) {
      const body = requestBody(route);
      state.requests.implement.push(body);
      state.specs = state.specs.map((spec) => ({
        ...spec,
        implement_path: IMPLEMENT_PATH,
        status: "implemented",
      }));
      await json(route, {
        success: true,
        run_path: IMPLEMENT_PATH,
        metadata_path: IMPLEMENT_METADATA_PATH,
        protocol_id: 42,
        protocol_root: IMPLEMENT_PATH,
        step_count: 3,
        sprint_id: 5,
        spec_run_id: SPEC_RUN_ID,
        worktree_path: "/tmp/demo-project",
        error: null,
      });
      return;
    }

    await json(route, {
      error: `Unhandled mock request for ${request.method()} ${p}`,
    }, 500);
  });

  return state;
}

test("drives the deterministic SpecKit happy path", async ({ page }) => {
  test.setTimeout(60_000);
  const state = await installApiMocks(page);

  await page.goto(appPath(`/projects/${PROJECT_ID}?tab=spec`));
  await expect(page.getByRole("button", { name: /initialize speckit/i })).toBeVisible();
  await page.getByRole("button", { name: /initialize speckit/i }).click();
  await expect.poll(() => state.requests.init.length).toBe(1);

  await page.goto(appPath(`/projects/${PROJECT_ID}?wizard=generate-specs&tab=spec`));
  await page.getByLabel(/feature name/i).fill("Auth Flow");
  await page.getByLabel(/^description/i).fill(
    "Build a deterministic authentication onboarding flow for the smoke test."
  );
  await page.getByRole("button", { name: /^Next$/ }).click();
  await page.getByLabel(/functional requirements/i).fill(
    "Users can sign in, sign out, and see an authenticated dashboard."
  );
  await page.getByLabel(/constraints/i).fill("Reuse existing auth tables and routes.");
  await page.getByRole("button", { name: /^Next$/ }).click();
  await page.getByRole("button", { name: /run spec workflow/i }).click();
  await expect.poll(() => state.requests.workflow.length).toBe(1);
  await expect.poll(() => state.specs[0]?.spec_path).toBe(SPEC_PATH);
  await expect.poll(() => state.specs[0]?.plan_path).toBe(PLAN_PATH);
  await expect.poll(() => state.specs[0]?.tasks_path).toBe(TASKS_PATH);
  await expect(page.getByText(/001-auth-flow/i).first()).toBeVisible();

  await page.goto(appPath(`/projects/${PROJECT_ID}?tab=spec`));
  await page.getByRole("button", { name: /^Checklist$/ }).first().click();
  await expect.poll(() => state.requests.checklist.length).toBe(1);
  await expect.poll(() => state.specs[0]?.checklist_path).toBe("specs/001-auth-flow/checklist.md");

  await page.getByRole("button", { name: /^Analyze$/ }).first().click();
  await expect.poll(() => state.requests.analyze.length).toBe(1);
  await expect.poll(() => state.specs[0]?.analysis_path).toBe("specs/001-auth-flow/analysis.md");

  await page.getByRole("button", { name: /^Implement$/ }).first().click();
  await expect.poll(() => state.requests.implement.length).toBe(1);
  // Wait for React Query to settle after implement mutation
  await page.waitForTimeout(1000);

  await page.getByRole("link", { name: /review implementation/i }).first().click({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/console\/specifications\/1\?tab=analysis$/);
  await expect(page.getByText(/implementation review is ready\./i)).toBeVisible();
  await expect(page.getByRole("link", { name: /view protocol/i })).toHaveAttribute(
    "href",
    "/console/protocols/42"
  );
  await expect(page.getByRole("link", { name: /open execution/i })).toHaveAttribute(
    "href",
    "/console/projects/9?tab=execution&sprint=5"
  );

  expect(state.requests.init[0]).toEqual({});
  expect(state.requests.workflow[0]).toMatchObject({
    feature_name: "Auth Flow",
  });
  expect(state.requests.checklist[0]).toMatchObject({
    spec_path: SPEC_PATH,
  });
  expect(state.requests.analyze[0]).toMatchObject({
    spec_path: SPEC_PATH,
  });
  expect(state.requests.implement[0]).toMatchObject({
    spec_path: SPEC_PATH,
  });
});

test("submits canonical protocol create payloads from the browser", async ({ page }) => {
  const state = await installApiMocks(page);

  await page.goto(appPath(`/projects/${PROJECT_ID}/protocols`));
  await page.getByRole("button", { name: /create protocol/i }).first().click();
  await page.getByLabel(/protocol name/i).fill("auth-flow");
  await page.getByLabel(/description/i).fill("Implement authentication flow");
  await page.getByLabel(/base branch/i).fill("develop");
  await page.getByLabel(/template source/i).fill("./templates/auth.yaml");
  await page
    .getByLabel(/template config/i)
    .fill('{ "mode": "brownfield", "owner": "protocol" }');
  await page.getByRole("button", { name: /create protocol/i }).last().click();

  await expect.poll(() => state.requests.createProtocol.length).toBe(1);
  expect(state.requests.createProtocol[0]).toEqual({
    protocol_name: "auth-flow",
    description: "Implement authentication flow",
    base_branch: "develop",
    template_source: "./templates/auth.yaml",
    template_config: {
      mode: "brownfield",
      owner: "protocol",
    },
  });
  await expect(page.getByRole("link", { name: "auth-flow" })).toBeVisible();
});
