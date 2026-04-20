import { test, expect } from "@playwright/test";

test("debug project detail", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(`PAGE ERROR: ${err.message}`));

  // Mock everything
  await page.route("**/api/v1/health**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) })
  );
  await page.route("**/api/v1/projects/42/onboarding**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ project_id: 42, steps: [] }) })
  );
  await page.route("**/api/v1/projects/42/protocols**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42/task-cycle**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ work_items: [] }) })
  );
  await page.route("**/api/v1/projects/42/sprints**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42/agents**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42/specifications**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42/policy**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) })
  );
  await page.route("**/api/v1/projects/42/clarifications**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42/branches**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/projects/42", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 42, name: "Test Project", git_url: "https://github.com/test/project.git",
        local_path: "/home/user/repos/test-project", github_token_configured: true,
        base_branch: "main", project_classification: "web-application",
        status: "active", policy_pack_key: null, policy_pack_version: null,
        policy_overrides: null, policy_repo_local_enabled: null,
        policy_effective_hash: null, policy_enforcement_mode: null,
        constitution_version: null, created_at: "2026-04-01T12:00:00Z",
        updated_at: "2026-04-19T12:00:00Z",
      }),
    })
  );

  await page.goto("http://127.0.0.1:8080/console/projects/42", { waitUntil: "networkidle" });
  
  // Wait a bit for React hydration
  await page.waitForTimeout(3000);
  
  // Log page content
  const h1 = await page.locator("h1").textContent().catch(() => "NO H1");
  console.log("H1 text:", h1);
  console.log("Page URL:", page.url());
  console.log("Console errors:", errors);
  
  // Get full body text
  const body = await page.locator("body").textContent();
  console.log("Body text (first 500):", body?.substring(0, 500));
});
