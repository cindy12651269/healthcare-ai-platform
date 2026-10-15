import { useState } from "react";
import { StaffApi } from "../services/staffApi";
import { Alert, Button, LoadingMessage, Tag } from "./ui";

// FHIR R4 export (#42, panel redesigned in #71): fetched on demand (each export is audited), summarised
// by resource type, previewed as collapsible JSON and downloadable as a file. Payload and endpoint are
// unchanged. The Bundle contains the raw intake text; synthetic demo data only.

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; json: string; resources: Array<[string, number]>; entries: number };

// The resource types the export is documented to contain (docs/interoperability/fhir_mapping.md)
const EXPECTED = ["QuestionnaireResponse", "Questionnaire", "Task", "Organization", "Device", "Provenance"];

function summarise(bundle: Record<string, unknown>): Array<[string, number]> {
  const counts = new Map<string, number>();
  const entries = Array.isArray(bundle.entry) ? bundle.entry : [];
  for (const e of entries) {
    const type = (e as { resource?: { resourceType?: unknown } })?.resource?.resourceType;
    const key = typeof type === "string" ? type : "Unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()];
}

export default function FhirExport({
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
  const [state, setState] = useState<State>({ status: "idle" });

  async function load() {
    if (state.status === "loading") return;
    setState({ status: "loading" });
    const result = await api.exportIntakeFhir(token, clinicId, intakeId);
    if (!result.ok) {
      onAuthError(result.kind);
      setState({ status: "error", message: result.message });
      return;
    }
    const entries = Array.isArray(result.data.entry) ? result.data.entry.length : 0;
    setState({ status: "ready", json: JSON.stringify(result.data, null, 2), resources: summarise(result.data), entries });
  }

  function download(json: string) {
    const url = URL.createObjectURL(new Blob([json], { type: "application/fhir+json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `intake-${intakeId}-fhir-r4.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section aria-labelledby="fhir-heading" className="fhir-panel">
      <h3 id="fhir-heading">FHIR R4 export</h3>
      <p className="badge" data-testid="fhir-label">
        FHIR R4 — Synthetic Demo Data
      </p>
      <p className="muted" data-testid="fhir-disclaimer">
        Synthetic demo data, export only: a Bundle (collection) with {EXPECTED.join(", ")}. It is not a FHIR
        conformance or certification claim, and nothing is sent to a FHIR server. It contains the original intake
        text; a downloaded file leaves the platform&apos;s access control.
      </p>
      <Button variant="primary" onClick={load} disabled={state.status === "loading"}>
        {state.status === "ready" ? "Reload FHIR export" : "Load FHIR export"}
      </Button>

      {state.status === "idle" && <p className="muted">No export loaded yet.</p>}
      {state.status === "loading" && <LoadingMessage>Building FHIR export…</LoadingMessage>}
      {state.status === "error" && (
        <Alert variant="error" data-testid="fhir-error">
          FHIR export failed. {state.message}
        </Alert>
      )}
      {state.status === "ready" &&
        (state.entries === 0 ? (
          <p className="muted">The export contains no resources.</p>
        ) : (
          <>
            <h4>Resources in this export</h4>
            <ul className="fhir-resources" data-testid="fhir-resources">
              {state.resources.map(([type, n]) => (
                <li key={type}>
                  <Tag tone="info">{type}</Tag> × {n}
                </li>
              ))}
            </ul>
            <div className="button-row">
              <Button onClick={() => download(state.json)}>Download JSON</Button>
            </div>
            <details className="fhir-json">
              <summary>JSON preview ({state.entries} entries)</summary>
              <pre className="json-preview" data-testid="fhir-preview">
                {state.json}
              </pre>
            </details>
          </>
        ))}
    </section>
  );
}
