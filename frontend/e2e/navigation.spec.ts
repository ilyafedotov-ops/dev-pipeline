import { expect, test } from "@playwright/test";

import { APP_BASE, PAGE_HEADINGS, SIDEBAR_NAV_ITEMS, goto, selectors } from "./helpers";

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await goto(page);
  });

  test("Dashboard loads on /console", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Dashboard");
    await expect(page).toHaveURL(new RegExp(`${APP_BASE}/?$`));
  });

  for (const item of SIDEBAR_NAV_ITEMS) {
    if (item.href === "/") continue; // already tested above

    test(`Sidebar → ${item.name} page loads with correct heading`, async ({ page }) => {
      // Click the nav link in the sidebar
      const sidebar = page.locator(selectors.sidebar);
      await sidebar.waitFor({ state: "visible" });

      // Find and click the link by name
      const navLink = sidebar.locator(`a:has-text("${item.name}")`).first();
      await navLink.click();

      // Verify the page heading
      const expectedHeading = PAGE_HEADINGS[item.href] ?? item.name;
      await expect(page.locator("h1")).toContainText(expectedHeading, { timeout: 10_000 });

      // Verify the URL
      await expect(page).toHaveURL(new RegExp(`${APP_BASE}${item.href}`));
    });
  }

  test("Breadcrumbs update on navigation", async ({ page }) => {
    // Starting at Dashboard – breadcrumbs may be empty for root
    // Navigate to Projects via sidebar
    const sidebar = page.locator(selectors.sidebar);
    await sidebar.locator('a:has-text("Projects")').first().click();

    // Breadcrumbs should now contain "Projects"
    const breadcrumbNav = page.locator(selectors.breadcrumbs);
    await expect(breadcrumbNav).toContainText("Projects");
  });

  test("Browser back/forward navigation works", async ({ page }) => {
    const sidebar = page.locator(selectors.sidebar);
    await sidebar.waitFor({ state: "visible" });

    // Navigate: Dashboard → Projects
    await sidebar.locator('a:has-text("Projects")').first().click();
    await expect(page.locator("h1")).toContainText("Projects");
    const projectsUrl = page.url();

    // Navigate: Projects → Settings
    await sidebar.locator('a:has-text("Settings")').first().click();
    await expect(page.locator("h1")).toContainText("Settings");

    // Go back → should land on Projects
    await page.goBack();
    await expect(page.locator("h1")).toContainText("Projects", { timeout: 10_000 });
    await expect(page).toHaveURL(projectsUrl);

    // Go forward → should land on Settings
    await page.goForward();
    await expect(page.locator("h1")).toContainText("Settings", { timeout: 10_000 });
  });
});
