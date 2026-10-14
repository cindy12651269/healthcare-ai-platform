// Headless Chrome via the DevTools Protocol (no dependencies). Screenshots + layout/a11y measurements.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
const OUT = process.argv[2]; mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "http://localhost:3100";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9333", "--user-data-dir=" + OUT + "/../profile-hosted", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch("http://127.0.0.1:9333/json/version")).json(); } catch { await sleep(200); } }
const tgt = await (await fetch("http://127.0.0.1:9333/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tgt.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, (m) => (m.error ? j(new Error(method + ": " + m.error.message)) : r(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };
const waitFor = async (cond, ms = 120000) => { for (let t = 0; t < ms; t += 100) { if (await ev(`return !!(${cond})`)) return true; await sleep(100); } throw new Error("timeout: " + cond); };
await send("Page.enable"); await send("Runtime.enable"); await send("Emulation.setLocaleOverride", { locale: "en-US" }); await send("Emulation.setTimezoneOverride", { timezoneId: "UTC" });

const MEASURE = `
  const vw = document.documentElement.clientWidth;
  const overflow = document.documentElement.scrollWidth - vw;
  const offenders = [...document.querySelectorAll("body *")].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 0.5 && !e.closest(".table-wrap"); })
    .slice(0, 5).map(e => e.tagName.toLowerCase() + "." + [...e.classList].join("."));
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
  const inline = e => e.tagName === "A" && e.closest("p, li, dd, td") && !e.classList.contains("entry");
  const small = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary")]
    .filter(vis).filter(e => !inline(e)).map(e => { const t = e.type === "checkbox" ? e.closest("label") : e; const r = t.getBoundingClientRect();
      return { el: e.tagName.toLowerCase() + (e.className ? "." + String(e.className).split(" ").join(".") : "") + (e.textContent ? " '" + e.textContent.trim().slice(0, 24) + "'" : ""), w: Math.round(r.width), h: Math.round(r.height) }; })
    .filter(x => x.w < 44 || x.h < 44);
  const scrollRegions = [...document.querySelectorAll(".table-wrap")].map(e => ({ label: e.getAttribute("aria-label"), scrolls: e.scrollWidth > e.clientWidth }));
  const indicator = document.querySelector("[data-testid=demo-indicator]")?.textContent || null;
  const apiStatus = document.querySelector("[data-testid=api-status]")?.textContent?.trim().slice(0, 60) || null;
  const staffPolicy = !!document.querySelector("[data-testid=staff-access-policy]");
  return { at: new Date().toISOString(), vw, overflow, offenders, small, scrollRegions, indicator, apiStatus, staffPolicy };`;

async function setView(width, theme) {
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
}
async function go(path, ready) { await send("Page.navigate", { url: BASE + path }); await waitFor(`document.readyState === "complete"`); await waitFor(ready); await sleep(300); }
async function shot(name) {
  const { cssContentSize } = await send("Page.getLayoutMetrics");
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 6000), scale: 1 } });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64"));
}
const setInput = (sel, val) => ev(`const el=document.querySelector(${JSON.stringify(sel)}); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; set.call(el, ${JSON.stringify(val)}); el.dispatchEvent(new Event("input",{bubbles:true})); return true;`);
const click = (sel) => ev(`document.querySelector(${JSON.stringify(sel)}).click(); return true;`);

const PAGES = [
  ["landing", "/", `document.querySelector("[data-testid=demo-staff]")`],
  ["intake", "/intake", `document.querySelector("[data-testid=llm-mode]")`],
  ["system-card", "/system-card", `document.querySelector("[data-testid=safety-table]")`],
  ["staff-signin", "/staff", `document.querySelector("#staff-token")`],
];
const results = [];
for (const theme of ["light", "dark"]) for (const width of [390, 768, 1280, 1440]) {
  await setView(width, theme);
  for (const [name, path, ready] of PAGES) {
    await go(path, ready);
    results.push({ page: name, width, theme, ...(await ev(MEASURE)) });
    await shot(`${name}-${width}-${theme}`);
  }
}

// Mobile navigation + keyboard + focus checks (390 px, light)
await setView(390, "light"); await go("/intake", `document.querySelector(".nav-toggle")`);
const nav = {};
nav.collapsedHidden = await ev(`return getComputedStyle(document.querySelector("#site-nav")).display === "none"`);
const key = async (k, code, vk) => { const text = k === "Enter" ? "\r" : k === " " ? " " : undefined; await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, code, windowsVirtualKeyCode: vk, text }); await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code, windowsVirtualKeyCode: vk }); await sleep(80); };
const active = () => ev(`const a=document.activeElement; const s=getComputedStyle(a); return { el: a.tagName.toLowerCase()+(a.className?"."+String(a.className).split(" ").join("."):"")+" '"+(a.textContent||a.id||"").trim().slice(0,30)+"'", outline: s.outlineStyle+" "+s.outlineWidth+" "+s.outlineColor };`);
const order = [];
for (let i = 0; i < 4; i++) { await key("Tab", "Tab", 9); order.push(await active()); }
nav.tabOrderStart = order;
// focus the toggle and open with Enter
await ev(`document.querySelector(".nav-toggle").focus(); return 1`);
await key("Enter", "Enter", 13);
nav.openAfterEnter = await ev(`return document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="true" && getComputedStyle(document.querySelector("#site-nav")).display !== "none"`);
await shot("nav-mobile-open-390-light");
await key("Tab", "Tab", 9);
nav.firstLinkFocused = await active();
// Space also toggles; following a link closes the menu

await shot("focus-visible-nav-link-390-light");
nav.linkSizes = await ev(`return [...document.querySelectorAll("#site-nav a")].map(a=>{const r=a.getBoundingClientRect(); return Math.round(r.width)+"x"+Math.round(r.height)})`);
await key("Escape", "Escape", 27);
nav.closedAfterEscape = await ev(`return document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="false" && getComputedStyle(document.querySelector("#site-nav")).display === "none"`);
nav.focusReturned = await ev(`return document.activeElement === document.querySelector(".nav-toggle")`);
// Desktop: nav visible, toggle hidden
await setView(1280, "dark"); await go("/staff", `document.querySelector("#staff-token")`);
nav.desktopNavVisible = await ev(`return getComputedStyle(document.querySelector("#site-nav")).display !== "none" && getComputedStyle(document.querySelector(".nav-toggle")).display === "none"`);
await ev(`document.querySelector("#staff-token").focus(); return 1`); await key("Tab", "Tab", 9);
nav.desktopFocus = await active();
await shot("focus-visible-signin-button-1280-dark");
// Reduced motion
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
await go("/system-card", `document.body`);
nav.reducedMotionSpinner = await ev(`const s=document.createElement("span"); s.className="spinner"; document.body.append(s); const d=getComputedStyle(s).animationDuration; s.remove(); return d;`);

writeFileSync(`${OUT}/../results.json`, JSON.stringify({ results, nav }, null, 2));
ws.close(); chrome.kill();
console.log(JSON.stringify(nav, null, 1));
for (const r of results) console.log(`${r.page.padEnd(16)} ${String(r.width).padStart(4)} ${r.theme.padEnd(5)} overflow=${r.overflow} offenders=${r.offenders.join(",")} small=${JSON.stringify(r.small)} scroll=${JSON.stringify(r.scrollRegions)}`);
