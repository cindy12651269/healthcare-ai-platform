import { ReactNode, Ref } from "react";
import { PipelineResult } from "../services/api";
import { IntakeOutcome, StorageStatus, asObject, asStrings, asText, readOutcome } from "../services/intakeOutcome";
import { Alert, Card, ReasonList, StatusBadge } from "./ui";

export { needsEmergencyGuidance } from "../services/intakeOutcome";

// Report section keys from llm/schemas/report_output.json, with patient-friendly headings.
const REPORT_SECTIONS: [string, string][] = [
  ["overview", "Overview"],
  ["symptom_analysis", "Your symptoms"],
  ["clinical_insights", "Notes for your care team"],
  ["risk_summary", "Things to watch"],
  ["recommendations", "Suggested next steps"],
];

// Patient-facing wording of the escalation decision (#70); staff views keep the stored status labels
const PATIENT_STATUS: Record<string, string> = {
  submitted: "Submitted",
  needs_review: "Flagged for staff review",
};

const BLOCK_LABELS: Record<string, string> = {
  block_diagnosis: "diagnostic language",
  block_prescription: "prescription or dosing content",
};

// Only a newly saved record is in the queue with this decision. For any other storage result the badge
// says what happened to the record instead, so it never implies a new queue item.
const STORAGE_BADGE: Partial<Record<StorageStatus, string>> = {
  duplicate: "Already received · no new record",
  disabled: "Not stored",
  skipped: "Not stored",
  failed: "Not stored",
};

const NOT_STORED: Partial<Record<StorageStatus, string>> = {
  disabled: "storage is turned off on this server",
  skipped: "the run did not complete",
  failed: "the record could not be saved",
};

function whatHappensNext(outcome: IntakeOutcome): string {
  const { flagged, storage } = outcome;
  if (storage === "saved") {
    return flagged
      ? "Your intake has been flagged for staff review. Authorized clinic staff can review this record in their queue."
      : "Your intake has been stored as submitted. Authorized clinic staff can see it in their queue; no review flag was raised.";
  }
  if (storage === "duplicate") {
    return "An identical description was received earlier, so no new record was created and nothing new was added to the clinic staff queue.";
  }
  if (storage === "unknown") {
    return "The service did not report whether this intake was stored, so we cannot say whether it is in the clinic staff queue.";
  }
  return `This intake was not stored (${NOT_STORED[storage]}), so it will not appear in the clinic staff queue.`;
}

interface ReportViewProps {
  data: PipelineResult;
  headingRef?: Ref<HTMLHeadingElement>; // focused when the result appears
  actions?: ReactNode; // e.g. "Start a new intake"
}

