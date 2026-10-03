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

export type IngestOutcome =
  | { kind: "success"; status: number; data: PipelineResult }
  | { kind: "validation"; message: string; diagnostics: FailureDiagnostics }
  | { kind: "failure"; message: string; diagnostics: FailureDiagnostics };

export const MESSAGES = {
  invalidInput:
    "We couldn't accept this description. Please check what you entered and try again.",
  consentRequired:
    "Your description appears to include personal details. Please confirm consent below, or remove identifying details and try again.",
  processing:
    "We couldn't process your intake right now. Please try again in a few minutes.",
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
      message: consent ? MESSAGES.consentRequired : MESSAGES.invalidInput,
      diagnostics,
    };
  }

  // 422 with a list: FastAPI request validation. 422 with a string: StructuringError (pipeline failure).
  if (status === 422 && Array.isArray(detail)) {
    return { kind: "validation", message: MESSAGES.invalidInput, diagnostics };
  }

  return { kind: "failure", message: MESSAGES.processing, diagnostics };
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
