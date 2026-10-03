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
