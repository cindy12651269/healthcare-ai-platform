// Hosted #70 check over the DevTools Protocol (no dependencies). Synthetic text only; no sign-in, no token.
// Usage: node capture-cdp-hosted.mjs <outDir> probe    — one non-flagged probe (before any flagged preset)
//        node capture-cdp-hosted.mjs <outDir> presets  — the four presets, 390/1280 × light/dark, + checks
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
const [OUT, PHASE] = process.argv.slice(2); mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "https://healthcare-ai-frontend-1s23.onrender.com";
const PROBE = "Synthetic probe for issue seventy: I have had a mild cough and a runny nose for three days.";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9335", "--user-data-dir=" + OUT + "/../profile-70-hosted-" + PHASE, "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9335/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9335/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const network = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  // Request log: method, URL and status only (no bodies)
  if (m.method === "Network.requestWillBeSent" && /onrender\.com\/(health|api\/)/.test(m.params.request.url)) network.push({ at: new Date().toISOString(), id: m.params.requestId, method: m.params.request.method, url: m.params.request.url });
  if (m.method === "Network.responseReceived") { const n = network.find((x) => x.id === m.params.requestId); if (n) n.status = m.params.response.status; }
};
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };
const waitFor = async (cond, ms = 150000) => { for (let t = 0; t < ms; t += 100) { if (await ev(`return !!(${cond})`)) return true; await sleep(100); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable"); await send("Emulation.setLocaleOverride", { locale: "en-US" }); await send("Emulation.setTimezoneOverride", { timezoneId: "UTC" });

const MEASURE = `
  const vw = document.documentElement.clientWidth;
  const overflow = document.documentElement.scrollWidth - vw;
  const offenders = [...document.querySelectorAll("body *")].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 0.5 && !e.closest(".table-wrap, .json"); }).slice(0, 5).map(e => e.tagName.toLowerCase() + "." + [...e.classList].join("."));
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const inline = e => e.tagName === "A" && e.closest("p, li, dd, td") && !e.classList.contains("entry");
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary")].filter(vis).filter(e => !inline(e)).map(e => { const t = e.type === "checkbox" ? e.closest("label") : e; const r = t.getBoundingClientRect(); return { el: e.tagName.toLowerCase() + " '" + (e.textContent || "").trim().slice(0, 24) + "'", w: Math.round(r.width), h: Math.round(r.height) }; }).filter(x => x.w < 44 || x.h < 44);
  const clipped = [...document.querySelectorAll(".scenario-card, .scenario-card > span, .progress-steps li, .status-badge, .reason, .card, .alert, .tags li")].filter(e => e.scrollWidth > e.clientWidth + 1).length;
  const q = (s) => document.querySelector(s); const results = q("section.results");
  return { at: new Date().toISOString(), vw, overflow, offenders, small, clipped, facts: {
    h1: document.querySelectorAll("h1").length, indicator: q("[data-testid=demo-indicator]")?.textContent || null, llmMode: q("[data-testid=llm-mode]")?.textContent || null,
    scenarios: [...document.querySelectorAll(".scenario-card")].map(b => ({ id: b.dataset.testid, text: b.querySelector(".scenario-text").textContent, expect: b.querySelector(".scenario-expect").textContent, pressed: b.getAttribute("aria-pressed") })),
    consentChecked: [...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent"))?.checked ?? null,
    progress: q("[data-testid=submission-progress]")?.dataset.stage || null, progressText: q("[data-testid=submission-progress]")?.textContent || null,
    badge: q("[data-testid=outcome-summary] .status-badge")?.textContent || null, badgeStatus: q("[data-testid=outcome-summary] .status-badge")?.dataset.status || null,
    reasonsHeading: q("[data-testid=outcome-reasons] .field-label")?.textContent || null, reasons: [...document.querySelectorAll("[data-testid=outcome-reasons] .reason-code")].map(e => e.textContent),
    emergencyFirst: results ? results.children[1]?.dataset.testid === "emergency-guidance" : null, blockedNotice: q("[data-testid=blocked-notice]")?.textContent || null,
    reportHeading: q("#report-heading")?.textContent || null, nextStep: q("[data-testid=next-step]")?.textContent || null, baselineNote: !!q("[data-testid=extraction-baseline-note]"),
    traceVisible: !!q("details.dev-panel"), focus: document.activeElement.id || document.activeElement.dataset.testid || document.activeElement.tagName.toLowerCase() } };`;
async function setView(width, theme) {
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
}
async function go() { await send("Page.navigate", { url: BASE + "/intake" }); await waitFor(`document.readyState === "complete" && document.querySelector("#symptoms")`); await sleep(500); }
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
const active = () => ev(`const a=document.activeElement; const s=getComputedStyle(a); return { el: a.tagName.toLowerCase() + (a.id ? "#" + a.id : "") + " '" + (a.textContent || "").trim().slice(0, 30) + "'", outline: s.outlineStyle + " " + s.outlineWidth };`);
// Submit from the keyboard: focus consent, Tab to the button, Enter
const submitByKeyboard = async () => { await ev(`[...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent")).focus(); return 1`); await key("Tab", "Tab", 9); await key("Enter", "Enter", 13); };
const stagesUntilDone = async () => { const st = []; let last = null; for (let t = 0; t < 150000; t += 100) { const s = await ev(`const p=document.querySelector("[data-testid=submission-progress]"); const e=document.querySelector("[data-testid=intake-error]"); return e ? { stage: "error", text: e.textContent.slice(0, 120) } : p ? { stage: p.dataset.stage, submitDisabled: document.querySelector("button[type=submit]").disabled } : null`); if (s && JSON.stringify(s) !== last) { st.push({ at: new Date().toISOString(), ...s }); last = JSON.stringify(s); } if (s && (s.stage === "done" || s.stage === "error")) break; await sleep(100); } return st; };

const out = { phase: PHASE, base: BASE };
if (PHASE === "probe") {
  await setView(1280, "light"); await go();
  out.before = await ev(MEASURE);
  await setText(PROBE); await tickConsent(); await submitByKeyboard();
  out.submittedAt = new Date().toISOString();
  out.stages = await stagesUntilDone(); await sleep(500);
  out.result = await ev(MEASURE);
  await shot("probe-routine-unique-1280-light");
} else {
  const SCENARIOS = ["routine", "emergency", "prescription", "vague"];
  out.results = [];
  for (const theme of ["light", "dark"]) for (const width of [390, 1280]) {
    await setView(width, theme); await go();
    await click("[data-testid=scenario-routine]"); await sleep(200);
    out.results.push({ view: "form", width, theme, ...(await ev(MEASURE)) });
    await shot(`intake-form-${width}-${theme}`);
    for (const s of SCENARIOS) {
      if (await ev(`return !!document.querySelector("section.results")`)) { await clickText("button", "Start a new intake"); await sleep(300); }
      await click(`[data-testid=scenario-${s}]`); await sleep(100);
      const consentAfterSelect = await ev(`return [...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent")).checked`);
      await tickConsent(); await submitByKeyboard();
      const stages = await stagesUntilDone(); await sleep(500);
      out.results.push({ view: `result-${s}`, width, theme, consentAfterSelect, stages, ...(await ev(MEASURE)), focusStyle: await active() });
      await shot(`result-${s}-${width}-${theme}`);
    }
  }
  // Developer trace behind the reviewer toggle (1280 dark, after the last result)
  await setView(1280, "dark");
  out.trace = { hiddenByDefault: await ev(`return !document.querySelector("details.dev-panel")`) };
  await ev(`[...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("Reviewer")).click(); return 1`); await sleep(200);
  await ev(`document.querySelector("details.dev-panel").open = true; return 1`); await sleep(200);
  out.trace.collapsedThenOpened = true;
  out.trace.run = await ev(`return document.querySelector("details.dev-panel .kv").textContent`);
  await shot("developer-trace-1280-dark");
  await clickText("button", "Start a new intake"); await sleep(300);
  out.reset = await ev(`return { text: document.querySelector("#symptoms").value, consent: [...document.querySelectorAll("input[type=checkbox]")].find(i => i.closest("label").textContent.includes("I consent")).checked, results: !!document.querySelector("section.results"), trace: !!document.querySelector("details.dev-panel"), pressed: [...document.querySelectorAll(".scenario-card")].some(b => b.getAttribute("aria-pressed") === "true"), focus: document.activeElement.id }`);
  // Client validation (nothing is sent)
  await setView(390, "light"); await go();
  await setText("short"); await clickText("button", "Submit intake"); await sleep(300);
  out.clientValidation = await ev(`const t=document.querySelector("#symptoms"); const e=document.querySelector("#symptoms-error"); return { focused: document.activeElement === t, invalid: t.getAttribute("aria-invalid"), describedby: t.getAttribute("aria-describedby"), role: e?.getAttribute("role"), message: e?.textContent }`);
  await shot("error-client-validation-390-light");
}
out.network = network.map(({ id: _id, ...n }) => n);
writeFileSync(`${OUT}/measurements-${PHASE}.json`, JSON.stringify(out, null, 2));
ws.close(); chrome.kill();
console.log(JSON.stringify(PHASE === "probe" ? { submittedAt: out.submittedAt, stages: out.stages, badge: out.result.facts.badge, reasons: out.result.facts.reasons, nextStep: out.result.facts.nextStep, network: out.network } : { n: out.results.length }, null, 1));
