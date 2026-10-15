// #84 hosted check, READ-ONLY: clinic-B queue references as demo-admin-b. No action button is clicked.
// The token is read from ~/.hc-demo-71/tokens.env inside this process and typed into the password field;
// it is never printed or written. Network log keeps method + URL + status only (no headers or bodies).
// Usage: node capture-cdp-hosted.mjs <outDir>
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
const [OUT] = process.argv.slice(2); mkdirSync(OUT, { recursive: true });
const BASE = "https://healthcare-ai-frontend-1s23.onrender.com";
const TOKEN = readFileSync(homedir() + "/.hc-demo-71/tokens.env", "utf8").split("\n").find((l) => l.startsWith("ADMIN_B_TOKEN=")).slice(14);
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9338", "--user-data-dir=" + OUT + "/../profile-84", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9338/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9338/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const network = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Network.requestWillBeSent" && m.params.request.url.includes("onrender.com/api/")) network.push({ rid: m.params.requestId, method: m.params.request.method, url: m.params.request.url.replace(/^https:\/\/[^/]+/, "") });
  if (m.method === "Network.responseReceived") { const n = network.find((x) => x.rid === m.params.requestId); if (n) n.status = m.params.response.status; }
};
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error("page script failed"); return r.result.value; };
const waitFor = async (cond, ms = 120000) => { for (let t = 0; t < ms; t += 150) { if (await ev(`return !!(${cond})`)) return true; await sleep(150); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
const MEASURE = `
  const vw = document.documentElement.clientWidth; const overflow = document.documentElement.scrollWidth - vw;
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, summary")].filter(vis).filter(e => !(e.tagName === "A" && e.closest("p, li, dd, td"))).map(e => { const r = e.getBoundingClientRect(); return { el: (e.textContent || "").trim().slice(0, 24), w: Math.round(r.width), h: Math.round(r.height) }; }).filter(x => x.w < 44 || x.h < 44);
  const clipped = [...document.querySelectorAll(".card, .status-badge, .reason, [data-intake-id], .kv dd")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  const tableScroll = [...document.querySelectorAll(".table-wrap")].filter(e => vis(e) && e.scrollWidth > e.clientWidth + 1).length;
  const rows = [...document.querySelectorAll("[data-intake-id]")].filter(vis).map(b => ({ dataIntakeId: b.dataset.intakeId, visible: b.textContent.trim(), ariaLabel: b.getAttribute("aria-label"), w: Math.round(b.getBoundingClientRect().width), h: Math.round(b.getBoundingClientRect().height) }));
  return { vw, overflow, small, clipped, tableScroll, rows, identity: document.querySelector(".identity-bar p")?.textContent || null,
    heading: document.querySelector("#detail-heading")?.textContent || null, fullId: document.querySelector(".detail-header .kv dd code")?.textContent || null,
    queueVisible: !!document.querySelector(".workspace-queue") && vis(document.querySelector(".workspace-queue")), detailVisible: !!document.querySelector(".intake-detail") && vis(document.querySelector(".intake-detail")),
    focus: document.activeElement.id || (document.activeElement.dataset.intakeId ? "row:" + document.activeElement.dataset.intakeId : document.activeElement.tagName.toLowerCase()) };`;
async function setView(width, theme) { await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 }); await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }); }
async function shot(name) { const { cssContentSize } = await send("Page.getLayoutMetrics"); const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 16000), scale: 1 } }); writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64")); }
const tokenFree = async () => !(await ev(`return document.documentElement.outerHTML + JSON.stringify({...localStorage}) + JSON.stringify({...sessionStorage}) + document.cookie`)).includes(TOKEN);
async function signInB() {
  await send("Page.navigate", { url: BASE + "/staff" }); // Wait for React hydration: a click before it would submit the form natively and reload the page
  await waitFor(`(() => { const el = document.querySelector("#staff-token"); return el && Object.keys(el).some(k => k.startsWith("__react")) && getComputedStyle(document.querySelector(".btn")).minHeight === "44px"; })()`); await sleep(300);
  await ev(`const el=document.querySelector("#staff-token"); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; set.call(el, ${JSON.stringify(TOKEN)}); el.dispatchEvent(new Event("input",{bubbles:true})); return 1`);
  await ev(`[...document.querySelectorAll("button")].find(b => b.textContent.trim()==="Sign in").click(); return 1`);
  await waitFor(`document.querySelector(".identity-bar") && document.querySelector("[data-filter=all]") && document.querySelector("[data-testid=queue-scope]")`); await sleep(400);
  await ev(`document.querySelector("[data-filter=all]").click(); return 1`); await sleep(300);
}
const signOut = () => ev(`[...document.querySelectorAll("button")].find(b => b.textContent.trim()==="Sign out").click(); return 1`);
const out = { base: BASE, account: "demo-admin-b", runs: [], details: [] };
// 1. Every row opened once at 1280 light: heading, full id, API path
await setView(1280, "light"); await signInB();
out.queue1280 = await ev(MEASURE); out.tokenFreeQueue = await tokenFree();
await shot("queue-all-1280-light");
for (const r of out.queue1280.rows) {
  await ev(`document.querySelector('[data-intake-id="${r.dataIntakeId}"]').click(); return 1`);
  await waitFor(`document.querySelector("#detail-heading") && document.querySelector(".detail-header .kv code")?.textContent === ${JSON.stringify(r.dataIntakeId)}`); await sleep(300);
  const m = await ev(MEASURE);
  out.details.push({ row: r.dataIntakeId, heading: m.heading, fullId: m.fullId, focus: m.focus });
  if (r.dataIntakeId === "demo-intake-b2") await shot("detail-demo-intake-b2-1280-light");
}
await signOut(); await sleep(300);
// 2. Responsive: queue (All) and one detail at 390/768/1280 × light/dark
for (const theme of ["light", "dark"]) for (const width of [390, 768, 1280]) {
  await setView(width, theme); await signInB();
  const q = await ev(MEASURE); await shot(`queue-all-${width}-${theme}`);
  await ev(`document.querySelector('[data-intake-id="demo-intake-b3"]').click(); return 1`);
  await waitFor(`document.querySelector(".detail-header .kv code")?.textContent === "demo-intake-b3"`); await sleep(300);
  const d = await ev(MEASURE); await shot(`detail-${width}-${theme}`);
  out.runs.push({ width, theme, queue: q, detail: d, tokenFree: await tokenFree() });
  await signOut(); await sleep(200);
}
out.network = network.map(({ rid: _r, ...n }) => n);
out.nonGetRequests = out.network.filter((n) => n.method !== "GET" && n.method !== "OPTIONS");
writeFileSync(`${OUT}/measurements.json`, JSON.stringify(out, null, 2));
ws.close(); chrome.kill(); console.log("done");
