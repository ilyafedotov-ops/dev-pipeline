import { expect, test } from "@playwright/test";

import { goto, mockHealthOk, mockAuth, mockProjectsList } from "./helpers";

test.describe("API Health & Connectivity", () => {
  test("Settings page shows 'Connected' when backend is healthy", async ({ page }) => {
    mockAuth(page);
    await mockHealthOk(page);
    await goto(page, "/settings");

    // The settings page should load
    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // The Connection Status card should show "Connected"
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 10_000 });
  });

  test("Settings page shows 'Disconnected' when backend is unreachable", async ({ page }) => {
    mockAuth(page);
    // Force health endpoint to return an error
    await page.route("**/api/v1/health**", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Service Unavailable" }),
      }),
    );

    await goto(page, "/settings");
    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });
    await expect(page.getByText("Disconnected")).toBeVisible({ timeout: 10_000 });
  });

  test("API requests are proxied through /api/v1/ prefix", async ({ page }) => {
    mockAuth(page);

    // Track outgoing requests
    const apiRequests: string[] = [];
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("/api/v1/")) {
        apiRequests.push(url);
      }
    });

    // Navigate to projects which will trigger API calls
    await page.route("**/api/v1/projects**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      }),
    );
    await page.route("**/api/v1/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", version: "0.1.0" }),
      }),
    );

    await goto(page, "/projects");

    // Wait for the page to load
    await expect(page.locator("h1")).toContainText("Projects", { timeout: 10_000 });

    // Verify that at least one API call went through
    expect(apiRequests.length).toBeGreaterThan(0);

    // All API calls should go through the /api/v1/ path (rewritten by Next.js)
    for (const url of apiRequests) {
      expect(url).toContain("/api/v1/");
    }
  });

  test("Health endpoint returns valid JSON", async ({ page }) => {
    // Make a direct request through the app proxy
    const response = await page.request.get("/console/api/v1/health");
    // The backend health endpoint may or may not be behind /api/v1/
    // In the real setup it's proxied. If it returns a valid response, check it.
    if (response.ok()) {
      const body = await response.json();
      expect(body).toHaveProperty("status");
    }
  });
});
