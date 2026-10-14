import { ReactNode, useEffect, useState } from "react";
import ApiStatus from "../components/ApiStatus";
import AppShell from "../components/AppShell";
import { Alert, Card, DataTable, LoadingMessage, PageHeader, ReasonLabel, Skeleton, Tag } from "../components/ui";
import { SystemCard, fetchSystemCard, waitForApi } from "../services/api";
import { evidenceHref } from "../services/evidence";

// Read-only system card (#43, redesigned in #69). All content comes from GET /api/system-card, which serves
// the existing rules and the committed evaluation snapshot (evaluation/system_card_results.json). Numbers
// are shown exactly as served; a missing value reads "Not reported" and is never filled in.

type JsonObject = Record<string, unknown>;
type Load = { status: "loading" } | { status: "error" } | { status: "ready"; card: SystemCard };

const obj = (v: unknown): JsonObject => (v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : {});
const list = (v: unknown): JsonObject[] => (Array.isArray(v) ? v.map(obj) : []);
const NOT_REPORTED = "Not reported";
const count = (v: unknown) => (typeof v === "number" ? String(v) : NOT_REPORTED);
const rate = (v: unknown) => (typeof v === "number" ? v.toFixed(2) : NOT_REPORTED);
const text = (v: unknown) => (typeof v === "string" && v ? v : NOT_REPORTED);
// "16/16 · 1.00": matched cases out of all cases, then the committed rate
const match = (c: JsonObject, matches: string, rateKey: string) =>
  typeof c[matches] === "number" && typeof c.cases === "number"
    ? `${c[matches]}/${c.cases} · ${rate(c[rateKey])}`
    : rate(c[rateKey]);
// Category codes from the #32 suite → readable labels (acronyms kept upper-case); unknown codes pass through
const humanize = (code: string) =>
  (code.charAt(0).toUpperCase() + code.slice(1).replace(/_/g, " ")).replace(/\bPhi\b/, "PHI");

const SECTIONS: Array<[string, string]> = [
  ["limitations", "Limitations"],
  ["pipeline", "Pipeline"],
  ["safety-rules", "Safety rules"],
  ["escalation-rules", "Escalation & review"],
  ["evaluation", "Evaluation"],
];

interface SystemCardPageProps {
  load?: () => Promise<SystemCard | null>; // injectable for tests
  checkApi?: typeof waitForApi; // injectable for tests (#67 cold start)
}

export default function SystemCardPage({ load = fetchSystemCard, checkApi = waitForApi }: SystemCardPageProps) {
  const [state, setState] = useState<Load>({ status: "loading" });

  useEffect(() => {
    let active = true;
    load().then((card) => {
      if (active) setState(card ? { status: "ready", card } : { status: "error" });
    });
    return () => {
      active = false;
    };
  }, [load]);

  return (
    <AppShell title="System Card" current="/system-card">
      <ApiStatus wait={checkApi} />
      <PageHeader
        title="System card"
        description="How the pipeline works, the safety and escalation rules it applies, how it was evaluated and what it cannot do."
      >
        <nav className="section-nav" aria-label="System card sections">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </nav>
      </PageHeader>
      <Alert variant="urgent" role="note" data-testid="not-a-medical-device">
        <strong>Not a medical device.</strong> Portfolio demonstration on synthetic data. Not clinically validated; no
        diagnosis, prescription or medical advice; no compliance claim.
      </Alert>

      {state.status === "loading" && (
        <>
          <LoadingMessage>Loading system card…</LoadingMessage>
          <Skeleton lines={4} />
        </>
      )}
      {state.status === "error" && (
        <Alert variant="error">The system card could not be loaded from the API. Please try again later.</Alert>
      )}
      {state.status === "ready" && <CardBody card={state.card} />}
    </AppShell>
  );
}

function Section({ id, title, children, className }: { id: string; title: string; children: ReactNode; className?: string }) {
  return (
    <Card id={id} aria-labelledby={`${id}-heading`} className={["sc-section", className].filter(Boolean).join(" ")}>
      <h2 id={`${id}-heading`}>{title}</h2>
      {children}
    </Card>
  );
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>
        <span className="stat-value">{value}</span>
        {detail && <span className="stat-detail">{detail}</span>}
      </dd>
    </div>
  );
}

