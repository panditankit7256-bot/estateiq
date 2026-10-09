import { test, expect } from "@playwright/test";

test("admin can sign in, see the command centre and switch facility", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Site plan")).toBeVisible({ timeout: 45000 });
  await page.getByLabel("Facility").selectOption("government_hospital");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Hospital", { timeout: 45000 });
});

test("operations role does not see the energy page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Operations team: ops/ }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("link", { name: "Energy" })).toHaveCount(0, { timeout: 45000 });
});
