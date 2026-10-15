import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, Page, test } from "@playwright/test";

// API-unreachable and network-loss states (#72): the browser blocks every request to the local API,
// so each page must show its own error state instead of a blank or stuck screen.
const API = "http://127.0.0.1:8010/**";
const blockApi = (page: Page) => page.route(API, (route) => route.abort("connectionrefused"));

test.describe("API unreachable from first load", () => {
  test.setTimeout(120_000);

  test("dashboard explains the wait, then reports the server unreachable with a retry", async ({ page }) => {
    await blockApi(page);
    await page.goto("/");
    await expect(page.getByText("Waking the demo server").first()).toBeVisible();
    await expect(page.getByTestId("status-api")).toHaveText("Unreachable", { timeout: 90_000 });
    await expect(page.getByRole("complementary", { name: "Live system status" }).getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("system card shows a load error", async ({ page }) => {
    await blockApi(page);
    await page.goto("/system-card");
    await expect(page.getByText("The system card could not be loaded from the API.")).toBeVisible({ timeout: 90_000 });
  });
});

test.describe("network lost after the page loaded", () => {
  test.setTimeout(120_000);

  test("intake submission reports the service unreachable and keeps the text for a retry", async ({ page }) => {
    await page.goto("/intake");
    await expect(page.getByRole("heading", { name: "Pre-visit symptom intake" })).toBeVisible();
    await blockApi(page);
    await page.getByLabel(/Your symptoms/).fill("I have had a mild headache since this morning.");
    await page.getByRole("checkbox", { name: /I consent/ }).check();
    await page.getByRole("button", { name: "Submit intake" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "couldn't reach the intake service" })).toBeVisible({ timeout: 90_000 });
    await expect(page.getByLabel(/Your symptoms/)).toHaveValue("I have had a mild headache since this morning.");
  });

  test("staff sign-in reports the staff service unreachable", async ({ page }) => {
    const token = readFileSync(join(__dirname, ".auth", "staff-token"), "utf8").trim();
    await page.goto("/staff");
    await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
    await blockApi(page);
    await page.getByLabel("Access token").fill(token);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "couldn't reach the staff service" })).toBeVisible();
  });
});