function CardBody({ card }: { card: SystemCard }) {
  const evaluation = obj(card.evaluation);
  const safety = obj(evaluation.safety_escalation);
  const extraction = obj(evaluation.extraction);
  const categories = Object.entries(obj(safety.categories));
  const agg = obj(safety.aggregate);
  const ext = obj(extraction.aggregate);
  const limitations = Array.isArray(card.known_limitations) ? card.known_limitations.map(String) : [];

  return (
    <>
      <Section id="limitations" title="Known limitations" className="sc-limitations">
        {limitations.length > 0 ? (
          <ul data-testid="limitations">
            {limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">{NOT_REPORTED}</p>
        )}
        <p className="muted">{text(card.not_a_medical_device)}</p>
      </Section>

      <Section id="pipeline" title="Pipeline">
        <p data-testid="execution-mode">
          Current execution mode: <strong>{String(card.execution_mode)}</strong>
          {card.execution_mode === "mock" && " (deterministic rule-based baseline, not LLM output)"}
        </p>
        <ol className="stage-grid">
          {list(card.pipeline_stages).map((s, i) => (
            <li key={String(s.stage)}>
              <span className="flow-marker" aria-hidden="true">
                {i + 1}
              </span>
              <div>
                <strong>{String(s.stage)}</strong>
                <p>{String(s.description)}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="muted small" data-testid="webhook-condition">
          The escalation webhook is sent only when a receiver is configured on the server; it is disabled on the hosted
          demo.
        </p>
      </Section>

      <Section id="safety-rules" title="Safety rules">
        <p className="muted">Deterministic keyword/regex rules applied to the generated report.</p>
        <ul className="rule-grid">
          {list(card.safety_rules).map((r) => (
            <li key={String(r.action)}>
              <code>{String(r.action)}</code>
              <p>{String(r.description)}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="escalation-rules" title="Escalation and review rules">
        <p className="muted">Any rule that matches sets the intake to needs review with its reason code.</p>
        <ul className="rule-grid" data-testid="escalation-rules">
          {list(card.escalation_rules).map((r) => (
            <li key={String(r.reason)}>
              <ReasonLabel code={String(r.reason)} />
              <p>{String(r.rule)}</p>
            </li>
          ))}
        </ul>
        <p>
          Low-confidence threshold: <strong data-testid="threshold">{String(card.low_confidence_threshold)}</strong>{" "}
          (strictly below escalates)
        </p>
        <h3>Review</h3>
        <p data-testid="review-rules">
          Clinic staff can mark an intake that needs review as <em>reviewed</em> or <em>escalated</em>. Every other
          transition is rejected, and the original reason codes are kept as the record of why it was flagged (
          <a href={evidenceHref("docs/review_queue_api.md#allowed-transitions")}>allowed transitions</a>).
        </p>
      </Section>

      <Section id="evaluation" title="Evaluation">
        <p className="muted" data-testid="evaluation-source">
          Committed snapshot <code>evaluation/system_card_results.json</code>, generated by{" "}
          <code>{text(evaluation.source)}</code>. A backend test re-runs both suites and fails CI if these numbers drift.
        </p>

        <h3>
          Safety &amp; escalation suite (#{count(safety.issue)}) <Tag tone="info">{text(safety.mode)} mode</Tag>
        </h3>
        <dl className="stat-grid" data-testid="safety-stats">
          <Stat label="Synthetic cases" value={count(agg.cases)} />
          <Stat label="Guard match" value={rate(agg.guard_match_rate)} detail={`${count(agg.guard_matches)} of ${count(agg.cases)}`} />
          <Stat
            label="Escalation match"
            value={rate(agg.escalation_match_rate)}
            detail={`${count(agg.escalation_matches)} of ${count(agg.cases)}`}
          />
          <Stat label="Known gaps" value={count(agg.known_gaps)} detail="recorded, not fixed" />
        </dl>
        <Alert variant="warning" role="note" data-testid="safety-caveat">
          {text(safety.limitation)}
        </Alert>
        <DataTable
          label="Safety and escalation evaluation by category"
          testId="safety-table"
          layout="stack"
          rows={[...categories, ["Total", agg] as [string, unknown]]}
          rowKey={([name]) => name}
          columns={[
            {
              key: "category",
              header: "Category",
              render: ([name]) => (name === "Total" ? <strong>Total</strong> : humanize(name)),
            },
            { key: "cases", header: "Cases", numeric: true, render: ([, c]) => count(obj(c).cases) },
            {
              key: "guard",
              header: "Guard match",
              numeric: true,
              render: ([, c]) => match(obj(c), "guard_matches", "guard_match_rate"),
            },
            {
              key: "escalation",
              header: "Escalation match",
              numeric: true,
              render: ([, c]) => match(obj(c), "escalation_matches", "escalation_match_rate"),
            },
            { key: "gaps", header: "Known gaps", numeric: true, render: ([, c]) => count(obj(c).known_gaps) },
          ]}
        />

        <h3>
          Extraction suite (#{count(extraction.issue)}) <Tag tone="info">{text(extraction.mode)} mode</Tag>
        </h3>
        <p data-testid="extraction-metrics">
          {count(ext.cases)} cases · micro precision {rate(ext.micro_precision)} · micro recall {rate(ext.micro_recall)} ·
          macro precision {rate(ext.macro_precision)} · macro recall {rate(ext.macro_recall)}
        </p>
        <dl className="stat-grid" data-testid="extraction-stats">
          <Stat label="Synthetic cases" value={count(ext.cases)} />
          <Stat label="Micro precision" value={rate(ext.micro_precision)} />
          <Stat label="Micro recall" value={rate(ext.micro_recall)} />
          <Stat
            label="Symptom matches"
            value={count(ext.true_positives)}
            detail={`${count(ext.false_positives)} false positive · ${count(ext.false_negatives)} missed`}
          />
        </dl>
        <p className="muted small">
          Method: <code>{text(extraction.method)}</code>
        </p>
        <Alert variant="warning" role="note" data-testid="extraction-caveat">
          {text(extraction.limitation)}
        </Alert>
      </Section>
    </>
  );
}
