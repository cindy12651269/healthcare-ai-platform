// Synthetic fixture API for the local #70 intake check. No database, no auth, no real data.
// POST /api/ingest returns the real mock-pipeline response for a SCENARIO_PRESETS text (ingest-fixtures.json,
// generated with persistence off); `persistence` is set to "saved" here because no local database ran.
// Error classes are triggered by a synthetic marker in the text, e.g. "[fixture:502]".
// GET /__control?healthDelayMs=…&ingestDelayMs=… adjusts timing for the cold-start and slow-response shots.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
const traces = JSON.parse(readFileSync(new URL("./ingest-fixtures.json", import.meta.url), "utf8"));
const byText = Object.fromEntries(Object.entries(traces).map(([k, t]) => [t.intake.raw_text, { key: k, trace: t }]));
const control = { healthDelayMs: 0, ingestDelayMs: 300 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ERRORS = {
  "400-consent": [400, { detail: "PHI detected but patient consent has not been granted." }],
  "422": [422, { detail: [{ loc: ["body", "text"], msg: "Field required", type: "missing" }] }],
  "502": [502, { detail: "LLM provider error: synthetic fixture" }],
  "503": [503, { detail: "LLM configuration error: synthetic fixture" }],
};
createServer(async (req, res) => {
  const h = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Content-Type": "application/json" };
  if (req.method === "OPTIONS") { res.writeHead(204, h); return res.end(); }
  const url = new URL(req.url, "http://x");
  const send = (body, s = 200) => { res.writeHead(s, h); res.end(JSON.stringify(body)); };
  if (url.pathname === "/__control") {
    for (const k of Object.keys(control)) if (url.searchParams.has(k)) control[k] = Number(url.searchParams.get(k));
    return send(control);
  }
  if (url.pathname === "/health") {
    await sleep(control.healthDelayMs);
    return send({ status: "ok", app: "Healthcare AI Platform", environment: "local-fixture", llm_mode: "mock" });
  }
  if (url.pathname === "/api/ingest" && req.method === "POST") {
    let raw = ""; for await (const c of req) raw += c;
    const { text = "" } = JSON.parse(raw || "{}");
    await sleep(control.ingestDelayMs);
    const marker = text.match(/\[fixture:([\w-]+)\]/)?.[1];
    if (marker === "network") return res.socket.destroy(); // no HTTP response at all
    if (marker && ERRORS[marker]) return send(ERRORS[marker][1], ERRORS[marker][0]);
    const hit = byText[text];
    if (!hit) return send({ detail: "Synthetic fixture: only the four scenario texts are served." }, 500);
    return send({ ...hit.trace, persistence: { status: "saved", record_id: `synthetic-record-${hit.key}` } });
  }
  send({ detail: "not found" }, 404);
}).listen(8787, () => console.log("fixtures on :8787"));
