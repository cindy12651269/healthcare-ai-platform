import { ReactNode, useEffect, useState } from "react";
import { Alert, LoadingMessage, ReasonLabel, ReasonList, StatusBadge } from "./ui";
import { IntakeTimeline, RecordedMatch, StaffApi, TimelineEvent } from "../services/staffApi";
import { formatStaffDateTime } from "../services/format";

// "Why flagged" evidence and review timeline for one intake (#41). Shows persisted data only:
// recorded guard matches are highlighted where they literally occur in the original input;
// extracted fields are labelled as derived. No model reasoning is shown because none is stored.

type JsonObject = Record<string, unknown>;
type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: IntakeTimeline };

const EVENT_LABELS: Record<TimelineEvent["kind"], string> = {
  submitted: "Submitted",
  processed: "Processed",
  safety_evaluated: "Safety evaluated",
  escalation_decision: "Escalation decision",
  webhook_delivery: "Webhook delivery",
  staff_transition: "Staff action",
};

const show = (v: unknown): string => {
  if (v === null || v === undefined || v === "") return "Not recorded";
  if (Array.isArray(v)) return v.length ? v.map(show).join(", ") : "None";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};

const when = (at: string | null) => formatStaffDateTime(at, "Time not recorded");

// Splits the input into plain and highlighted parts for each recorded match found in it (case-insensitive)
export function highlightMatches(text: string, matches: RecordedMatch[]): ReactNode[] {
  const needles = matches.filter((m) => m.found_in_input).map((m) => m.match.toLowerCase());
  const lower = text.toLowerCase();
  const ranges: Array<[number, number]> = [];
  for (const needle of needles) {
    for (let i = lower.indexOf(needle); i !== -1 && needle; i = lower.indexOf(needle, i + needle.length)) {
      ranges.push([i, i + needle.length]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const parts: ReactNode[] = [];
  let pos = 0;
  for (const [start, end] of ranges) {
    if (start < pos) continue; // overlapping match already highlighted
    if (start > pos) parts.push(text.slice(pos, start));
    parts.push(
      <mark key={start} data-testid="recorded-match">
        {text.slice(start, end)}
      </mark>,
    );
    pos = end;
  }
  if (pos < text.length) parts.push(text.slice(pos));
  return parts;
}

function EventDetails({ event }: { event: TimelineEvent }) {
  const d = event.details as JsonObject;
  switch (event.kind) {
    case "submitted":
      return null;
    case "processed":
      return (
        <>
          Mode {show(d.execution_mode)} · model {show(d.model_version)} · prompt {show(d.prompt_version)} · pipeline{" "}
          {show(d.pipeline_version)} · run {show(d.run_id)}
        </>
      );
    case "safety_evaluated":
      return (
        <>
          Actions {show(d.actions)} · reason types {show(d.reason_types)} · severity {show(d.severity)}
        </>
      );
    case "escalation_decision":
      return d.required ? (
        <>
          Escalated: <ReasonList reasons={Array.isArray(d.reasons) ? d.reasons.map(String) : null} empty="Not recorded" />
        </>
      ) : (
        <>Not escalated</>
      );
    case "webhook_delivery":
      return (
        <>
          {show(d.event_type)}: {show(d.status)} after {show(d.attempts)} attempt(s)
          {d.last_http_status ? ` · last HTTP ${d.last_http_status}` : ""}
          {d.last_error ? ` · last error ${d.last_error}` : ""}
        </>
      );
    case "staff_transition":
      return (
        <>
          {show(d.actor_id)}: <StatusBadge status={show(d.from_status)} /> → <StatusBadge status={show(d.to_status)} />
        </>
      );
  }
}

export default function IntakeEvidence({
  api,
  token,
  clinicId,
  intakeId,
  onAuthError,
}: {
  api: StaffApi;
  token: string;
  clinicId: string;
  intakeId: string;
  onAuthError: (kind: string) => void;
}) {
  const [state, setState] = useState<Load>({ status: "loading" });

  useEffect(() => {
    let active = true;
    api.getIntakeTimeline(token, clinicId, intakeId).then((result) => {
      if (!active) return;
      if (result.ok) {
        setState({ status: "ready", data: result.data });
      } else {
        onAuthError(result.kind);
        setState({ status: "error", message: result.message });
      }
    });
    return () => {
      active = false;
    };
  }, [api, token, clinicId, intakeId, onAuthError]);

  if (state.status === "loading") {
    return <LoadingMessage>Loading evidence and timeline…</LoadingMessage>;
  }
  if (state.status === "error") {
    return (
      <Alert variant="error" data-testid="timeline-error">
        Evidence and timeline could not be loaded. {state.message}
      </Alert>
    );
  }

  const { evidence, events, notes } = state.data;
  const extracted = evidence.extracted;
  const unmatched = evidence.recorded_matches.filter((m) => !m.found_in_input);

  return (
    <>
      <section aria-labelledby="why-flagged-heading">
        <h3 id="why-flagged-heading">Why flagged</h3>
        {evidence.escalation_rules.length === 0 ? (
          <p className="muted" data-testid="no-escalation">
            No escalation rule was triggered for this intake.
          </p>
        ) : (
          <ul data-testid="escalation-rules">
            {evidence.escalation_rules.map((r) => (
              <li key={r.reason}>
                <strong>{r.rule}</strong> <ReasonLabel code={r.reason} />
                <div className="muted">Recorded evidence: {show(r.evidence)}</div>
              </li>
            ))}
          </ul>
        )}

        <div className="evidence-grid">
          <div>
            <h4>Original input</h4>
            {evidence.original_input ? (
              <p data-testid="original-input">{highlightMatches(evidence.original_input, evidence.recorded_matches)}</p>
            ) : (
              <p className="muted">Original input is not available for this intake.</p>
            )}
            <p className="muted">
              Highlighted: phrases the safety guard recorded that also appear in this input.
              {unmatched.length > 0 &&
                ` Other recorded matches (from the generated report, not the input): ${unmatched
                  .map((m) => m.match)
                  .join(", ")}.`}
            </p>
          </div>
          <div>
            <h4>Extracted fields (derived, not recorded matches)</h4>
            <dl className="kv" data-testid="extracted-fields">
              <dt>Symptoms</dt>
              <dd>{show(extracted.symptoms)}</dd>
              <dt>Duration</dt>
              <dd>{show(extracted.duration)}</dd>
              <dt>Onset</dt>
              <dd>{show(extracted.onset)}</dd>
              <dt>Severity</dt>
              <dd>{show(extracted.severity)}</dd>
              <dt>Red flags</dt>
              <dd>{show(extracted.red_flags)}</dd>
              <dt>Confidence</dt>
              <dd>{show(extracted.confidence_level)}</dd>
            </dl>
          </div>
        </div>

        <h4>Processing provenance</h4>
        <dl className="kv" data-testid="provenance">
          <dt>Execution mode</dt>
          <dd>{show(evidence.provenance.execution_mode)}</dd>
          <dt>Model version</dt>
          <dd>{show(evidence.provenance.model_version)}</dd>
          <dt>Prompt version</dt>
          <dd>{show(evidence.provenance.prompt_version)}</dd>
          <dt>Pipeline version</dt>
          <dd>{show(evidence.provenance.pipeline_version)}</dd>
          <dt>Run ID</dt>
          <dd>{show(evidence.provenance.run_id)}</dd>
        </dl>
      </section>

      <section aria-labelledby="timeline-heading">
        <h3 id="timeline-heading">Timeline</h3>
        {events.length === 0 ? (
          <p className="muted">No events have been recorded for this intake.</p>
        ) : (
          <ol className="timeline timeline-vertical" data-testid="timeline">
            {events.map((e, i) => (
              <li key={`${e.kind}-${i}`} data-kind={e.kind}>
                <span className="timeline-marker" aria-hidden="true" />
                <div className="timeline-body">
                  <strong>{EVENT_LABELS[e.kind]}</strong>{" "}
                  <time className="muted" dateTime={e.at ?? undefined}>
                    {when(e.at)}
                  </time>
                  <div>
                    <EventDetails event={e} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
        {/* Only recorded deliveries are shown; their absence is stated, never read as "sent" or "disabled" */}
        {events.length > 0 && !events.some((e) => e.kind === "webhook_delivery") && (
          <p className="muted small" data-testid="no-webhook-delivery">
            No webhook delivery is recorded for this intake.
          </p>
        )}
        {notes.map((n) => (
          <p key={n} className="muted" data-testid="timeline-note">
            {n}
          </p>
        ))}
      </section>
    </>
  );
}
