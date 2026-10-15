// #71 hosted staff workspace check over the DevTools Protocol (no dependencies).
// Tokens are read from ~/.hc-demo-71/tokens.env inside this process, typed into the password field
// and never printed, logged or written. Screenshots are taken before a token is entered or after
// sign-in (the field is then unmounted). Each signed-in page is checked for the token in its HTML.
// Usage: node capture-cdp-hosted.mjs <outDir> transitions|matrix
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
const [OUT, PHASE] = process.argv.slice(2); mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "https://healthcare-ai-frontend-1s23.onrender.com";
const TOK = Object.fromEntries(readFileSync(homedir() + "/.hc-demo-71/tokens.env", "utf8").trim().split("\n").map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
const WHO = { a: { user: "demo-admin-a", clinic: "default", tok: TOK.ADMIN_A_TOKEN }, b: { user: "demo-admin-b", clinic: "demo-clinic-b", tok: TOK.ADMIN_B_TOKEN } };
const R1 = "2f005d14d0fc4de1acc4879d586481a3", R2 = "demo-intake-b2";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9337", "--user-data-dir=" + OUT + "/../profile-71-hosted-" + PHASE, "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9337/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9337/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error("page script failed"); return r.result.value; };
const waitFor = async (cond, ms = 120000) => { for (let t = 0; t < ms; t += 150) { if (await ev(`return !!(${cond})`)) return true; await sleep(150); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setLocaleOverride", { locale: "de-DE" }); await send("Emulation.setTimezoneOverride", { timezoneId: "Asia/Taipei" });
const bws = new WebSocket(ver.webSocketDebuggerUrl); await new Promise((r) => (bws.onopen = r));
bws.send(JSON.stringify({ id: 1, method: "Browser.setDownloadBehavior", params: { behavior: "allow", downloadPath: OUT } }));

const MEASURE = `
  const vw = document.documentElement.clientWidth; const overflow = document.documentElement.scrollWidth - vw;
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const inline = e => e.tagName === "A" && e.closest("p, li, dd, td");
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary")].filter(vis).filter(e => !inline(e)).map(e => { const r = e.getBoundingClientRect(); return { el: e.tagName.toLowerCase() + " '" + (e.textContent || "").trim().slice(0, 24) + "'", w: Math.round(r.width), h: Math.round(r.height) }; }).filter(x => x.w < 44 || x.h < 44);
  const clipped = [...document.querySelectorAll(".card, .status-tabs .btn, .status-badge, .reason, .timeline-body, .kv dd")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  const tableScroll = [...document.querySelectorAll(".table-wrap")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  const q = (s) => document.querySelector(s); const shown = (s) => { const e = q(s); return !!e && vis(e); };
  return { vw, overflow, small, clipped, tableScroll, h1: document.querySelectorAll("h1").length,
    identity: q(".identity-bar p")?.textContent || null,
    queueVisible: shown(".workspace-queue"), detailVisible: shown(".intake-detail"), backVisible: shown(".back-to-queue"),
    tabLabels: [...document.querySelectorAll(".status-tabs .btn")].map(b => b.getAttribute("aria-label")),
    rowIds: [...document.querySelectorAll("[data-intake-id]")].map(b => b.dataset.intakeId),
    scope: q("[data-testid=queue-scope]")?.textContent || null,
    detailStatus: q("[data-testid=detail-status]")?.textContent || null,
    timeline: [...document.querySelectorAll("[data-testid=timeline] li")].map(li => ({ kind: li.dataset.kind, text: li.querySelector(".timeline-body").textContent.trim().slice(0, 160), datetime: li.querySelector("time")?.getAttribute("datetime") })),
    noWebhookNote: q("[data-testid=no-webhook-delivery]")?.textContent || null,
    focus: document.activeElement.id || (document.activeElement.dataset.intakeId ? "row:" + document.activeElement.dataset.intakeId : document.activeElement.tagName.toLowerCase()) };`;
const measure = async () => ev(MEASURE);
async function setView(width, theme) { await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 }); await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }); }
async function shot(name) { const { cssContentSize } = await send("Page.getLayoutMetrics"); const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 16000), scale: 1 } }); writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64")); }
const clickText = (text) => ev(`const b=[...document.querySelectorAll("button")].find(b => b.textContent.trim() === ${JSON.stringify(text)}); if (!b) throw 0; b.click(); return 1`);
// Token hygiene for the current page: HTML, storage and cookies (booleans only)
const tokenFree = async () => { const html = await ev(`return document.documentElement.outerHTML + "|" + JSON.stringify({...localStorage}) + JSON.stringify({...sessionStorage}) + document.cookie`); return !html.includes(TOK.ADMIN_A_TOKEN) && !html.includes(TOK.ADMIN_B_TOKEN); };
async function openStaff() { await send("Page.navigate", { url: BASE + "/staff" }); await waitFor(`document.querySelector("#staff-token") && getComputedStyle(document.querySelector(".btn")).minHeight === "44px"`); await sleep(300); }
async function signIn(w) {
  await ev(`const el=document.querySelector("#staff-token"); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; set.call(el, ${JSON.stringify(WHO[w].tok)}); el.dispatchEvent(new Event("input",{bubbles:true})); return 1`);
  await clickText("Sign in");
  await waitFor(`document.querySelector(".identity-bar") && (document.querySelector(".data-table") || document.querySelector(".empty-state") || document.querySelector(".workspace-queue .alert"))`); await sleep(500);
  return { field: await ev(`return !!document.querySelector("#staff-token")`), tokenFree: await tokenFree() };
}
async function openRow(rid) { await ev(`document.querySelector('[data-intake-id="${rid}"]').click(); return 1`); await waitFor(`document.querySelector("[data-testid=timeline]")`); await sleep(500); }
const out = { phase: PHASE, base: BASE, browser: "headless Chrome, de-DE / Asia/Taipei" };

