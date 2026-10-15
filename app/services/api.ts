// Thin client for the FastAPI `/api/ingest` endpoint.
// Only the public API base URL is read from the environment; no credentials ever live in browser code.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const MIN_TEXT_LENGTH = 10; // mirrors agents/intake_agent.py
export const MAX_TEXT_LENGTH = 5000;

const DEFAULT_TIMEOUT_MS = 60_000;

type JsonObject = Record<string, unknown>;

export interface IngestRequest {
  text: string;
  consent_granted: boolean;
}

// Shape of the pipeline trace returned by `HealthcarePipeline.run()` (agents/pipeline.py).
// Fields are optional because the backend does not apply a response model.
export interface PipelineResult {
  run_id?: string;
  success: boolean;
  intake?: JsonObject | null;
  structured?: JsonObject | null;
  rag?: JsonObject | null;
  report?: JsonObject | null;
  safety?: JsonObject | null;
  escalation?: JsonObject | null; // #29: required, review_status, reasons (codes only)
  persistence?: JsonObject | null; // status: saved | duplicate | disabled | skipped | failed
  errors?: unknown[];
  telemetry?: JsonObject | null;
  metrics?: Record<string, number> | null;
}

// Developer-only diagnostics for a failed request; rendered only in the trace panel.
export interface FailureDiagnostics {
  status?: number;
  body?: unknown;
  note?: string;
}

// Why a submission failed (#70), so the page can offer the right recovery. "network" and "timeout" are
// ambiguous: the request may have reached the API, so they are never retried automatically.
export type IngestErrorClass =
  | "validation" // 400 / 422 list: the input was rejected
  | "consent" // 400: personal details found without consent
  | "provider" // 502: the model provider failed
  | "configuration" // 503: the service is not configured or unavailable
  | "server" // 500, 422 string, or 200 without success
  | "network" // no readable HTTP response
  | "timeout"; // aborted after the client timeout

export type IngestOutcome =
  | { kind: "success"; status: number; data: PipelineResult }
  | { kind: "validation"; errorClass: IngestErrorClass; message: string; diagnostics: FailureDiagnostics }
  | { kind: "failure"; errorClass: IngestErrorClass; message: string; diagnostics: FailureDiagnostics };

export const MESSAGES = {
  invalidInput:
    "We couldn't accept this description. Please check what you entered and try again.",
  consentRequired:
    "Your description appears to include personal details. Please confirm consent below, or remove identifying details and try again.",
  processing:
    "We couldn't process your intake right now. Please try again in a few minutes.",
  provider:
    "The service that prepares your summary did not respond properly, so nothing was saved. Please try again in a few minutes.",
  configuration:
    "The intake service is not available at the moment, so nothing was saved. Please try again later.",
  unreachable:
    "We couldn't reach the intake service. Please try again in a few minutes.",
  timeout:
    "The intake service took too long to respond. Please try again.",
} as const;

// Client-side checks matching the backend intake rules, so obvious mistakes never leave the browser.
export function validateIntake(req: IngestRequest): string | null {
  const length = req.text.trim().length;
  if (length < MIN_TEXT_LENGTH) {
    return `Please describe your symptoms in at least ${MIN_TEXT_LENGTH} characters.`;
  }
  if (length > MAX_TEXT_LENGTH) {
    return `Please keep your description under ${MAX_TEXT_LENGTH} characters.`;
  }
  return null;
}

// Map an HTTP error response to a user-safe message. Backend detail stays in diagnostics only.
function classifyError(status: number, body: unknown): IngestOutcome {
  const detail =
    body && typeof body === "object" ? (body as JsonObject).detail : undefined;
  const diagnostics: FailureDiagnostics = { status, body };

  // 400: IntakeValidationError (agents/intake_agent.py)
  if (status === 400) {
    const consent =
      typeof detail === "string" && detail.toLowerCase().includes("consent");
    return {
      kind: "validation",
      errorClass: consent ? "consent" : "validation",
      message: consent ? MESSAGES.consentRequired : MESSAGES.invalidInput,
      diagnostics,
    };
  }

  // 422 with a list: FastAPI request validation. 422 with a string: StructuringError (pipeline failure).
  if (status === 422 && Array.isArray(detail)) {
    return { kind: "validation", errorClass: "validation", message: MESSAGES.invalidInput, diagnostics };
  }

  // 502: LLMError, 503: LLMConfigurationError (api/routers/ingest.py). Both are raised before anything is stored.
  if (status === 502) return { kind: "failure", errorClass: "provider", message: MESSAGES.provider, diagnostics };
  if (status === 503) {
    return { kind: "failure", errorClass: "configuration", message: MESSAGES.configuration, diagnostics };
  }

  return { kind: "failure", errorClass: "server", message: MESSAGES.processing, diagnostics };
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export interface SubmitOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

// Submit an intake. Never throws: every outcome is returned as a typed result.
export async function submitIntake(
  req: IngestRequest,
  options: SubmitOptions = {},
): Promise<IngestOutcome> {
  const {
    baseUrl = API_BASE_URL,
    fetchImpl = fetch,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/api/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: req.text.trim(),
        consent_granted: req.consent_granted,
        source: "web",
        input_type: "intake",
      }),
      signal: controller.signal,
    });
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    return {
      kind: "failure",
      errorClass: aborted ? "timeout" : "network",
      message: aborted ? MESSAGES.timeout : MESSAGES.unreachable,
      diagnostics: {
        note: aborted
          ? `Request aborted after ${timeoutMs} ms.`
          : "No readable HTTP response: the API is down, or it returned a response without CORS headers (e.g. an unhandled server error).",
      },
    };
  } finally {
    clearTimeout(timer);
  }

  const body = await readBody(response);

  if (!response.ok) {
    return classifyError(response.status, body);
  }

  if (!body || typeof body !== "object" || (body as PipelineResult).success !== true) {
    return {
      kind: "failure",
      errorClass: "server",
      message: MESSAGES.processing,
      diagnostics: {
        status: response.status,
        body,
        note: "HTTP 200 but the pipeline did not report success.",
      },
    };
  }

  return { kind: "success", status: response.status, data: body as PipelineResult };
}

