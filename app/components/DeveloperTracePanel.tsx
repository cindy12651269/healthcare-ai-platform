import { useState } from "react";
import { FailureDiagnostics, PipelineResult } from "../services/api";

type JsonObject = Record<string, unknown>;

const asObject = (v: unknown): JsonObject | null =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : null;

// Stage keys emitted by observability/metrics.py::build_run_metrics
const STAGE_METRICS: [string, string][] = [
  ["intake_ms", "Intake"],
  ["structuring_ms", "Structuring"],
  ["retrieval_ms", "Retrieval"],
  ["output_ms", "Report generation"],
  ["safety_ms", "Safety"],
  ["persistence_ms", "Persistence"],
  ["latency_ms", "Total"],
];

const NOT_RETURNED = "Not returned by the API for this run.";

const formatMs = (v: unknown) =>
  typeof v === "number" ? `${v.toFixed(1)} ms` : "—";

const yesNo = (v: unknown) => (v === true ? "yes" : v === false ? "no" : "—");

type DeveloperTracePanelProps =
  | { mode: "success"; status: number; data: PipelineResult }
  | { mode: "failure"; diagnostics: FailureDiagnostics };

// Read-only developer evidence. Collapsed by default so it never competes with the patient workflow.
export default function DeveloperTracePanel(props: DeveloperTracePanelProps) {
  const raw = props.mode === "success" ? props.data : props.diagnostics;
  const json = JSON.stringify(raw, null, 2);
  const [copied, setCopied] = useState(false);

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <details className="dev-panel">
      <summary>Developer trace</summary>
      <p className="muted small">
        Read-only diagnostics from the backend response, for reviewers and
        developers. Pipeline settings (RAG, persistence, LLM mode) are server
        configuration and cannot be changed here.
      </p>

      {props.mode === "failure" ? (
        <FailureSection diagnostics={props.diagnostics} />
      ) : (
        <SuccessSections status={props.status} data={props.data} />
      )}

      <section className="dev-section">
        <div className="dev-section-header">
          <h4>{props.mode === "success" ? "Response JSON" : "Error JSON"}</h4>
          <button type="button" className="secondary small" onClick={copyJson}>
            {copied ? "Copied" : "Copy JSON"}
          </button>
        </div>
        <pre className="json" data-testid="raw-json">
          {json}
        </pre>
      </section>
    </details>
  );
}

function FailureSection({ diagnostics }: { diagnostics: FailureDiagnostics }) {
  return (
    <section className="dev-section">
      <h4>Request failure</h4>
      <dl className="kv">
        <dt>HTTP status</dt>
        <dd>{diagnostics.status ?? "no response"}</dd>
        {diagnostics.note && (
          <>
            <dt>Note</dt>
            <dd>{diagnostics.note}</dd>
          </>
        )}
      </dl>
    </section>
  );
}

function SuccessSections({ status, data }: { status: number; data: PipelineResult }) {
  const metrics = asObject(data.metrics);
  const rag = asObject(data.rag);
  const safety = asObject(data.safety);
  const safetyChecks = asObject(asObject(data.report)?.safety_checks);
  const chunks = Array.isArray(rag?.chunks) ? (rag!.chunks as unknown[]) : [];

  return (
    <>
      <section className="dev-section">
        <h4>Run</h4>
        <dl className="kv">
          <dt>Run ID</dt>
          <dd><code>{data.run_id ?? "—"}</code></dd>
          <dt>HTTP status</dt>
          <dd>{status}</dd>
          <dt>Pipeline success</dt>
          <dd>{yesNo(data.success)}</dd>
        </dl>
      </section>

      <section className="dev-section" data-testid="metrics-section">
        <h4>Latency / stage metrics</h4>
        {metrics ? (
          <table className="metrics">
            <tbody>
              {STAGE_METRICS.map(([key, label]) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  <td>{formatMs(metrics[key])}</td>
                </tr>
              ))}
              <tr>
                <th scope="row">Retrieval hits</th>
                <td>{String(metrics.retrieval_hit_count ?? "—")}</td>
              </tr>
              <tr>
                <th scope="row">Safety violations</th>
                <td>{String(metrics.safety_violation_count ?? "—")}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="muted small">{NOT_RETURNED}</p>
        )}
      </section>

      <section className="dev-section" data-testid="retrieval-section">
        <h4>Retrieval trace</h4>
        {rag ? (
          <>
            <dl className="kv">
              <dt>Enabled (server config)</dt>
              <dd>{yesNo(rag.enabled)}</dd>
              <dt>Used</dt>
              <dd>{yesNo(rag.used)}</dd>
              <dt>Query</dt>
              <dd>{typeof rag.query === "string" && rag.query ? rag.query : "—"}</dd>
              <dt>Top K</dt>
              <dd>{String(rag.top_k ?? "—")}</dd>
              <dt>Chunks</dt>
              <dd>{chunks.length}</dd>
              {typeof rag.error === "string" && rag.error && (
                <>
                  <dt>Error</dt>
                  <dd>{rag.error}</dd>
                </>
              )}
            </dl>
            {chunks.length > 0 && (
              <ol className="chunks">
                {chunks.map((c, i) => (
                  <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                ))}
              </ol>
            )}
          </>
        ) : (
          <p className="muted small">{NOT_RETURNED}</p>
        )}
      </section>

      <section className="dev-section" data-testid="safety-section">
        <h4>Safety trace</h4>
        {safety || safetyChecks ? (
          <>
            {safety && (
              <dl className="kv">
                <dt>Allowed</dt>
                <dd>{yesNo(safety.allowed)}</dd>
                <dt>Severity</dt>
                <dd>{String(safety.severity ?? "—")}</dd>
                <dt>Actions</dt>
                <dd>
                  {Array.isArray(safety.actions) && safety.actions.length
                    ? safety.actions.join(", ")
                    : "none"}
                </dd>
                <dt>Reasons</dt>
                <dd>
                  {Array.isArray(safety.reasons) ? safety.reasons.length : 0}
                </dd>
              </dl>
            )}
            {safetyChecks && (
              <>
                <h5>Report safety checks</h5>
                <pre className="json">{JSON.stringify(safetyChecks, null, 2)}</pre>
              </>
            )}
          </>
        ) : (
          <p className="muted small">{NOT_RETURNED}</p>
        )}
      </section>
    </>
  );
}
