// Issue #73: read-only screenshots of the hosted demo's public pages.
// No sign-in, no bearer token, no form submission. Selecting a scenario card only fills the text field.
// Any non-GET request other than a CORS preflight fails the run.
// Usage (repository root): node docs/screenshots/capture-hosted-public.mjs <out-dir> <yyyy-mm-dd>
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";
import path from "node:path";

const require = createRequire(new URL("../../app/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const BASE = "https://healthcare-ai-frontend-1s23.onrender.com";
const [outDir, date] = process.argv.slice(2);
if (!outDir || !/^\d{4}-\d{2}-\d{2}$/.test(date ?? "")) {
  console.error("usage: capture-hosted-public.mjs <out-dir> <yyyy-mm-dd>");
  process.exit(2);
}

const views = [
  { name: "dashboard-desktop", url: "/", width: 1280, height: 900, ready: '[data-state="ready"]' },
  { name: "dashboard-mobile", url: "/", width: 390, height: 844, ready: '[data-state="ready"]' },
  { name: "system-card-desktop", url: "/system-card", width: 1280, height: 900, ready: "table" },
  { name: "intake-form-desktop", url: "/intake", width: 1280, height: 900, ready: "text=LLM Mode", selectScenario: "Routine symptoms" },
  { name: "staff-signin-desktop", url: "/staff", width: 1280, height: 900, ready: "text=Staff sign-in" },
];

const requests = [];
const facts = [];
const browser = await chromium.launch();
try {
  for (const v of views) {
    const context = await browser.newContext({
      viewport: { width: v.width, height: v.height },
      deviceScaleFactor: v.width < 768 ? 2 : 1,
      colorScheme: "light",
      locale: "en-US",
      timezoneId: "UTC",
    });
    const page = await context.newPage();
    page.on("request", (r) => requests.push({ view: v.name, method: r.method(), url: r.url().split("?")[0] }));
    await page.goto(BASE + v.url, { waitUntil: "networkidle", timeout: 120_000 });
    await page.locator(v.ready).first().waitFor({ timeout: 120_000 });
    if (v.selectScenario) {
      await page.getByRole("button", { name: new RegExp(v.selectScenario) }).first().click();
      const consent = await page.getByRole("checkbox").first().isChecked();
      facts.push({ view: v.name, scenarioSelected: v.selectScenario, consentChecked: consent });
    }
    await page.waitForTimeout(500);
    const file = path.join(outDir, `${v.name}-${date}.png`);
    await page.screenshot({ path: file, fullPage: false });
    const fullFile = path.join(outDir, `${v.name}-full-${date}.png`);
    await page.screenshot({ path: fullFile, fullPage: true });
    const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, cookies: document.cookie.length }));
    facts.push({ view: v.name, url: v.url, width: v.width, title: await page.title(), storage, capturedAt: new Date().toISOString() });
    await context.close();
  }
} finally {
  await browser.close();
}

const writes = requests.filter((r) => r.method !== "GET" && r.method !== "OPTIONS");
writeFileSync(path.join(outDir, `capture-log-${date}.json`), JSON.stringify({ base: BASE, facts, requests, nonGetRequests: writes }, null, 2));
console.log(JSON.stringify({ facts, requestCount: requests.length, nonGet: writes }, null, 2));
if (writes.length) process.exit(1);