if (PHASE === "transitions") {
  await setView(1280, "light");
  for (const [w, rid, action, label] of [["a", R1, "Mark reviewed", "reviewed"], ["b", R2, "Mark escalated", "escalated"]]) {
    const run = (out[WHO[w].user] = {});
    await openStaff(); run.signIn = await signIn(w);
    run.queue = await measure(); await shot(`${w}-queue-1280-light`);
    if (!run.queue.rowIds.includes(rid)) throw new Error(`record ${rid} not in ${WHO[w].user} needs_review queue`);
    await openRow(rid);
    run.before = await measure(); await shot(`${w}-detail-before-1280-light`);
    if (!/Needs review/.test(run.before.detailStatus) || run.before.timeline.some((e) => e.kind === "staff_transition")) throw new Error(`record ${rid} not eligible in the UI`);
    await clickText(action); await sleep(300);
    run.confirm = await ev(`return { text: document.querySelector("[data-testid=confirm-step]")?.textContent, focus: document.activeElement.textContent }`);
    await shot(`${w}-confirm-1280-light`);
    await clickText(`Confirm: mark ${label}`);
    const seen = []; const t0 = Date.now();
    for (let t = 0; t < 60000; t += 50) {
      const s = await ev(`const live=document.querySelector(".detail-actions [aria-live]"); return { pending: !!live && live.textContent.includes("Updating status"), done: !!live && live.textContent.includes("Marked ${label}"), disabled: [...document.querySelectorAll(".detail-actions button")].map(b => b.disabled) }`);
      if (!seen.length || JSON.stringify(s) !== JSON.stringify(seen[seen.length - 1].s)) seen.push({ ms: Date.now() - t0, s });
      if (s.done) break; await sleep(50);
    }
    run.transitionStates = seen;
    await waitFor(`[...document.querySelectorAll("[data-testid=timeline] li")].some(li => li.dataset.kind === "staff_transition")`); await sleep(600);
    run.after = await measure(); run.afterTokenFree = await tokenFree();
    run.success = await ev(`return document.querySelector(".detail-actions [aria-live]").textContent`);
    await shot(`${w}-detail-after-1280-light`);
    if (w === "a") {
      await clickText("Load FHIR export"); await waitFor(`document.querySelector("[data-testid=fhir-resources]")`); await sleep(300);
      run.fhir = await ev(`return { resources: [...document.querySelectorAll("[data-testid=fhir-resources] li")].map(li => li.textContent), disclaimer: document.querySelector("[data-testid=fhir-disclaimer]").textContent, previewCollapsed: !document.querySelector(".fhir-json").open, summary: document.querySelector(".fhir-json summary").textContent }`);
      await ev(`document.querySelector(".fhir-json").open = true; return 1`); await sleep(200);
      await shot(`a-fhir-preview-1280-light`);
      run.fhir.previewText = (await ev(`return document.querySelector("[data-testid=fhir-preview]").textContent`)).length;
      const before = new Set(readdirSync(OUT)); await clickText("Download JSON");
      for (let t = 0; t < 15000 && !readdirSync(OUT).some((f) => f.endsWith(".json") && !before.has(f)); t += 200) await sleep(200);
      run.fhir.downloaded = readdirSync(OUT).filter((f) => f.endsWith(".json") && !before.has(f));
    }
    await clickText("Sign out"); await sleep(300);
    run.signedOut = await ev(`return !!document.querySelector("#staff-token") && !document.querySelector(".identity-bar")`);
  }
} else {
  out.results = [];
  for (const theme of ["light", "dark"]) for (const width of [390, 768, 1280]) {
    const w = theme === "light" ? "a" : "b";
    await setView(width, theme); await openStaff();
    out.results.push({ view: "signin", width, theme, ...(await measure()) }); await shot(`signin-${width}-${theme}`);
    const s = await signIn(w);
    out.results.push({ view: "queue", width, theme, who: WHO[w].user, signIn: s, ...(await measure()) }); await shot(`queue-${width}-${theme}`);
    await ev(`document.querySelector("[data-filter=all]").click(); return 1`); await sleep(200);
    const rid = await ev(`return document.querySelector("[data-intake-id]").dataset.intakeId`);
    await openRow(rid);
    out.results.push({ view: "detail", width, theme, who: WHO[w].user, openedRow: rid, tokenFree: await tokenFree(), ...(await measure()) }); await shot(`detail-${width}-${theme}`);
    if (width < 1280) { await clickText("← Back to queue"); await sleep(300); out.results.push({ view: "back", width, theme, ...(await measure()) }); }
    await clickText("Sign out"); await sleep(200);
  }
}
writeFileSync(`${OUT}/measurements-${PHASE}.json`, JSON.stringify(out, null, 2));
ws.close(); bws.close(); chrome.kill();
console.log("done", PHASE);
