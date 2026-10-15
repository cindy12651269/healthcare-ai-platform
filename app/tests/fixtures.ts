import { PipelineResult } from "../services/api";

// Mirrors the trace shape built in agents/pipeline.py, with a report following
// llm/schemas/report_output.json. Used to exercise rendering; not a claim about current backend output.
export function pipelineResult(overrides: Partial<PipelineResult> = {}): PipelineResult {
  return {
    run_id: "run-123",
    success: true,
    intake: { input_id: "in-1", raw_text: "Sore throat and mild fever for two days." },
    structured: {
      clinical_structuring: {
        chief_complaint: "Sore throat and mild fever for two days.",
        symptoms: ["sore throat", "fever"],
        clinical_summary: "Two-day history of sore throat with low-grade fever.",
        confidence_level: 0.9,
      },
    },
    rag: { enabled: false, used: false, query: null, top_k: 3, chunks: [], error: null },
    report: {
      source_struct_id: "in-1",
      report_sections: {
        overview: "You reported a sore throat and mild fever.",
        symptom_analysis: "Symptoms began two days ago.",
        clinical_insights: "Pattern is consistent with a common upper respiratory complaint.",
        risk_summary: "Watch for difficulty swallowing or a high fever.",
        recommendations: "Rest, fluids, and follow up with your care team.",
      },
      safety_checks: { diagnostic_check_passed: true, phi_safe: true, events: [] },
      report_metadata: { generated_at: "2026-01-01T00:00:00Z", model_version: "x", prompt_version: "v1" },
    },
    safety: { allowed: true, masked_text: "", actions: [], reasons: [], severity: "low" },
    escalation: { required: false, review_status: "submitted", reasons: [], confidence_level: 0.9, low_confidence_threshold: 0.5 },
    persistence: { status: "saved", record_id: "rec-1" },
    errors: [],
    telemetry: { latency_ms: 12, retrieval_hits: 0, safety_violations: 0 },
    metrics: {
      intake_ms: 1.2,
      structuring_ms: 3.4,
      retrieval_ms: 0,
      output_ms: 5.6,
      safety_ms: 0.1,
      persistence_ms: 0.5,
      latency_ms: 12,
      safety_violation_count: 0,
      retrieval_hit_count: 0,
    },
    ...overrides,
  };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const EMERGENCY_GUIDANCE =
  "If you are experiencing severe or rapidly worsening symptoms, or you might be in danger, please seek urgent medical care immediately.";

// The four guided-demo outcomes (#70), shaped like the mock pipeline's responses to SCENARIO_PRESETS.
// Synthetic, written for rendering tests; the backend rules themselves are tested in tests/test_escalation.py.
export const scenarioResults: Record<"routine" | "emergency" | "prescription" | "vague", PipelineResult> = {
  routine: pipelineResult({
    structured: {
      clinical_structuring: {
        chief_complaint: "I have had a sore throat and a mild fever for two days.",
        symptoms: ["sore throat", "fever"],
        red_flags: [],
        duration: "two days",
        severity: "mild",
        clinical_summary: "Rule-based baseline (not LLM-generated). Reported symptoms: sore throat, fever.",
        confidence_level: 1,
      },
      output_metadata: { generated_at: "2025-01-01T00:00:00Z", model_version: "mock", prompt_version: "v1" },
    },
    escalation: { required: false, review_status: "submitted", reasons: [], confidence_level: 1, low_confidence_threshold: 0.5 },
  }),
  emergency: pipelineResult({
    structured: {
      clinical_structuring: {
        chief_complaint: "I have chest pain and shortness of breath since this morning.",
        symptoms: ["chest pain", "shortness of breath"],
        red_flags: ["chest pain", "shortness of breath"],
        onset: "since this morning",
        clinical_summary: "Rule-based baseline (not LLM-generated). Reported symptoms: chest pain, shortness of breath.",
        confidence_level: 0.85,
      },
      output_metadata: { generated_at: "2025-01-01T00:00:00Z", model_version: "mock", prompt_version: "v1" },
    },
    report: {
      report_sections: {
        overview: `Pre-visit intake received.\n\n${EMERGENCY_GUIDANCE}`,
        recommendations: "Keep a note of when your symptoms occur and share it with your care team.",
      },
      safety_checks: {
        diagnostic_check_passed: true,
        phi_safe: true,
        events: [{ severity: "high", actions: ["add_emergency_guidance"], reasons: [{ type: "EMERGENCY" }] }],
      },
      report_metadata: { model_version: "mock" },
    },
    safety: { allowed: true, actions: ["add_emergency_guidance"], reasons: [], severity: "high" },
    escalation: { required: true, review_status: "needs_review", reasons: ["emergency_signal"], confidence_level: 0.85 },
  }),
  prescription: pipelineResult({
    structured: {
      clinical_structuring: {
        chief_complaint: "Should I take 500 mg of amoxicillin for this cough?",
        symptoms: ["cough"],
        red_flags: [],
        clinical_summary: "Rule-based baseline (not LLM-generated). Reported symptoms: cough.",
        confidence_level: 0.5,
      },
      output_metadata: { generated_at: "2025-01-01T00:00:00Z", model_version: "mock", prompt_version: "v1" },
    },
    report: {
      report_sections: {
        overview:
          "Thank you, your pre-visit intake has been received. A member of your care team will review it before your visit.",
        symptom_analysis: "An automated summary is not available for this intake.",
        recommendations: "Please bring any questions about your symptoms to your care team.",
      },
      safety_checks: { diagnostic_check_passed: false, phi_safe: true },
      report_metadata: { model_version: "safety_acknowledgement" },
    },
    safety: { allowed: false, masked_text: "", actions: ["block_prescription"], reasons: [{ type: "MEDICAL_PRESCRIPTION" }], severity: "high" },
    escalation: { required: true, review_status: "needs_review", reasons: ["blocked_prescription"], confidence_level: 0.5 },
  }),
  vague: pipelineResult({
    structured: {
      clinical_structuring: {
        chief_complaint: "I just don't feel right and wanted to check in.",
        symptoms: [],
        red_flags: [],
        clinical_summary: "Rule-based baseline (not LLM-generated): no symptoms from the baseline lexicon were found.",
        confidence_level: 0.1,
      },
      output_metadata: { generated_at: "2025-01-01T00:00:00Z", model_version: "mock", prompt_version: "v1" },
    },
    escalation: { required: true, review_status: "needs_review", reasons: ["low_confidence"], confidence_level: 0.1 },
  }),
};
