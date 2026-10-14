import { useEffect, useState } from "react";
import ApiStatus from "../components/ApiStatus";
import AppShell from "../components/AppShell";
import { Alert, Card, DataTable, LoadingMessage, PageHeader, ReasonLabel, Skeleton } from "../components/ui";
import { SystemCard, fetchSystemCard, waitForApi } from "../services/api";

// Read-only system card (#43). All content comes from GET /api/system-card, which serves the
// existing rules and the committed evaluation snapshot (evaluation/system_card_results.json).

type JsonObject = Record<string, unknown>;
type Load = { status: "loading" } | { status: "error" } | { status: "ready"; card: SystemCard };

const obj = (v: unknown): JsonObject => (v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : {});
const list = (v: unknown): JsonObject[] => (Array.isArray(v) ? v.map(obj) : []);
const rate = (v: unknown) => (typeof v === "number" ? v.toFixed(2) : "—");

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
        />
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

function CardBody({ card }: { card: SystemCard }) {
  const evaluation = obj(card.evaluation);
  const safety = obj(evaluation.safety_escalation);
  const extraction = obj(evaluation.extraction);
  const categories = Object.entries(obj(safety.categories));
  const agg = obj(safety.aggregate);
  const ext = obj(extraction.aggregate);

  return (
    <>
      <Card>
        <h2>Pipeline</h2>
        <p data-testid="execution-mode">
          Current execution mode: <strong>{String(card.execution_mode)}</strong>
          {card.execution_mode === "mock" && " (deterministic rule-based baseline, not LLM output)"}
        </p>
        <ol>
          {list(card.pipeline_stages).map((s) => (
            <li key={String(s.stage)}>
              <strong>{String(s.stage)}</strong> — {String(s.description)}
            </li>
          ))}
        </ol>
      </Card>

      <Card>
        <h2>Safety rules</h2>
        <ul>
          {list(card.safety_rules).map((r) => (
            <li key={String(r.action)}>
              <code>{String(r.action)}</code> — {String(r.description)}
            </li>
          ))}
        </ul>
        <h2>Escalation rules</h2>
        <ul data-testid="escalation-rules">
          {list(card.escalation_rules).map((r) => (
            <li key={String(r.reason)}>
              <ReasonLabel code={String(r.reason)} /> — {String(r.rule)}
            </li>
          ))}
        </ul>
        <p>
          Low-confidence threshold: <strong data-testid="threshold">{String(card.low_confidence_threshold)}</strong>{" "}
          (strictly below escalates)
        </p>
      </Card>

      <Card>
        <h2>Safety &amp; escalation evaluation (#32)</h2>
        <DataTable
          label="Safety and escalation evaluation by category"
          testId="safety-table"
          layout="stack"
          rows={[...categories, ["Total", agg] as [string, unknown]]}
          rowKey={([name]) => name}
          columns={[
            { key: "category", header: "Category", render: ([name]) => name },
            { key: "cases", header: "Cases", numeric: true, render: ([, c]) => String(obj(c).cases) },
            { key: "guard", header: "Guard rate", numeric: true, render: ([, c]) => rate(obj(c).guard_match_rate) },
            { key: "escalation", header: "Escalation rate", numeric: true, render: ([, c]) => rate(obj(c).escalation_match_rate) },
            { key: "gaps", header: "Known gaps", numeric: true, render: ([, c]) => String(obj(c).known_gaps) },
          ]}
        />
        <p className="muted">{String(safety.limitation)}</p>
      </Card>

      <Card>
        <h2>Extraction evaluation (#40)</h2>
        <p data-testid="extraction-metrics">
          {String(ext.cases)} cases · micro precision {rate(ext.micro_precision)} · micro recall {rate(ext.micro_recall)} ·
          macro precision {rate(ext.macro_precision)} · macro recall {rate(ext.macro_recall)}
        </p>
        <p className="muted">{String(extraction.limitation)}</p>
      </Card>

      <Card>
        <h2>Known limitations</h2>
        <ul>
          {(Array.isArray(card.known_limitations) ? card.known_limitations : []).map((l) => (
            <li key={String(l)}>{String(l)}</li>
          ))}
        </ul>
        <p className="muted">{String(card.not_a_medical_device)}</p>
      </Card>
    </>
  );
}
