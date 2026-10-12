import Head from "next/head";
import { useEffect, useState } from "react";
import SiteNav from "../components/SiteNav";
import { SystemCard, fetchSystemCard } from "../services/api";

// Read-only system card (#43). All content comes from GET /api/system-card, which serves the
// existing rules and the committed evaluation snapshot (evaluation/system_card_results.json).

type JsonObject = Record<string, unknown>;
type Load = { status: "loading" } | { status: "error" } | { status: "ready"; card: SystemCard };

const obj = (v: unknown): JsonObject => (v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : {});
const list = (v: unknown): JsonObject[] => (Array.isArray(v) ? v.map(obj) : []);
const rate = (v: unknown) => (typeof v === "number" ? v.toFixed(2) : "—");

interface SystemCardPageProps {
  load?: () => Promise<SystemCard | null>; // injectable for tests
}

export default function SystemCardPage({ load = fetchSystemCard }: SystemCardPageProps) {
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
    <>
      <Head>
        <title>System Card | Healthcare AI Platform</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <header className="site-header">
        <div className="container">
          <span className="brand">Healthcare AI Platform · System card</span>
          <span className="badges">
            <span className="badge">Demo · synthetic data only</span>
          </span>
        </div>
        <div className="container">
          <SiteNav current="/system-card" />
        </div>
      </header>

      <main className="container">
        <div className="alert alert-urgent" role="note" data-testid="not-a-medical-device">
          <strong>Not a medical device.</strong> Portfolio demonstration on synthetic data. Not clinically validated; no
          diagnosis, prescription or medical advice; no compliance claim.
        </div>

        {state.status === "loading" && (
          <p className="status-loading" role="status">
            Loading system card…
          </p>
        )}
        {state.status === "error" && (
          <div className="alert alert-error" role="alert">
            The system card could not be loaded from the API. Please try again later.
          </div>
        )}
        {state.status === "ready" && <CardBody card={state.card} />}
      </main>

      <footer className="site-footer container">
        Portfolio demonstration. Not a medical device; not for real patient data.
      </footer>
    </>
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
      <section className="card">
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
      </section>

      <section className="card">
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
              <code>{String(r.reason)}</code> — {String(r.rule)}
            </li>
          ))}
        </ul>
        <p>
          Low-confidence threshold: <strong data-testid="threshold">{String(card.low_confidence_threshold)}</strong>{" "}
          (strictly below escalates)
        </p>
      </section>

      <section className="card">
        <h2>Safety &amp; escalation evaluation (#32)</h2>
        <table data-testid="safety-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Cases</th>
              <th>Guard rate</th>
              <th>Escalation rate</th>
              <th>Known gaps</th>
            </tr>
          </thead>
          <tbody>
            {[...categories, ["Total", agg] as [string, unknown]].map(([name, c]) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{String(obj(c).cases)}</td>
                <td>{rate(obj(c).guard_match_rate)}</td>
                <td>{rate(obj(c).escalation_match_rate)}</td>
                <td>{String(obj(c).known_gaps)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted">{String(safety.limitation)}</p>
      </section>

      <section className="card">
        <h2>Extraction evaluation (#40)</h2>
        <p data-testid="extraction-metrics">
          {String(ext.cases)} cases · micro precision {rate(ext.micro_precision)} · micro recall {rate(ext.micro_recall)} ·
          macro precision {rate(ext.macro_precision)} · macro recall {rate(ext.macro_recall)}
        </p>
        <p className="muted">{String(extraction.limitation)}</p>
      </section>

      <section className="card">
        <h2>Known limitations</h2>
        <ul>
          {(Array.isArray(card.known_limitations) ? card.known_limitations : []).map((l) => (
            <li key={String(l)}>{String(l)}</li>
          ))}
        </ul>
        <p className="muted">{String(card.not_a_medical_device)}</p>
      </section>
    </>
  );
}
