import { RefObject, useEffect, useRef, useState } from "react";
import InputForm, { FieldError, IntakeFormValues } from "../components/InputForm";
import ReportView from "../components/ReportView";
import DeveloperTracePanel from "../components/DeveloperTracePanel";
import SubmissionProgress, { SubmissionPhase } from "../components/SubmissionProgress";
import AppShell from "../components/AppShell";
import { ApiState, ApiStatusView, Wait, useApiReadiness } from "../components/ApiStatus";
import { Alert, Button, PageHeader } from "../components/ui";
import { SCENARIO_PRESETS } from "../services/demo";
import {
  FailureDiagnostics,
  IngestErrorClass,
  LlmMode,
  PipelineResult,
  WAKE_POLICY,
  submitIntake,
  validateIntake,
  waitForApi,
} from "../services/api";

// "unavailable": the #67 wake check gave up, so the intake was never sent
type ErrorClass = IngestErrorClass | "unavailable";

type Submission =
  | { status: "idle" }
  | { status: "active"; stage: "waking" | "processing"; woke: boolean; slow: boolean }
  | { status: "success"; woke: boolean; httpStatus: number; data: PipelineResult }
  | { status: "error"; woke: boolean; errorClass: ErrorClass; message: string; diagnostics: FailureDiagnostics };

const UNAVAILABLE_MESSAGE =
  "The demo server did not respond, so your intake was not sent. Your description is kept. Please try again in a minute.";

// Per error class: title, alert tone, and the recovery action offered (#70)
const ERROR_COPY: Record<ErrorClass, { title: string; variant: "warning" | "error"; retry: string; note?: string }> = {
  validation: { title: "Please check your intake", variant: "warning", retry: "Review your description" },
  consent: { title: "Please check your intake", variant: "warning", retry: "Review consent" },
  provider: { title: "The summary service failed", variant: "error", retry: "Try again" },
  configuration: { title: "The intake service is unavailable", variant: "error", retry: "Try again" },
  server: { title: "Something went wrong", variant: "error", retry: "Try again" },
  unavailable: { title: "The demo server did not respond", variant: "error", retry: "Try again" },
  network: {
    title: "We couldn't confirm your submission",
    variant: "error",
    retry: "Send again",
    note: "Your intake may or may not have been received. Nothing is resent automatically. If you send it again unchanged and it had already been stored, this demo normally recognises the identical text and does not store it twice, but that cannot be guaranteed.",
  },
  timeout: {
    title: "We couldn't confirm your submission",
    variant: "error",
    retry: "Send again",
    note: "Your intake may still have been received. Nothing is resent automatically. If you send it again unchanged and it had already been stored, this demo normally recognises the identical text and does not store it twice, but that cannot be guaranteed.",
  },
};

const EMPTY_FORM: IntakeFormValues = { text: "", consent: false, scenarioId: null };

interface IntakePageProps {
  submit?: typeof submitIntake; // injectable for tests
  loadLlmMode?: () => Promise<LlmMode | null>; // injectable for tests; by default read from the #67 /health check
  checkApi?: Wait; // injectable for tests (#67 cold start)
  slowProcessingMs?: number; // when the "taking longer than usual" note appears
}

