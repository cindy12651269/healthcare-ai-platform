// Synthetic fixture API for local visual checks (#68). Accepts any bearer string; no real auth, no real data.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
const card = readFileSync(new URL("./system_card.json", import.meta.url), "utf8");
const ME = { user_id: "demo-staff-a", email: "demo-staff-a@example.test", memberships: [{ clinic_id: "default", role: "clinic_staff" }] };
const at = (m) => `2026-10-14T0${m}:00:00Z`;
const queue = [
  ["a1f3c2d4e5f60718", "needs_review", "emergency_signal", 1],
  ["b2e4d6f8a0b1c2d3", "needs_review", "blocked_prescription,low_confidence", 2],
  ["c3d5e7f9a1b2c3d4", "needs_review", "low_confidence", 3],
  ["d4e6f8a0b2c3d4e5", "reviewed", "blocked_diagnosis", 4],
  ["e5f7a9b1c3d4e5f6", "escalated", "emergency_signal", 5],
  ["f6a8b0c2d4e5f6a7", "submitted", null, 6],
].map(([id, review_status, escalation_reason, m]) => ({ id, trace_id: `trace-${id}`, review_status, escalation_reason, created_at: at(m), updated_at: at(m) }));
const detail = (id) => ({
  ...queue.find((q) => q.id === id), clinic_id: "default",
  structured: { clinical_structuring: { chief_complaint: "Sudden chest pain and shortness of breath since this morning.", symptoms: ["chest pain", "shortness of breath"], clinical_summary: "Synthetic: chest pain with breathlessness, onset this morning.", confidence_level: 0.7 } },
  report: { report_sections: { overview: "Pre-visit intake received (synthetic).", symptom_analysis: "Symptoms noted: chest pain, shortness of breath.", clinical_insights: "Not a medical assessment.", risk_summary: "Seek urgent care if severe.", recommendations: "Share these notes with your care team." } },
  safety: { allowed: true, actions: ["add_emergency_guidance"], reasons: [], severity: "high" },
});
const timeline = (id) => ({
  intake_id: id, clinic_id: "default", review_status: "needs_review",
  evidence: {
    original_input: "Sudden chest pain and shortness of breath since this morning.",
    extracted: { symptoms: ["chest pain", "shortness of breath"], duration: null, onset: "since this morning", severity: null, red_flags: ["chest pain"], confidence_level: 0.7 },
    recorded_matches: [{ type: "EMERGENCY", detail: "Emergency or crisis signal detected", match: "chest pain", found_in_input: true }],
    escalation_rules: [{ reason: "emergency_signal", rule: "Emergency or crisis language in the intake or the generated report", evidence: { guard_action_recorded: true } }],
    provenance: { execution_mode: "mock", model_version: "mock", prompt_version: "deterministic_rule_based_baseline_v1", pipeline_version: "v0.1.0", run_id: "run-synthetic-0001" },
  },
  events: [
    { kind: "submitted", at: at(1), at_source: "intake.timestamp", details: {} },
    { kind: "processed", at: at(1), at_source: "record.created_at", details: { execution_mode: "mock", model_version: "mock", run_id: "run-synthetic-0001" } },
    { kind: "safety_evaluated", at: at(1), at_source: "record.created_at", details: { actions: ["add_emergency_guidance"], reason_types: ["EMERGENCY"], severity: "high" } },
    { kind: "escalation_decision", at: at(1), at_source: "record.created_at", details: { required: true, reasons: ["emergency_signal"] } },
    { kind: "staff_transition", at: at(2), at_source: "review_events.created_at", details: { actor_id: "demo-admin-a", from_status: "needs_review", to_status: "escalated" } },
  ],
  notes: [],
});
const fhir = { resourceType: "Bundle", type: "collection", entry: [{ fullUrl: "urn:uuid:synthetic-1", resource: { resourceType: "Task", status: "ready", intent: "order" } }] };
createServer((req, res) => {
  const h = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Content-Type": "application/json" };
  if (req.method === "OPTIONS") { res.writeHead(204, h); return res.end(); }
  const url = new URL(req.url, "http://x"); const p = url.pathname;
  const send = (body, s = 200) => { res.writeHead(s, h); res.end(typeof body === "string" ? body : JSON.stringify(body)); };
  if (p === "/health") return send({ status: "ok", environment: "local-fixture", llm_mode: "mock" });
  if (p === "/api/system-card") return send(card);
  if (p === "/api/staff/me") return send(ME);
  let m;
  if ((m = p.match(/^\/api\/clinics\/default\/intakes$/))) { const f = url.searchParams.get("review_status"); return send(f ? queue.filter((q) => q.review_status === f) : queue); }
  if ((m = p.match(/^\/api\/clinics\/default\/intakes\/([^/]+)\/timeline$/))) return send(timeline(m[1]));
  if ((m = p.match(/^\/api\/clinics\/default\/intakes\/([^/]+)\/fhir$/))) return send(fhir);
  if ((m = p.match(/^\/api\/clinics\/default\/intakes\/([^/]+)$/))) return send(detail(m[1]));
  send({ detail: "not found" }, 404);
}).listen(8787, () => console.log("fixtures on :8787"));
