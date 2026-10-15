// Headless Chrome via the DevTools Protocol (no dependencies): #70 intake screenshots + layout/a11y measurements
// against a production build pointed at fixtures-server.mjs. Synthetic data only.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
const OUT = process.argv[2]; mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "http://localhost:3100";
const API = process.env.API || "http://localhost:8787";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9334", "--user-data-dir=" + OUT + "/../profile-70", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9334/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9334/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };
const waitFor = async (cond, ms = 60000) => { for (let t = 0; t < ms; t += 100) { if (await ev(`return !!(${cond})`)) return true; await sleep(100); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable"); await send("Emulation.setLocaleOverride", { locale: "en-US" }); await send("Emulation.setTimezoneOverride", { timezoneId: "UTC" });
const control = (q) => fetch(`${API}/__control?${q}`).then((r) => r.json());

const MEASURE = `
  const vw = document.documentElement.clientWidth;
  const overflow = document.documentElement.scrollWidth - vw;
  const offenders = [...document.querySelectorAll("body *")].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 0.5 && !e.closest(".table-wrap, .json"); })
    .slice(0, 5).map(e => e.tagName.toLowerCase() + "." + [...e.classList].join("."));
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const inline = e => e.tagName === "A" && e.closest("p, li, dd, td") && !e.classList.contains("entry");
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary")]
    .filter(vis).filter(e => !inline(e)).map(e => { const t = e.type === "checkbox" ? e.closest("label") : e; const r = t.getBoundingClientRect();
      return { el: e.tagName.toLowerCase() + (e.className ? "." + String(e.className).split(" ").join(".") : "") + " '" + (e.textContent || "").trim().slice(0, 24) + "'", w: Math.round(r.width), h: Math.round(r.height) }; })
    .filter(x => x.w < 44 || x.h < 44);
  const clipped = [...document.querySelectorAll(".scenario-card, .scenario-card > span, .progress-steps li, .status-badge, .reason, .card, .alert, .tags li")].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className).slice(0, 5);
  const q = (s) => document.querySelector(s);
  const results = q("section.results");
  const facts = {
    h1: document.querySelectorAll("h1").length,
    indicator: q("[data-testid=demo-indicator]")?.textContent || null,
    llmMode: q("[data-testid=llm-mode]")?.textContent || null,
    scenarios: [...document.querySelectorAll(".scenario-card")].map(b => ({ id: b.dataset.testid, pressed: b.getAttribute("aria-pressed"), h: Math.round(b.getBoundingClientRect().height) })),
    consentChecked: q("#symptoms") ? document.querySelector("input[type=checkbox]")?.checked : null,
    progress: q("[data-testid=submission-progress]")?.dataset.stage || null,
    status: q("[data-testid=outcome-summary] .status-badge")?.textContent || null,
    statusCode: q("[data-testid=outcome-summary] .status-badge")?.dataset.status || null,
    reasons: [...document.querySelectorAll("[data-testid=outcome-reasons] .reason-code")].map(e => e.textContent),
    emergencyFirst: results ? results.children[1]?.dataset.testid === "emergency-guidance" : null,
    blockedNotice: q("[data-testid=blocked-notice]")?.textContent || null,
    reportHeading: q("#report-heading")?.textContent || null,
    nextStep: q("[data-testid=next-step]")?.textContent || null,
    baselineNote: !!q("[data-testid=extraction-baseline-note]"),
    traceVisible: !!q("details.dev-panel"),
    focus: document.activeElement.id || document.activeElement.dataset.testid || document.activeElement.tagName.toLowerCase(),
  };
  return { at: new Date().toISOString(), vw, overflow, offenders, small, clipped, facts };`;

async function setView(width, theme) {
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
}
async function go(path) {
  await send("Page.navigate", { url: BASE + path });
  await waitFor(`document.readyState === "complete" && document.querySelector("#symptoms")`); await sleep(400);
}
async function shot(name) {
  const { cssContentSize } = await send("Page.getLayoutMetrics");
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 16000), scale: 1 } });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64"));
}
const click = (sel) => ev(`document.querySelector(${JSON.stringify(sel)}).click(); return true;`);
const clickText = (tag, text) => ev(`[...document.querySelectorAll(${JSON.stringify(tag)})].find(e => e.textContent.trim() === ${JSON.stringify(text)}).click(); return true;`);
const setText = (val) => ev(`const el=document.querySelector("#symptoms"); const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set; set.call(el, ${JSON.stringify(val)}); el.dispatchEvent(new Event("input",{bubbles:true})); return true;`);
const tickConsent = () => ev(`const c=[...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent")); if (!c.checked) c.click(); return true;`);
const key = async (k, code, vk) => { const text = k === "Enter" ? "\r" : k === " " ? " " : undefined; await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, code, windowsVirtualKeyCode: vk, text }); await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code, windowsVirtualKeyCode: vk }); await sleep(80); };
const active = () => ev(`const a=document.activeElement; const s=getComputedStyle(a); return { el: a.tagName.toLowerCase() + (a.id ? "#" + a.id : "") + (a.dataset.testid ? "[" + a.dataset.testid + "]" : "") + " '" + (a.textContent || "").trim().slice(0, 30) + "'", outline: s.outlineStyle + " " + s.outlineWidth + " " + s.outlineColor };`);
const SCENARIOS = ["routine", "emergency", "prescription", "vague"];

