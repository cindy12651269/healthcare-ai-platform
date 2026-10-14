import { useEffect, useRef, useState } from "react";
import InputForm from "../components/InputForm";
import ReportView from "../components/ReportView";
import DeveloperTracePanel from "../components/DeveloperTracePanel";
import AppShell from "../components/AppShell";
import { Alert, LoadingMessage, PageHeader } from "../components/ui";
import ApiStatus from "../components/ApiStatus";
import { SCENARIO_PRESETS } from "../services/demo";
import {
  FailureDiagnostics,
  IngestOutcome,
  IngestRequest,
  LlmMode,
  PipelineResult,
  fetchLlmMode,
  submitIntake,
  waitForApi,
} from "../services/api";

type PageState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; httpStatus: number; data: PipelineResult }
  | {
      status: "error";
      kind: "validation" | "failure";
      message: string;
      diagnostics: FailureDiagnostics;
    };

function toPageState(outcome: IngestOutcome): PageState {
  if (outcome.kind === "success") {
    return { status: "success", httpStatus: outcome.status, data: outcome.data };
  }
  return {
    status: "error",
    kind: outcome.kind,
    message: outcome.message,
    diagnostics: outcome.diagnostics,
  };
}

interface IntakePageProps {
  submit?: typeof submitIntake; // injectable for tests
  loadLlmMode?: () => Promise<LlmMode | null>; // injectable for tests
  checkApi?: typeof waitForApi; // injectable for tests (#67 cold start)
}

export default function IntakePage({
  submit = submitIntake,
  loadLlmMode = fetchLlmMode,
  checkApi = waitForApi,
}: IntakePageProps) {
  const [state, setState] = useState<PageState>({ status: "idle" });
  const [llmMode, setLlmMode] = useState<LlmMode | null>(null);
  // Developer trace is for reviewers only and hidden by default (#43). It shows this browser's own
  // submission response, which the browser already holds; it adds no data access.
  const [showTrace, setShowTrace] = useState(false);
  const inFlight = useRef(false);

  // Display-only: the mode is configured on the server (LLM_MODE) and cannot be changed here
  useEffect(() => {
    let active = true;
    loadLlmMode().then((mode) => {
      if (active) setLlmMode(mode);
    });
    return () => {
      active = false;
    };
  }, [loadLlmMode]);

  async function handleSubmit(req: IngestRequest) {
    // Guard against double submission even if the click lands before re-render
    if (inFlight.current) return;
    inFlight.current = true;
    setState({ status: "loading" });
    try {
      setState(toPageState(await submit(req)));
    } finally {
      inFlight.current = false;
    }
  }

  const isSubmitting = state.status === "loading";

  return (
    <AppShell
      title="Pre-visit Intake"
      current="/intake"
      indicators={
        llmMode && (
          <span className="badge" data-testid="llm-mode">
            LLM Mode: {llmMode === "real" ? "Real" : "Mock"}
          </span>
        )
      }
    >
        <ApiStatus wait={checkApi} />
        <PageHeader
          title="Pre-visit symptom intake"
          description="Share how you are feeling before your appointment. We will prepare a short, safety-checked summary so your care team can get ready for your visit."
        >
          <ol className="steps" aria-label="How it works">
            <li>Describe your symptoms</li>
            <li>We structure your intake</li>
            <li>You receive a safe summary</li>
          </ol>
        </PageHeader>

        <InputForm onSubmit={handleSubmit} isSubmitting={isSubmitting} presets={SCENARIO_PRESETS} />

        <div aria-live="polite">
          {isSubmitting && <LoadingMessage>Processing your intake…</LoadingMessage>}

          {state.status === "error" && (
            <Alert
              variant={state.kind === "validation" ? "warning" : "error"}
              role="alert"
              title={state.kind === "validation" ? "Please check your intake" : "Something went wrong"}
            >
              <p>{state.message}</p>
            </Alert>
          )}
        </div>

        {state.status === "success" && <ReportView data={state.data} />}

        {(state.status === "success" || state.status === "error") && (
          <label className="checkbox reviewer-toggle">
            <input type="checkbox" checked={showTrace} onChange={(e) => setShowTrace(e.target.checked)} />
            <span>Reviewer / developer: show the pipeline trace for this submission</span>
          </label>
        )}
        {showTrace && state.status === "success" && (
          <DeveloperTracePanel mode="success" status={state.httpStatus} data={state.data} />
        )}
        {showTrace && state.status === "error" && (
          <DeveloperTracePanel mode="failure" diagnostics={state.diagnostics} />
        )}
    </AppShell>
  );
}
