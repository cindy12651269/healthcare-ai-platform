import { PipelineResult } from "./api";

// Patient-facing reading of one /api/ingest response (#70). Display only: every value comes from the
// response; nothing here re-evaluates safety or escalation.

type JsonObject = Record<string, unknown>;

export const asObject = (v: unknown): JsonObject | null =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : null;

export const asText = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);

export const asStrings = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((s): s is string => typeof s === "string" && s.trim() !== "") : [];

// True when any backend safety result asked for emergency guidance.
export function needsEmergencyGuidance(data: PipelineResult): boolean {
  const actionLists: unknown[] = [asObject(data.safety)?.actions];
  const events = asObject(asObject(data.report)?.safety_checks)?.events;
  if (Array.isArray(events)) {
    events.forEach((e) => actionLists.push(asObject(e)?.actions));
  }
  return actionLists.some((a) => Array.isArray(a) && a.includes("add_emergency_guidance"));
}

// persistence.status from agents/pipeline.py::save_record
export type StorageStatus = "saved" | "duplicate" | "disabled" | "skipped" | "failed" | "unknown";

export interface IntakeOutcome {
  reviewStatus: string | null; // "submitted" | "needs_review" as decided by the escalation rules (#29)
  flagged: boolean;
  reasons: string[];
  emergency: boolean;
  blocked: boolean; // the generated report was withheld and a safe acknowledgement returned
  blockedActions: string[]; // guard actions that blocked it (block_diagnosis / block_prescription)
  storage: StorageStatus;
}

const STORAGE: StorageStatus[] = ["saved", "duplicate", "disabled", "skipped", "failed"];

export function readOutcome(data: PipelineResult): IntakeOutcome {
  const escalation = asObject(data.escalation);
  const reasons = asStrings(escalation?.reasons);
  const reviewStatus = asText(escalation?.review_status);
  const safety = asObject(data.safety);
  const actions = asStrings(safety?.actions);
  const reportVersion = asText(asObject(asObject(data.report)?.report_metadata)?.model_version);
  const storage = asText(asObject(data.persistence)?.status);

  return {
    reviewStatus,
    flagged: escalation?.required === true || reviewStatus === "needs_review",
    reasons,
    emergency: needsEmergencyGuidance(data) || reasons.includes("emergency_signal"),
    blocked: safety?.allowed === false || reportVersion === "safety_acknowledgement",
    blockedActions: actions.filter((a) => a.startsWith("block_")),
    storage: STORAGE.includes(storage as StorageStatus) ? (storage as StorageStatus) : "unknown",
  };
}