// 1. Responsive matrix: form (scenario selected, consent untouched) + the four outcomes, 390/768/1280 × light/dark
await control("healthDelayMs=0&ingestDelayMs=300");
const results = [];
for (const theme of ["light", "dark"]) for (const width of [390, 768, 1280]) {
  await setView(width, theme);
  await go("/intake");
  await click("[data-testid=scenario-routine]"); await sleep(200);
  results.push({ view: "form", width, theme, ...(await ev(MEASURE)) });
  await shot(`intake-form-${width}-${theme}`);
  for (const s of SCENARIOS) {
    if (await ev(`return !!document.querySelector("section.results")`)) { await clickText("button", "Start a new intake"); await sleep(200); }
    await click(`[data-testid=scenario-${s}]`); await tickConsent(); await clickText("button", "Submit intake");
    await waitFor(`document.querySelector("section.results")`); await sleep(400);
    results.push({ view: `result-${s}`, width, theme, ...(await ev(MEASURE)) });
    await shot(`result-${s}-${width}-${theme}`);
  }
}

// 2. Interactions (real key events where keyboard behaviour is checked)
const checks = {};
await setView(390, "light"); await go("/intake");
// Keyboard: Tab to the first scenario card, select it with Space
await ev(`document.querySelector("#intake-form-heading").focus(); return 1`);
await key("Tab", "Tab", 9);
checks.firstTabAfterHeading = await active();
await key(" ", "Space", 32);
checks.scenarioSelectedByKeyboard = await ev(`return { pressed: document.querySelector("[data-testid=scenario-routine]").getAttribute("aria-pressed"), text: document.querySelector("#symptoms").value, consent: document.querySelector("input[type=checkbox]").checked }`);
await shot("focus-scenario-card-390-light");
// Client validation: focus moves to the field, error linked and announced
await setText("short"); await clickText("button", "Submit intake"); await sleep(300);
checks.clientValidation = await ev(`const t=document.querySelector("#symptoms"); const e=document.querySelector("#symptoms-error"); return { focused: document.activeElement === t, invalid: t.getAttribute("aria-invalid"), describedby: t.getAttribute("aria-describedby"), role: e?.getAttribute("role"), message: e?.textContent }`);
checks.clientValidationFocus = await active();
await shot("error-client-validation-390-light");
// API error classes (synthetic markers)
checks.errors = {};
for (const m of ["400-consent", "422", "502", "503", "network"]) {
  await go("/intake");
  const text = `Headache and a stiff neck since yesterday [fixture:${m}]`;
  // Submitted from the keyboard (Tab to the button, Enter), as a keyboard user would
  await setText(text); await tickConsent();
  await ev(`[...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent")).focus(); return 1`);
  await key("Tab", "Tab", 9); await key("Enter", "Enter", 13);
  await waitFor(`document.querySelector("[data-testid=intake-error]")`); await sleep(300);
  checks.errors[m] = await ev(`const a=document.querySelector("[data-testid=intake-error]"); const r=a.querySelector("[data-testid=error-recovery]"); return { errorClass: a.dataset.errorClass, role: a.getAttribute("role"), title: a.querySelector(".alert-title").textContent, text: a.textContent, recovery: r.textContent, recoveryEnabled: !r.disabled, textKept: document.querySelector("#symptoms").value === ${JSON.stringify(text)}, consentKept: document.querySelector("input[type=checkbox]").checked, focus: document.activeElement.id || document.activeElement.dataset.testid || document.activeElement.tagName }`);
  checks.errors[m].focusStyle = await active();
  await shot(`error-${m}-390-light`);
}
// Start a new intake after an error: everything cleared, focus back to the form heading
await clickText("button", "Start a new intake"); await sleep(300);
checks.resetAfterError = await ev(`return { text: document.querySelector("#symptoms").value, consent: document.querySelector("input[type=checkbox]").checked, error: !!document.querySelector("[data-testid=intake-error]"), focus: document.activeElement.id }`);

