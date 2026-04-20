import { expect, test } from "@playwright/test";

import { goto, mockHealthOk, mockProtocols } from "./helpers";

test.describe("Protocols Page", () => {
  test.beforeEach(async ({ page }) => {
    await mockHealthOk(page);
  });

  test("Shows empty state when no protocols exist", async ({ page }) => {
    await mockProtocols(page, []);
    await goto(page, "/protocols");

    await expect(page.locator("h1")).toContainText("Protocols", { timeout: 10_000 });
    // Should show some kind of empty indicator
    await expect(
      page.getByText(/no protocols/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("Displays protocol list with correct status badges", async ({ page }) => {
    const protocols = [
      {
        id: 1,
        protocol_name: "auth-flow",
        project_id: 10,
        status: "running",
        base_branch: "main",
        created_at: "2026-04-01T12:00:00Z",
        updated_at: "2026-04-19T12:00:00Z",
      },
      {
        id: 2,
        protocol_name: "payment-integration",
        project_id: 11,
        status: "completed",
        base_branch: "develop",
        created_at: "2026-04-02T12:00:00Z",
        updated_at: "2026-04-18T12:00:00Z",
      },
      {
        id: 3,
        protocol_name: "user-profile",
        project_id: 10,
        status: "failed",
        base_branch: "main",
        created_at: "2026-04-03T12:00:00Z",
        updated_at: "2026-04-17T12:00:00Z",
      },
      {
        id: 4,
        protocol_name: "notification-system",
        project_id: 12,
        status: "blocked",
        base_branch: "main",
        created_at: "2026-04-04T12:00:00Z",
        updated_at: "2026-04-16T12:00:00Z",
      },
      {
        id: 5,
        protocol_name: "search-feature",
        project_id: 10,
        status: "paused",
        base_branch: "feature/search",
        created_at: "2026-04-05T12:00:00Z",
        updated_at: "2026-04-15T12:00:00Z",
      },
      {
        id: 6,
        protocol_name: "api-refactor",
        project_id: 13,
        status: "pending",
        base_branch: "main",
        created_at: "2026-04-06T12:00:00Z",
        updated_at: "2026-04-14T12:00:00Z",
      },
    ];
    await mockProtocols(page, protocols);
    await goto(page, "/protocols");

    await expect(page.locator("h1")).toContainText("Protocols", { timeout: 10_000 });

    // Verify protocol names appear
    await expect(page.getByText("auth-flow")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("payment-integration")).toBeVisible();
    await expect(page.getByText("user-profile")).toBeVisible();
    await expect(page.getByText("notification-system")).toBeVisible();

    // Verify status badges are rendered (StatusPill component)
    await expect(page.locator("text=Running").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Completed").first()).toBeVisible();
    await expect(page.locator("text=Failed").first()).toBeVisible();
    await expect(page.locator("text=Blocked").first()).toBeVisible();
    await expect(page.locator("text=Paused").first()).toBeVisible();
    await expect(page.locator("text=Pending").first()).toBeVisible();
  });

  test("Click on protocol navigates to protocol detail page", async ({ page }) => {
    const protocols = [
      {
        id: 22,
        protocol_name: "clickable-protocol",
        project_id: 10,
        status: "running",
        base_branch: "main",
        created_at: "2026-04-01T12:00:00Z",
        updated_at: "2026-04-19T12:00:00Z",
      },
    ];
    await mockProtocols(page, protocols);

    // Mock the detail endpoint too — the wildcard in mockProtocols also matches /protocols/22
    // but we need to make sure the detail route returns a single object (not array)
    await page.route("**/api/v1/protocols/22/steps**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      }),
    );

    await goto(page, "/protocols");
    await expect(page.getByText("clickable-protocol")).toBeVisible({ timeout: 10_000 });

    // Click the protocol link
    await page.getByText("clickable-protocol").click();

    // Should navigate to the protocol detail page
    await expect(page).toHaveURL(/\/console\/protocols\/22/, { timeout: 10_000 });
  });

  test("Status filter dropdown works", async ({ page }) => {
    const protocols = [
      {
        id: 1,
        protocol_name: "running-protocol",
        project_id: 10,
        status: "running",
        base_branch: "main",
        created_at: "2026-04-01T12:00:00Z",
        updated_at: "2026-04-19T12:00:00Z",
      },
      {
        id: 2,
        protocol_name: "completed-protocol",
        project_id: 11,
        status: "completed",
        base_branch: "main",
        created_at: "2026-04-02T12:00:00Z",
        updated_at: "2026-04-18T12:00:00Z",
      },
    ];
    await mockProtocols(page, protocols);
    await goto(page, "/protocols");

    await expect(page.getByText("running-protocol")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("completed-protocol")).toBeVisible();

    // Open the status filter dropdown
    // The protocols page has a Select trigger for status filter
    const statusFilterTrigger = page.locator('button[class*="SelectTrigger"], button:has(> span)').filter({ hasText: /all|status/i }).first();
    
    // Try clicking the select trigger
    try {
      await statusFilterTrigger.click({ timeout: 3000 });
    } catch {
      // If the generic trigger fails, try by looking for the actual select component
      const selectTrigger = page.locator('[data-slot="select-trigger"]').first();
      await selectTrigger.click({ timeout: 5000 });
    }

    // Select "Completed" option from the dropdown
    await page.getByRole("option", { name: /completed/i }).click({ timeout: 5000 }).catch(async () => {
      await page.locator('[data-slot="select-item"]').filter({ hasText: /completed/i }).click({ timeout: 5000 });
    });

    // After filtering, only completed protocol should be visible
    await expect(page.getByText("completed-protocol")).toBeVisible();
    await expect(page.getByText("running-protocol")).not.toBeVisible({ timeout: 5_000 });
  });

  test("Search box filters protocols", async ({ page }) => {
    const protocols = [
      {
        id: 1,
        protocol_name: "auth-login-flow",
        project_id: 10,
        status: "running",
        base_branch: "main",
        created_at: "2026-04-01T12:00:00Z",
        updated_at: "2026-04-19T12:00:00Z",
      },
      {
        id: 2,
        protocol_name: "payment-gateway",
        project_id: 11,
        status: "completed",
        base_branch: "main",
        created_at: "2026-04-02T12:00:00Z",
        updated_at: "2026-04-18T12:00:00Z",
      },
      {
        id: 100,
        protocol_name: "legacy-api",
        project_id: 12,
        status: "failed",
        base_branch: "main",
        created_at: "2026-04-03T12:00:00Z",
        updated_at: "2026-04-17T12:00:00Z",
      },
    ];
    await mockProtocols(page, protocols);
    await goto(page, "/protocols");

    await expect(page.getByText("auth-login-flow")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("payment-gateway")).toBeVisible();

    // Find and use the search input
    const searchInput = page.locator('input[placeholder*="Search" i], input[placeholder*="search" i], input[placeholder*="filter" i]').first();
    await searchInput.fill("payment");

    // Only matching protocol should be visible
    await expect(page.getByText("payment-gateway")).toBeVisible();
    await expect(page.getByText("auth-login-flow")).not.toBeVisible({ timeout: 5_000 });

    // Clear and search by different term
    await searchInput.clear();
    await searchInput.fill("auth");

    await expect(page.getByText("auth-login-flow")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("payment-gateway")).not.toBeVisible();
  });
});
