// #71 staff workspace: headless Chrome over the DevTools Protocol (no dependencies), against a production
// build pointed at fixtures-server.mjs. Sign-in uses the placeholder "synthetic-fixture-not-a-token"
// (the fixture server accepts any bearer string); no real token is generated or used.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
const OUT = process.argv[2]; mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "http://localhost:3100";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9336", "--user-data-dir=" + OUT + "/../profile-71", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9336/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9336/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };
const waitFor = async (cond, ms = 30000) => { for (let t = 0; t < ms; t += 100) { if (await ev(`return !!(${cond})`)) return true; await sleep(100); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable"); await send("Emulation.setLocaleOverride", { locale: "de-DE" }); await send("Emulation.setTimezoneOverride", { timezoneId: "Asia/Taipei" });
const MEASURE = `
  const vw = document.documentElement.clientWidth; const overflow = document.documentElement.scrollWidth - vw;
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const inline = e => e.tagName === "A" && e.closest("p, li, dd, td");
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary")].filter(vis).filter(e => !inline(e)).map(e => { const r = e.getBoundingClientRect(); return { el: e.tagName.toLowerCase() + " '" + (e.textContent || "").trim().slice(0, 24) + "'", w: Math.round(r.width), h: Math.round(r.height) }; }).filter(x => x.w < 44 || x.h < 44);
  const clipped = [...document.querySelectorAll(".card, .status-tabs .btn, .status-badge, .reason, .timeline-body, .kv dd")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  // Table scroll regions count as clipped here: a column hidden behind horizontal scroll is not acceptable (#71)
  const tableScroll = [...document.querySelectorAll(".table-wrap")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  const q = (s) => document.querySelector(s); const shown = (s) => { const e = q(s); return !!e && vis(e); };
  return { vw, overflow, small, clipped, tableScroll, h1: document.querySelectorAll("h1").length,
    queueVisible: shown(".workspace-queue"), detailVisible: shown(".intake-detail"), backVisible: shown(".back-to-queue"),
    tabs: [...document.querySelectorAll(".status-tabs .btn")].map(b => b.textContent), firstTime: q(".data-table tbody tr td:last-child")?.textContent || null,
    focus: document.activeElement.id || document.activeElement.tagName.toLowerCase() };`;
async function setView(width, theme) { await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 }); await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }); }
async function shot(name) { const { cssContentSize } = await send("Page.getLayoutMetrics"); const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 16000), scale: 1 } }); writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64")); }
async function signIn() {
  await send("Page.navigate", { url: BASE + "/staff" }); await waitFor(`document.querySelector("#staff-token")`); await sleep(300);
  await ev(`const el=document.querySelector("#staff-token"); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; set.call(el,"synthetic-fixture-not-a-token"); el.dispatchEvent(new Event("input",{bubbles:true})); return 1`);
  await ev(`[...document.querySelectorAll("button")].find(b => b.textContent.trim()==="Sign in").click(); return 1`);
  await waitFor(`document.querySelector(".data-table")`); await sleep(400);
}
// Warm-up: the first cold navigation can be measured before the stylesheet applies
await send("Page.navigate", { url: BASE + "/staff" }); await waitFor(`document.querySelector("#staff-token") && getComputedStyle(document.querySelector(".btn")).minHeight === "44px"`); await sleep(500);
const results = []; const checks = {};
for (const theme of ["light", "dark"]) for (const width of [390, 768, 1280]) {
  await setView(width, theme);
  await send("Page.navigate", { url: BASE + "/staff" }); await waitFor(`document.querySelector("#staff-token") && getComputedStyle(document.querySelector(".btn")).minHeight === "44px"`); await sleep(300);
  results.push({ view: "signin", width, theme, ...(await ev(MEASURE)) }); await shot(`signin-${width}-${theme}`);
  await signIn();
  results.push({ view: "queue", width, theme, ...(await ev(MEASURE)) }); await shot(`queue-${width}-${theme}`);
  await ev(`document.querySelector("[data-intake-id]").click(); return 1`);
  await waitFor(`document.querySelector("[data-testid=timeline]")`); await sleep(400);
  results.push({ view: "detail", width, theme, ...(await ev(MEASURE)) }); await shot(`detail-${width}-${theme}`);
}
// Confirmation step + FHIR panel (1280 light); Back to queue (390 light)
await setView(1280, "light"); await signIn();
await ev(`document.querySelector("[data-intake-id]").click(); return 1`); await waitFor(`document.querySelector("[data-testid=timeline]")`);
await ev(`[...document.querySelectorAll("button")].find(b => b.textContent.trim()==="Mark escalated").click(); return 1`); await sleep(300);
checks.confirm = await ev(`return { text: document.querySelector("[data-testid=confirm-step]")?.textContent, focus: document.activeElement.textContent }`);
await ev(`[...document.querySelectorAll("button")].find(b => b.textContent.trim()==="Load FHIR export").click(); return 1`);
await waitFor(`document.querySelector("[data-testid=fhir-resources]")`); await sleep(300);
checks.fhir = await ev(`return { resources: document.querySelector("[data-testid=fhir-resources]").textContent, previewOpen: document.querySelector(".fhir-json").open }`);
await shot("detail-confirm-fhir-1280-light");
await setView(390, "light"); await signIn();
await ev(`document.querySelector("[data-intake-id]").focus(); document.querySelector("[data-intake-id]").click(); return 1`); await waitFor(`document.querySelector("[data-testid=timeline]")`); await sleep(300);
checks.mobileDetail = await ev(MEASURE);
await ev(`document.querySelector(".back-to-queue").click(); return 1`); await sleep(300);
checks.mobileBack = await ev(MEASURE);
checks.tokenStorage = await ev(`return { local: localStorage.length, session: sessionStorage.length, cookie: document.cookie }`);
writeFileSync(`${OUT}/measurements.json`, JSON.stringify({ locale: "de-DE (browser)", timezone: "Asia/Taipei (browser)", results, checks }, null, 2));
ws.close(); chrome.kill();
for (const r of results) console.log(`${r.view.padEnd(7)} ${String(r.width).padStart(4)} ${r.theme.padEnd(5)} overflow=${r.overflow} tableScroll=${r.tableScroll} small=${r.small.length} clipped=${r.clipped} queue=${r.queueVisible} detail=${r.detailVisible} back=${r.backVisible} time=${r.firstTime}`);
console.log(JSON.stringify(checks, null, 1));