// 3. Cold start: /health answers after 6 s; the submission waits in stage 1 and sends only afterwards
await setView(1280, "light");
await control("healthDelayMs=6000&ingestDelayMs=1500");
await send("Page.navigate", { url: BASE + "/intake" });
await waitFor(`document.readyState === "complete" && document.querySelector("#symptoms")`);
await click("[data-testid=scenario-emergency]"); await tickConsent(); await clickText("button", "Submit intake");
const stages = []; let last = null; let wakingShot = false;
for (let t = 0; t < 30000; t += 100) {
  const s = await ev(`const p=document.querySelector("[data-testid=submission-progress]"); return p ? { stage: p.dataset.stage, status: p.querySelector("[role=status]").textContent.trim(), submitDisabled: [...document.querySelectorAll("button[type=submit]")][0].disabled } : null`);
  if (s && JSON.stringify(s) !== last) { stages.push({ at: new Date().toISOString(), ...s }); last = JSON.stringify(s); }
  if (s?.stage === "waking" && !wakingShot) { await sleep(300); await shot("stage-waking-1280-light"); wakingShot = true; }
  if (s?.stage === "done") break;
  await sleep(100);
}
checks.coldStartStages = stages;
await sleep(400); await shot("result-after-cold-start-1280-light");

// 4. Slow processing: the note appears after 15 s; no percentage, no resubmission
await control("healthDelayMs=0&ingestDelayMs=17000");
await go("/intake");
await click("[data-testid=scenario-vague]"); await tickConsent(); await clickText("button", "Submit intake");
await waitFor(`document.querySelector("[data-testid=submission-progress] [role=status]")?.textContent.includes("longer than usual")`, 30000);
checks.slow = await ev(`return { status: document.querySelector("[data-testid=submission-progress] [role=status]").textContent.trim(), submitDisabled: document.querySelector("button[type=submit]").disabled, percent: document.querySelector("[data-testid=submission-progress]").textContent.includes("%") }`);
await shot("stage-processing-slow-1280-light");
await waitFor(`document.querySelector("section.results")`, 30000);
await control("healthDelayMs=0&ingestDelayMs=300");

// 5. Developer trace behind the reviewer toggle (1280 dark), then reset from a result
await setView(1280, "dark"); await go("/intake");
await click("[data-testid=scenario-prescription]"); await tickConsent(); await clickText("button", "Submit intake");
await waitFor(`document.querySelector("section.results")`); await sleep(300);
checks.traceHiddenByDefault = await ev(`return !document.querySelector("details.dev-panel")`);
await ev(`[...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("Reviewer")).click(); return 1`); await sleep(200);
await ev(`document.querySelector("details.dev-panel").open = true; return 1`); await sleep(200);
checks.traceRun = await ev(`return document.querySelector("details.dev-panel .kv").textContent`);
await shot("developer-trace-1280-dark");
await clickText("button", "Start a new intake"); await sleep(300);
checks.resetAfterResult = await ev(`return { text: document.querySelector("#symptoms").value, consent: document.querySelector("input[type=checkbox]").checked, results: !!document.querySelector("section.results"), trace: !!document.querySelector("details.dev-panel"), pressed: [...document.querySelectorAll(".scenario-card")].some(b => b.getAttribute("aria-pressed") === "true"), focus: document.activeElement.id }`);
checks.resetFocusStyle = await active();

// Reduced motion
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
checks.reducedMotionSpinner = await ev(`const s=document.createElement("span"); s.className="spinner"; document.body.append(s); const d=getComputedStyle(s).animationDuration; s.remove(); return d;`);

writeFileSync(`${OUT}/measurements.json`, JSON.stringify({ results, checks }, null, 2));
ws.close(); chrome.kill();
for (const r of results) console.log(`${r.view.padEnd(20)} ${String(r.width).padStart(4)} ${r.theme.padEnd(5)} overflow=${r.overflow} offenders=${r.offenders.join(",")} small=${JSON.stringify(r.small)} clipped=${JSON.stringify(r.clipped)} status=${r.facts.status} reasons=${r.facts.reasons}`);
console.log(JSON.stringify(checks, null, 1));
