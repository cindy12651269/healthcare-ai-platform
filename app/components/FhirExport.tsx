import { useState } from "react";
import { StaffApi } from "../services/staffApi";

// FHIR R4 export (#42): fetched on demand (each export is audited), previewed as JSON and
// downloadable as a file. The Bundle contains the raw intake text; synthetic demo data only.

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; json: string; entries: number };

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
    setState({ status: "ready", json: JSON.stringify(result.data, null, 2), entries });
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
    <section aria-labelledby="fhir-heading">
      <h3 id="fhir-heading">FHIR R4 export</h3>
      <p className="badge" data-testid="fhir-label">
        FHIR R4 — Synthetic Demo Data
      </p>
      <p className="muted">
        Bundle (collection) with QuestionnaireResponse, Task, Provenance, Organization, Device and Questionnaire. It
        contains the original intake text; a downloaded file leaves the platform&apos;s access control.
      </p>
      <button type="button" className="primary" onClick={load} disabled={state.status === "loading"}>
        {state.status === "ready" ? "Reload FHIR export" : "Load FHIR export"}
      </button>

      {state.status === "idle" && <p className="muted">No export loaded yet.</p>}
      {state.status === "loading" && (
        <p className="status-loading" role="status">
          Building FHIR export…
        </p>
      )}
      {state.status === "error" && (
        <div className="alert alert-error" role="alert" data-testid="fhir-error">
          FHIR export failed. {state.message}
        </div>
      )}
      {state.status === "ready" &&
        (state.entries === 0 ? (
          <p className="muted">The export contains no resources.</p>
        ) : (
          <>
            <button type="button" onClick={() => download(state.json)}>
              Download JSON
            </button>
            <pre className="json-preview" data-testid="fhir-preview">
              {state.json}
            </pre>
          </>
        ))}
    </section>
  );
}