// Backend execution mode (Issue #22). Read-only: the browser displays it but can never change it,
// and only the mode is read from /health — no provider configuration reaches the browser.
export type LlmMode = "mock" | "real";

export async function fetchLlmMode(
  options: Pick<SubmitOptions, "baseUrl" | "fetchImpl"> = {},
): Promise<LlmMode | null> {
  const { baseUrl = API_BASE_URL, fetchImpl = fetch } = options;
  try {
    const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/health`);
    if (!response.ok) return null;
    const mode = ((await response.json()) as JsonObject).llm_mode;
    return mode === "mock" || mode === "real" ? mode : null;
  } catch {
    return null;
  }
}

// Read-only system card (#43): GET /api/system-card. Public, no credentials.
export type SystemCard = Record<string, unknown>;

export async function fetchSystemCard(
  options: Pick<SubmitOptions, "baseUrl" | "fetchImpl"> = {},
): Promise<SystemCard | null> {
  const { baseUrl = API_BASE_URL, fetchImpl = fetch } = options;
  try {
    const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/api/system-card`);
    if (!response.ok) return null;
    return (await response.json()) as SystemCard;
  } catch {
    return null;
  }
}

// Cold start (#67): free hosted services sleep when idle, and the first request can take up to about a
// minute. Poll the existing GET /health with a per-attempt timeout and a bounded number of attempts.
// Attempts start at most once per attemptTimeoutMs, so fast failures (e.g. a 502 without CORS headers
// while the instance restarts) cannot use up the attempts in a few seconds: the window is ~75–105 s.
export const WAKE_POLICY = { maxAttempts: 6, attemptTimeoutMs: 15_000, retryDelayMs: 3_000 } as const;

export type ApiReadiness = "ready" | "unavailable";

// What the dashboard shows from a successful GET /health (#69). Values are passed through as reported;
// a missing or non-string field stays null rather than being guessed.
export interface HealthInfo {
  environment: string | null;
  llmMode: string | null;
}

export function parseHealth(body: JsonObject): HealthInfo {
  const text = (v: unknown) => (typeof v === "string" && v ? v : null);
  return { environment: text(body.environment), llmMode: text(body.llm_mode) };
}

export interface WaitForApiOptions extends Pick<SubmitOptions, "baseUrl" | "fetchImpl"> {
  maxAttempts?: number;
  attemptTimeoutMs?: number;
  retryDelayMs?: number;
  signal?: AbortSignal; // cancels the wait (e.g. the page was left)
  onAttempt?: (attempt: number, maxAttempts: number) => void;
  onHealth?: (health: HealthInfo) => void; // called once with the healthy /health body (#69)
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>; // injectable for tests
}

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal?.removeEventListener("abort", done);
      resolve();
    }
    signal?.addEventListener("abort", done);
  });
}

// Never throws. "ready" as soon as /health answers 200 with status "ok"; "unavailable" after
// maxAttempts failed or timed-out attempts, or when cancelled.
export async function waitForApi(options: WaitForApiOptions = {}): Promise<ApiReadiness> {
  const {
    baseUrl = API_BASE_URL,
    fetchImpl = fetch,
    maxAttempts = WAKE_POLICY.maxAttempts,
    attemptTimeoutMs = WAKE_POLICY.attemptTimeoutMs,
    retryDelayMs = WAKE_POLICY.retryDelayMs,
    signal,
    onAttempt,
    onHealth,
    sleep = abortableSleep,
  } = options;
  const url = `${baseUrl.replace(/\/$/, "")}/health`;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (signal?.aborted) return "unavailable";
    onAttempt?.(attempt, maxAttempts);
    const startedAt = Date.now();
    const controller = new AbortController();
    const cancel = () => controller.abort();
    const timer = setTimeout(cancel, attemptTimeoutMs);
    signal?.addEventListener("abort", cancel);
    try {
      const response = await fetchImpl(url, { signal: controller.signal });
      if (response.ok) {
        const body = (await response.json()) as JsonObject;
        if (body.status === "ok") {
          onHealth?.(parseHealth(body));
          return "ready";
        }
      }
    } catch {
      // Unreachable, timed out, or not JSON yet (e.g. a 502 page while the instance starts): retry
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", cancel);
    }
    if (attempt < maxAttempts) {
      await sleep(Math.max(retryDelayMs, attemptTimeoutMs - (Date.now() - startedAt)), signal);
    }
  }
  return "unavailable";
}
