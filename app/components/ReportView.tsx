import { PipelineResult } from "../services/api";

type JsonObject = Record<string, unknown>;

const asObject = (v: unknown): JsonObject | null =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : null;

const asText = (v: unknown): string | null =>
  typeof v === "string" && v.trim() ? v : null;

// Report section keys from llm/schemas/report_output.json, with patient-friendly headings.
const REPORT_SECTIONS: [string, string][] = [
  ["overview", "Overview"],
  ["symptom_analysis", "Your symptoms"],
  ["clinical_insights", "Notes for your care team"],
  ["risk_summary", "Things to watch"],
  ["recommendations", "Suggested next steps"],
];

// True when any backend safety result asked for emergency guidance.
export function needsEmergencyGuidance(data: PipelineResult): boolean {
  const actionLists: unknown[] = [asObject(data.safety)?.actions];
  const events = asObject(asObject(data.report)?.safety_checks)?.events;
  if (Array.isArray(events)) {
    events.forEach((e) => actionLists.push(asObject(e)?.actions));
  }
  return actionLists.some(
    (a) => Array.isArray(a) && a.includes("add_emergency_guidance"),
  );
}

interface ReportViewProps {
  data: PipelineResult;
}

// User-facing result: structured intake summary and the safety-checked report.
export default function ReportView({ data }: ReportViewProps) {
  const clinical = asObject(asObject(data.structured)?.clinical_structuring);
  const chiefComplaint = asText(clinical?.chief_complaint);
  const clinicalSummary = asText(clinical?.clinical_summary);
  const symptoms = Array.isArray(clinical?.symptoms)
    ? (clinical!.symptoms as unknown[]).filter((s): s is string => typeof s === "string")
    : [];

  const reportSections = asObject(asObject(data.report)?.report_sections);
  const sections = REPORT_SECTIONS.flatMap(([key, heading]) => {
    const body = asText(reportSections?.[key]);
    return body ? [{ key, heading, body }] : [];
  });

  const safetyChecks = asObject(asObject(data.report)?.safety_checks);

  return (
    <section className="results" aria-labelledby="results-heading">
      <h2 id="results-heading">Your intake has been received</h2>

      {needsEmergencyGuidance(data) && (
        <div className="alert alert-urgent" role="alert">
          <strong>Your description mentions symptoms that may need urgent attention.</strong>{" "}
          If your symptoms are severe or getting worse quickly, please seek urgent
          medical care now. In the U.S., call 911; elsewhere, contact your local
          emergency number.
        </div>
      )}

      <article className="card">
        <h3>Intake summary</h3>
        <dl className="summary-list">
          <dt>What you told us</dt>
          <dd>{chiefComplaint ?? "Not available"}</dd>
          <dt>Symptoms noted</dt>
          <dd>
            {symptoms.length > 0 ? (
              <ul className="tags">
                {symptoms.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            ) : (
              "No specific symptoms were extracted."
            )}
          </dd>
          {clinicalSummary && (
            <>
              <dt>Summary</dt>
              <dd>{clinicalSummary}</dd>
            </>
          )}
        </dl>
      </article>

      <article className="card">
        <h3>Pre-visit report</h3>
        {sections.length > 0 ? (
          sections.map((s) => (
            <div key={s.key} className="report-section">
              <h4>{s.heading}</h4>
              <p>{s.body}</p>
            </div>
          ))
        ) : (
          <p className="muted" data-testid="report-unavailable">
            A written report was not returned for this submission.
          </p>
        )}
        {safetyChecks && (
          <p className="safety-note">
            Safety review:{" "}
            {safetyChecks.diagnostic_check_passed === true &&
            safetyChecks.phi_safe === true
              ? "checked for diagnostic language and personal details."
              : "safety checks adjusted this report before it was shown."}
          </p>
        )}
      </article>

      <p className="disclaimer">
        This summary helps your care team prepare for your visit. It is not a
        diagnosis or medical advice.
        {data.run_id && <> Reference: <code>{data.run_id}</code></>}
      </p>
    </section>
  );
}
