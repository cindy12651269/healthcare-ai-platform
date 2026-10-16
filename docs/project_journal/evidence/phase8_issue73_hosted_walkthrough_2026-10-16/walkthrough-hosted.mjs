// Issue #73 merge-date hosted walkthrough: read-only checks of the public pages.
// No sign-in, no token, no form submission, no click that sends data. Any non-GET request
// other than a CORS preflight fails the run.
// Usage (repository root): node <this file> <output-dir>
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const require = createRequire(new URL("../../../../app/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const FE = "https://healthcare-ai-frontend-1s23.onrender.com";
const API = "https://healthcare-ai-api-tovn.onrender.com";
const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: walkthrough-hosted.mjs <output-dir>");
  process.exit(2);
}

const requests = [];
const results = [];
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "light", locale: "en-US", timezoneId: "UTC" });
const page = await context.newPage();
page.on("request", (r) => requests.push({ method: r.method(), url: r.url().split("?")[0] }));
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push({ url: page.url(), text: m.text().slice(0, 200) }); });

async function visit(name, url, check) {
  const started = new Date().toISOString();
  const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 120_000 });
  const facts = await check();
  await page.screenshot({ path: path.join(outDir, `${name}-1280-light.jpg`), type: "jpeg", quality: 80 });
  const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, cookies: document.cookie.length }));
  results.push({ name, url, started, finished: new Date().toISOString(), http: resp?.status(), title: await page.title(), lang: await page.getAttribute("html", "lang"), h1: await page.locator("h1").allInnerTexts(), storage, ...facts });
}

const text = (sel) => page.locator(sel).first().innerText();

try {
  await visit("dashboard", FE + "/", async () => {
    await page.locator('[data-state="ready"]').first().waitFor({ timeout: 120_000 });
    const status = await page.locator('[data-state="ready"]').first().innerText();
    return {
      indicator: await page.getByText("Demo · synthetic data · mock mode").count(),
      liveStatus: status.replace(/\s+/g, " ").slice(0, 300),
      ctas: await page.getByRole("link", { name: /Try Patient Intake|Explore Staff Workflow/ }).allInnerTexts(),
    };
  });

  await visit("intake", FE + "/intake", async () => {
    await page.getByText("LLM Mode").first().waitFor({ timeout: 120_000 });
    const scenarios = [];
    for (const name of ["Routine symptoms", "Emergency language", "Prescription request", "Vague / low confidence"]) {
      const card = page.getByRole("button", { name: new RegExp(name.replace("/", "\\/")) }).first();
      scenarios.push({ name, present: (await card.count()) === 1, text: (await card.innerText()).replace(/\s+/g, " ").slice(0, 260) });
    }
    return {
      llmModeBadge: (await text("text=LLM Mode")).trim(),
      scenarios,
      consentChecked: await page.getByRole("checkbox").first().isChecked(),
      submitButtons: await page.getByRole("button", { name: "Submit intake" }).count(),
    };
  });

  await visit("system-card", FE + "/system-card", async () => {
    await page.locator("table").first().waitFor({ timeout: 120_000 });
    const body = await page.locator("main").innerText();
    return {
      notMedicalDevice: body.includes("Not a medical device"),
      mentionsMock: /mock/i.test(body),
      executionModeLine: (body.match(/[^\n]*[Ee]xecution mode[^\n]*\n?[^\n]*/) || [""])[0].replace(/\s+/g, " ").slice(0, 160),
      safetyTotalRow: (body.match(/Total[^\n]*(\n[^\n]*){0,4}/) || [""])[0].replace(/\s+/g, " ").slice(0, 200),
      extractionLine: (body.match(/6 cases[^\n]*/) || [""])[0].slice(0, 200),
    };
  });

  await visit("staff-signin", FE + "/staff", async () => {
    await page.getByText("Staff sign-in").first().waitFor({ timeout: 60_000 });
    return {
      policyCard: await page.getByText("Visiting the public demo?").count(),
      tokenField: await page.getByLabel("Access token").count(),
      tokenFieldEmpty: (await page.getByLabel("Access token").inputValue()) === "",
      signInButton: await page.getByRole("button", { name: "Sign in" }).count(),
      // Signed out: the queue's status tabs (e.g. "Needs review, 3 intakes") must not render.
      queueStatusTabs: await page.getByRole("button", { name: /^(Needs review|Reviewed|Escalated|Submitted|All), \d+ intakes?$/ }).count(),
      signOutButton: await page.getByRole("button", { name: "Sign out" }).count(),
    };
  });

  await visit("not-found", FE + "/does-not-exist-e73", async () => ({
    pageNotFoundText: await page.getByText("Page not found").count(),
    insideAppShell: await page.getByText("Demo · synthetic data · mock mode").count(),
  }));
} finally {
  await browser.close();
}

// Compare the hosted system-card evaluation with the committed snapshot (read-only GET).
const hosted = await (await fetch(API + "/api/system-card")).json();
const committed = JSON.parse(readFileSync(new URL("../../../../evaluation/system_card_results.json", import.meta.url)));
const evaluationDeepEqual = JSON.stringify(sortKeys(hosted.evaluation)) === JSON.stringify(sortKeys(committed));
function sortKeys(v) {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === "object") return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])]));
  return v;
}

const nonGet = requests.filter((r) => r.method !== "GET" && r.method !== "OPTIONS");
const apiRequests = requests.filter((r) => r.url.startsWith(API)).map((r) => `${r.method} ${r.url.replace(API, "")}`);
const out = { frontend: FE, api: API, results, consoleErrors, evaluationDeepEqual, executionMode: hosted.execution_mode ?? hosted.mode ?? null, requestCount: requests.length, apiRequests, nonGetRequests: nonGet };
writeFileSync(path.join(outDir, "walkthrough-results.json"), JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
if (nonGet.length) process.exit(1);
