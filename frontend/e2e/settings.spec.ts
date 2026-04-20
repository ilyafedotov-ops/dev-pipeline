import { expect, test } from "@playwright/test";

import { goto, mockHealthOk } from "./helpers";

test.describe("Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    await mockHealthOk(page);
  });

  test("Shows API configuration form", async ({ page }) => {
    await goto(page, "/settings");

    // Page should have Settings heading
    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // API Configuration card should be visible
    await expect(page.getByText("API Configuration")).toBeVisible({ timeout: 10_000 });

    // API Base URL input
    const apiBaseInput = page.locator("#apiBase");
    await expect(apiBaseInput).toBeVisible();

    // API Token input
    const tokenInput = page.locator("#token");
    await expect(tokenInput).toBeVisible();

    // Save button
    await expect(page.getByRole("button", { name: /save configuration/i })).toBeVisible();
  });

  test("Shows connection status (Connected when health is OK)", async ({ page }) => {
    // Health is already mocked to return OK via mockHealthOk
    await goto(page, "/settings");

    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // Connection Status card title should be visible (use exact match to avoid strict mode)
    await expect(page.getByText("Connection Status", { exact: true })).toBeVisible({ timeout: 10_000 });

    // Connected status — use a more specific locator to avoid matching the header badge
    await expect(page.getByLabel("General").getByText("Connected")).toBeVisible({ timeout: 10_000 });
  });

  test("Shows dark mode toggle", async ({ page }) => {
    await goto(page, "/settings");

    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // Display Preferences section
    await expect(page.getByText("Display Preferences")).toBeVisible({ timeout: 10_000 });

    // Dark Mode toggle
    await expect(page.getByText("Dark Mode")).toBeVisible();
  });

  test("Shows language selector", async ({ page }) => {
    await goto(page, "/settings");

    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // Language label should be visible
    await expect(page.getByText("Language")).toBeVisible({ timeout: 10_000 });
  });

  test("Test Connection button triggers health check", async ({ page }) => {
    let healthCheckCount = 0;
    // Override the health mock to track calls
    await page.route("**/api/v1/health**", (route) => {
      healthCheckCount++;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", version: "0.1.0", service: "devgodzilla" }),
      });
    });

    await goto(page, "/settings");

    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });

    // Find and click Test Connection button
    const testButton = page.getByRole("button", { name: /test connection/i });
    await expect(testButton).toBeVisible({ timeout: 10_000 });

    const countBefore = healthCheckCount;
    await testButton.click();

    // Wait for the health check to fire
    await expect
      .poll(() => healthCheckCount, { timeout: 5_000 })
      .toBeGreaterThan(countBefore);

    // Should show Connected status after successful health check — use specific locator
    await expect(page.getByLabel("General").getByText("Connected")).toBeVisible({ timeout: 5_000 });
  });
});
