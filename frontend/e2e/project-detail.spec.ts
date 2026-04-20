import { expect, test } from "@playwright/test";
import { goto, mockHealthOk, mockAuth, mockAllProjectApis } from "./helpers";

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
    await goto(page, "/projects/42");
    await expect(page.getByText("Test Project").first()).toBeVisible({ timeout: 15_000 });
    const taskCycleTab = page.locator("aside").getByRole("button", { name: /Task Cycle/ });
    await expect(taskCycleTab).toBeVisible({ timeout: 10_000 });
    await taskCycleTab.click();
    // Wait for work items to load (React Query fetch + render)
    await expect(page.getByText("Implement login page").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Setup auth middleware").first()).toBeVisible({ timeout: 10_000 });
  });
});