export default function IntakePage({
  submit = submitIntake,
  loadLlmMode,
  checkApi = waitForApi,
  slowProcessingMs = 15_000,
}: IntakePageProps) {
  // One /health poll per page (#67): it drives the cold-start notice, gates submission and reports the mode
  const readiness = useApiReadiness(checkApi);
  const [values, setValues] = useState<IntakeFormValues>(EMPTY_FORM);
  const [fieldError, setFieldError] = useState<FieldError>(null);
  const [announceFieldError, setAnnounceFieldError] = useState(true);
  const [submission, setSubmission] = useState<Submission>({ status: "idle" });
  const [loadedMode, setLoadedMode] = useState<LlmMode | null>(null);
  // Developer trace is for reviewers only and hidden by default (#43). It shows this browser's own
  // submission response, which the browser already holds; it adds no data access.
  const [showTrace, setShowTrace] = useState(false);
  const inFlight = useRef(false);

  const formHeadingRef = useRef<HTMLHeadingElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const consentRef = useRef<HTMLInputElement>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  // Move focus after the next commit, once the target is mounted and no longer disabled. A timer is not
  // enough: it can fire before React commits, while the form is still disabled from the submission.
  const focusTarget = useRef<RefObject<HTMLElement | null> | null>(null);
  const focusSoon = (ref: RefObject<HTMLElement | null>) => {
    focusTarget.current = ref;
  };
  useEffect(() => {
    const el = focusTarget.current?.current;
    if (el && !(el as HTMLInputElement).disabled) {
      el.focus();
      focusTarget.current = null;
    }
  });

  // Resolve submissions that are waiting for the server to wake once the readiness check settles
  const readinessRef = useRef<ApiState>(readiness.state);
  const waiters = useRef<((r: "ready" | "unavailable") => void)[]>([]);
  useEffect(() => {
    readinessRef.current = readiness.state;
    const s = readiness.state.status;
    if (s === "ready" || s === "unavailable") waiters.current.splice(0).forEach((resolve) => resolve(s));
  }, [readiness.state]);

  function serverReady(): Promise<"ready" | "unavailable"> {
    const s = readinessRef.current.status;
    if (s === "ready") return Promise.resolve("ready");
    // A failed wake is re-checked once per explicit submission, never in the background
    if (s === "unavailable") readiness.retry();
    return new Promise((resolve) => waiters.current.push(resolve));
  }

  // Display-only: the mode is configured on the server (LLM_MODE) and cannot be changed here
  useEffect(() => {
    if (!loadLlmMode) return;
    let active = true;
    loadLlmMode().then((mode) => {
      if (active) setLoadedMode(mode);
    });
    return () => {
      active = false;
    };
  }, [loadLlmMode]);
  const healthMode = readiness.state.status === "ready" ? readiness.state.health?.llmMode : null;
  const llmMode: LlmMode | null =
    loadedMode ?? (healthMode === "mock" || healthMode === "real" ? healthMode : null);

  async function attemptSubmit() {
    // Guard against double submission even if the click lands before re-render
    if (inFlight.current) return;

    const req = { text: values.text, consent_granted: values.consent };
    const error = validateIntake(req);
    if (error) {
      setFieldError({ field: "symptoms", message: error });
      setAnnounceFieldError(true);
      textRef.current?.focus();
      return;
    }

    inFlight.current = true;
    setFieldError(null);
    setShowTrace(false);
    let slowTimer: ReturnType<typeof setTimeout> | undefined;
    try {
      const woke = readinessRef.current.status !== "ready";
      if (woke) {
        // Stage 1: nothing is sent until GET /health answers, so no POST can hit a sleeping server
        setSubmission({ status: "active", stage: "waking", woke, slow: false });
        if ((await serverReady()) === "unavailable") {
          setSubmission({
            status: "error",
            woke,
            errorClass: "unavailable",
            message: UNAVAILABLE_MESSAGE,
            diagnostics: { note: "GET /health did not answer within the wake window; POST /api/ingest was not sent." },
          });
          focusSoon(errorRef);
          return;
        }
      }

      // Stage 2 starts only as the request is made
      setSubmission({ status: "active", stage: "processing", woke, slow: false });
      slowTimer = setTimeout(
        () => setSubmission((s) => (s.status === "active" ? { ...s, slow: true } : s)),
        slowProcessingMs,
      );
      const outcome = await submit(req);

      if (outcome.kind === "success") {
        setSubmission({ status: "success", woke, httpStatus: outcome.status, data: outcome.data });
        focusSoon(resultHeadingRef);
        return;
      }
      setSubmission({
        status: "error",
        woke,
        errorClass: outcome.errorClass,
        message: outcome.message,
        diagnostics: outcome.diagnostics,
      });
      if (outcome.kind === "validation") {
        // The page alert announces the message; the field is marked and described by it
        setFieldError({ field: outcome.errorClass === "consent" ? "consent" : "symptoms", message: outcome.message });
        setAnnounceFieldError(false);
        focusSoon(outcome.errorClass === "consent" ? consentRef : textRef);
      } else {
        focusSoon(errorRef);
      }
    } finally {
      clearTimeout(slowTimer);
      inFlight.current = false;
    }
  }

  function startNewIntake() {
    if (inFlight.current) return;
    // Clears this page only; records already submitted stay on the server
    setValues(EMPTY_FORM);
    setFieldError(null);
    setSubmission({ status: "idle" });
    setShowTrace(false);
    focusSoon(formHeadingRef);
  }

  function recover(errorClass: ErrorClass) {
    if (errorClass === "validation") textRef.current?.focus();
    else if (errorClass === "consent") consentRef.current?.focus();
    else attemptSubmit();
  }

  const isSubmitting = submission.status === "active";
  let phase: SubmissionPhase | null = null;
  if (submission.status === "active" && submission.stage === "waking") {
    const s = readiness.state;
    phase = s.status === "waking"
      ? { stage: "waking", attempt: s.attempt, maxAttempts: s.maxAttempts }
      : { stage: "waking", attempt: 1, maxAttempts: WAKE_POLICY.maxAttempts };
  } else if (submission.status === "active") {
    phase = { stage: "processing", slow: submission.slow };
  } else if (submission.status === "success") {
    phase = { stage: "done" };
  }

  const newIntakeButton = (
    <Button onClick={startNewIntake} disabled={isSubmitting}>
      Start a new intake
    </Button>
  );

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
      {/* While a submission waits for the server, its own progress explains the wake */}
      {!isSubmitting && <ApiStatusView state={readiness.state} retry={readiness.retry} />}
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

      <InputForm
        values={values}
        onChange={(v) => {
          setValues(v);
          if (fieldError?.field === "symptoms" && v.text !== values.text) setFieldError(null);
          if (fieldError?.field === "consent" && v.consent !== values.consent) setFieldError(null);
        }}
        onSubmit={attemptSubmit}
        isSubmitting={isSubmitting}
        fieldError={fieldError}
        announceFieldError={announceFieldError}
        presets={SCENARIO_PRESETS}
        headingRef={formHeadingRef}
        textRef={textRef}
        consentRef={consentRef}
      />

      {phase && <SubmissionProgress phase={phase} woke={submission.status !== "idle" && submission.woke} />}

      {submission.status === "error" && (
        <Alert
          ref={errorRef}
          tabIndex={-1}
          variant={ERROR_COPY[submission.errorClass].variant}
          role="alert"
          title={ERROR_COPY[submission.errorClass].title}
          data-testid="intake-error"
          data-error-class={submission.errorClass}
        >
          <p>{submission.message}</p>
          {ERROR_COPY[submission.errorClass].note && <p>{ERROR_COPY[submission.errorClass].note}</p>}
          <p className="muted small">Your description and your consent choice have been kept.</p>
          <div className="button-row">
            <Button
              variant="primary"
              onClick={() => recover(submission.errorClass)}
              disabled={isSubmitting}
              data-testid="error-recovery"
            >
              {ERROR_COPY[submission.errorClass].retry}
            </Button>
            {newIntakeButton}
          </div>
        </Alert>
      )}

      {submission.status === "success" && (
        <ReportView
          data={submission.data}
          headingRef={resultHeadingRef}
          actions={<div className="button-row">{newIntakeButton}</div>}
        />
      )}

      {(submission.status === "success" || submission.status === "error") && (
        <label className="checkbox reviewer-toggle">
          <input type="checkbox" checked={showTrace} onChange={(e) => setShowTrace(e.target.checked)} />
          <span>Reviewer / developer: show the pipeline trace for this submission</span>
        </label>
      )}
      {showTrace && submission.status === "success" && (
        <DeveloperTracePanel mode="success" status={submission.httpStatus} data={submission.data} />
      )}
      {showTrace && submission.status === "error" && (
        <DeveloperTracePanel mode="failure" diagnostics={submission.diagnostics} />
      )}
    </AppShell>
  );
}
