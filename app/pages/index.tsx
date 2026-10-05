import Head from "next/head";
import { useEffect, useRef, useState } from "react";
import InputForm from "../components/InputForm";
import ReportView from "../components/ReportView";
import DeveloperTracePanel from "../components/DeveloperTracePanel";
import {
  FailureDiagnostics,
  IngestOutcome,
  IngestRequest,
  LlmMode,
  PipelineResult,
  fetchLlmMode,
  submitIntake,
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
}

export default function IntakePage({
  submit = submitIntake,
  loadLlmMode = fetchLlmMode,
}: IntakePageProps) {
  const [state, setState] = useState<PageState>({ status: "idle" });
  const [llmMode, setLlmMode] = useState<LlmMode | null>(null);
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
    <>
      <Head>
        <title>Pre-visit Intake | Healthcare AI Platform</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <header className="site-header">
        <div className="container">
          <span className="brand">Healthcare AI Platform</span>
          <span className="badges">
            {llmMode && (
              <span className="badge" data-testid="llm-mode">
                LLM Mode: {llmMode === "real" ? "Real" : "Mock"}
              </span>
            )}
            <span className="badge">Demo · synthetic data only</span>
          </span>
        </div>
      </header>

      <main className="container">
        <section className="intro">
          <h1>Pre-visit symptom intake</h1>
          <p>
            Share how you are feeling before your appointment. We will prepare a
            short, safety-checked summary so your care team can get ready for
            your visit.
          </p>
          <ol className="steps" aria-label="How it works">
            <li>Describe your symptoms</li>
            <li>We structure your intake</li>
            <li>You receive a safe summary</li>
          </ol>
        </section>

        <InputForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />

        <div aria-live="polite">
          {isSubmitting && (
            <p className="status-loading" role="status">
              Processing your intake…
            </p>
          )}

          {state.status === "error" && (
            <div
              className={`alert ${state.kind === "validation" ? "alert-warn" : "alert-error"}`}
              role="alert"
            >
              <strong>
                {state.kind === "validation"
                  ? "Please check your intake"
                  : "Something went wrong"}
              </strong>
              <p>{state.message}</p>
            </div>
          )}
        </div>

        {state.status === "success" && <ReportView data={state.data} />}

        {state.status === "success" && (
          <DeveloperTracePanel mode="success" status={state.httpStatus} data={state.data} />
        )}
        {state.status === "error" && (
          <DeveloperTracePanel mode="failure" diagnostics={state.diagnostics} />
        )}
      </main>

      <footer className="site-footer container">
        Portfolio demonstration. Not a medical device; not for real patient data.
      </footer>
    </>
  );
}