// User-facing result (#70): outcome first, then the intake summary, extracted information, safety
// findings, the report (or the safe acknowledgement that replaced it) and next steps.
export default function ReportView({ data, headingRef, actions }: ReportViewProps) {
  const outcome = readOutcome(data);
  const clinical = asObject(asObject(data.structured)?.clinical_structuring);
  const chiefComplaint = asText(clinical?.chief_complaint);
  const clinicalSummary = asText(clinical?.clinical_summary);
  const symptoms = asStrings(clinical?.symptoms);
  const redFlags = asStrings(clinical?.red_flags);
  const duration = asText(clinical?.duration);
  const onset = asText(clinical?.onset);
  const severity = asText(clinical?.severity);
  // Mock mode (#40): a deterministic rule-based baseline produced these fields, not an LLM
  const ruleBasedBaseline =
    asText(asObject(asObject(data.structured)?.output_metadata)?.model_version) === "mock";

  const reportSections = asObject(asObject(data.report)?.report_sections);
  const sections = REPORT_SECTIONS.flatMap(([key, heading]) => {
    const body = asText(reportSections?.[key]);
    return body ? [{ key, heading, body }] : [];
  });
  const safetyChecks = asObject(asObject(data.report)?.safety_checks);
  const checksPassed = safetyChecks?.diagnostic_check_passed === true && safetyChecks?.phi_safe === true;

  return (
    <section className="results" aria-labelledby="results-heading">
      <h2 id="results-heading" ref={headingRef} tabIndex={-1}>
        Your intake has been received
      </h2>

      {/* Emergency guidance stays first and most prominent whenever present */}
      {outcome.emergency && (
        <Alert variant="urgent" data-testid="emergency-guidance" title="Your description mentions symptoms that may need urgent attention.">
          <p>
            If your symptoms are severe or getting worse quickly, please seek urgent medical care now. In the U.S.,
            call 911; elsewhere, contact your local emergency number. Do not wait for the clinic to review this
            intake.
          </p>
        </Alert>
      )}

      <Card as="article" className="outcome-card" data-testid="outcome-summary" aria-labelledby="outcome-heading">
        <h3 id="outcome-heading">Outcome</h3>
        <p className="outcome-status">
          {STORAGE_BADGE[outcome.storage] ? (
            <StatusBadge status={outcome.storage} label={STORAGE_BADGE[outcome.storage]} />
          ) : outcome.reviewStatus ? (
            <StatusBadge status={outcome.reviewStatus} label={PATIENT_STATUS[outcome.reviewStatus]} />
          ) : (
            <span className="muted">The service did not return a review status.</span>
          )}
        </p>
        {outcome.reasons.length > 0 && (
          <div className="outcome-reasons" data-testid="outcome-reasons">
            <span className="field-label">
              {outcome.storage === "saved" || outcome.storage === "unknown"
                ? "Why it was flagged"
                : "Escalation rules this description matched"}
            </span>
            <ReasonList reasons={outcome.reasons} />
          </div>
        )}
        {outcome.blocked && (
          <p className="outcome-blocked" data-testid="blocked-notice">
            <strong>No automated report was generated for you.</strong> The safety check withheld it because it
            would have included{" "}
            {outcome.blockedActions.map((a) => BLOCK_LABELS[a] ?? a).join(" and ") || "content that is not allowed"}.
            You see a safe acknowledgement instead.
          </p>
        )}
        <p data-testid="next-step">{whatHappensNext(outcome)}</p>
      </Card>

      <Card as="article" aria-labelledby="summary-heading">
        <h3 id="summary-heading">Intake summary</h3>
        <dl className="summary-list">
          <dt>What you told us</dt>
          <dd>{chiefComplaint ?? "Not available"}</dd>
          {clinicalSummary && (
            <>
              <dt>Summary</dt>
              <dd>{clinicalSummary}</dd>
            </>
          )}
        </dl>
      </Card>

      <Card as="article" aria-labelledby="extracted-heading">
        <h3 id="extracted-heading">Extracted information</h3>
        <dl className="summary-list">
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
          {duration && (
            <>
              <dt>Duration</dt>
              <dd>{duration}</dd>
            </>
          )}
          {onset && (
            <>
              <dt>Onset</dt>
              <dd>{onset}</dd>
            </>
          )}
          {severity && (
            <>
              <dt>Severity</dt>
              <dd>{severity}</dd>
            </>
          )}
          {redFlags.length > 0 && (
            <>
              <dt>Warning signs noted</dt>
              <dd>{redFlags.join(", ")}</dd>
            </>
          )}
        </dl>
        {ruleBasedBaseline && (
          <p className="muted" data-testid="extraction-baseline-note">
            Extracted by a deterministic rule-based baseline, not LLM-generated output. It recognises only a small
            fixed symptom vocabulary and simple duration, onset and severity phrases, and may miss or misread
            anything else.
          </p>
        )}
      </Card>

      <Card as="article" aria-labelledby="safety-heading" data-testid="safety-findings">
        <h3 id="safety-heading">Safety findings</h3>
        <ul className="finding-list">
          {outcome.emergency && <li>Emergency language was recognised, so urgent-care guidance was added.</li>}
          {outcome.blocked && <li>The generated report was blocked and replaced with a safe acknowledgement.</li>}
          {outcome.reasons.includes("low_confidence") && (
            <li>Few details could be extracted automatically, so the intake was flagged for a person to read.</li>
          )}
          {safetyChecks && (
            <li className="safety-note">
              Safety review:{" "}
              {checksPassed
                ? "checked for diagnostic language and personal details."
                : "safety checks adjusted this report before it was shown."}
            </li>
          )}
          {!safetyChecks && !outcome.emergency && !outcome.blocked && <li>No safety results were returned.</li>}
        </ul>
      </Card>

      <Card as="article" aria-labelledby="report-heading" className={outcome.blocked ? "report-blocked" : undefined}>
        <h3 id="report-heading">{outcome.blocked ? "Safe acknowledgement (report withheld)" : "Pre-visit report"}</h3>
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
      </Card>

      <Card as="article" aria-labelledby="next-heading">
        <h3 id="next-heading">Next steps</h3>
        <ul className="finding-list">
          {outcome.emergency && <li>If your symptoms are severe or getting worse, seek urgent care now.</li>}
          <li>{whatHappensNext(outcome)}</li>
          <li>Bring any questions about your symptoms to your appointment.</li>
        </ul>
        <p className="disclaimer">
          This summary helps your care team prepare for your visit. It is not a diagnosis or medical advice.
          {data.run_id && (
            <>
              {" "}
              Reference: <code>{data.run_id}</code>
            </>
          )}
        </p>
        {actions}
      </Card>
    </section>
  );
}
