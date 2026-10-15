import { defineConfig, devices } from "@playwright/test";

// Browser E2E smoke suite (#72). Runs only against a local mock-mode stack: the API from
// scripts/e2e_api.sh (isolated test database, test-only token, no webhook) and a production
// build of this app pointed at it. CI runs Chromium; E2E_ALL_BROWSERS=1 adds Firefox and WebKit.
const API_URL = "http://127.0.0.1:8010";
const APP_URL = "http://127.0.0.1:3010";

const browsers = [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }];
if (process.env.E2E_ALL_BROWSERS === "1") {
  browsers.push({ name: "firefox", use: { ...devices["Desktop Firefox"] } }, { name: "webkit", use: { ...devices["Desktop Safari"] } });
}

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: APP_URL, trace: "retain-on-failure" },
  projects: browsers,
  webServer: [
    {
      command: "../scripts/e2e_api.sh",
      url: `${API_URL}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: process.env.CI ? "pipe" : "ignore",
    },
    {
      command: "npx next build && npx next start -H 127.0.0.1 -p 3010",
      url: APP_URL,
      timeout: 240_000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_BASE_URL: API_URL, NEXT_PUBLIC_DEMO_MODE: "false", NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
