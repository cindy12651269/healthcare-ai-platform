import { describe, expect, it, vi } from "vitest";
import { MESSAGES, submitIntake, validateIntake } from "../services/api";
import { jsonResponse, pipelineResult } from "./fixtures";

const req = { text: "  Sore throat and mild fever for two days.  ", consent_granted: true };

describe("submitIntake", () => {
  it("posts the intake to /api/ingest and returns the pipeline result", async () => {
    const data = pipelineResult();
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, data));

    const outcome = await submitIntake(req, { baseUrl: "http://api.test/", fetchImpl });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("http://api.test/api/ingest");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      text: "Sore throat and mild fever for two days.",
      consent_granted: true,
      source: "web",
      input_type: "intake",
    });
    expect(outcome).toEqual({ kind: "success", status: 200, data });
  });

  it("never sends feature flags or credentials in the request", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, pipelineResult()));
    await submitIntake(req, { fetchImpl });
    const [, init] = fetchImpl.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(Object.keys(body).sort()).toEqual(["consent_granted", "input_type", "source", "text"]);
    expect(init.headers).not.toHaveProperty("Authorization");
    expect(init.credentials).toBeUndefined();
  });

  it("maps a 400 consent error to a consent message", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(400, { detail: "PHI detected but patient consent has not been granted." }),
    );
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome.kind).toBe("validation");
    expect(outcome.kind !== "success" && outcome.message).toBe(MESSAGES.consentRequired);
  });

  it("maps other 400 intake errors to a generic validation message", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(400, { detail: "raw_text is too short to be meaningful." }),
    );
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome).toMatchObject({
      kind: "validation",
      message: MESSAGES.invalidInput,
      diagnostics: { status: 400 },
    });
  });

  it("maps FastAPI request validation (422 list) to a validation error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(422, { detail: [{ loc: ["body", "text"], msg: "Field required" }] }),
    );
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome).toMatchObject({ kind: "validation", message: MESSAGES.invalidInput });
  });

  it("maps a structuring failure (422 string) to a pipeline failure without leaking detail", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(422, { detail: "LLM structuring error: Schema validation error: x" }),
    );
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome.kind).toBe("failure");
    if (outcome.kind === "success") return;
    expect(outcome.message).toBe(MESSAGES.processing);
    expect(outcome.message).not.toContain("LLM");
    expect(outcome.diagnostics.body).toEqual({
      detail: "LLM structuring error: Schema validation error: x",
    });
  });

  it("maps a plain-text 500 to a pipeline failure", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response("Internal Server Error", { status: 500 }));
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome).toMatchObject({
      kind: "failure",
      message: MESSAGES.processing,
      diagnostics: { status: 500, body: "Internal Server Error" },
    });
  });

  it("maps a network/CORS failure to an unreachable message", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome).toMatchObject({ kind: "failure", message: MESSAGES.unreachable });
  });

  it("times out slow requests", async () => {
    const fetchImpl = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    const outcome = await submitIntake(req, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      timeoutMs: 10,
    });
    expect(outcome).toMatchObject({ kind: "failure", message: MESSAGES.timeout });
  });

  it("treats HTTP 200 without success=true as a failure", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, pipelineResult({ success: false })));
    const outcome = await submitIntake(req, { fetchImpl });
    expect(outcome).toMatchObject({ kind: "failure", message: MESSAGES.processing });
  });
});

describe("validateIntake", () => {
  it("rejects text shorter than the backend minimum", () => {
    expect(validateIntake({ text: "   short   ", consent_granted: true })).toMatch(/at least 10/);
  });

  it("rejects text longer than the backend maximum", () => {
    expect(validateIntake({ text: "a".repeat(5001), consent_granted: true })).toMatch(/under 5000/);
  });

  it("accepts valid text", () => {
    expect(validateIntake({ text: "I have had a headache since Monday.", consent_granted: false })).toBeNull();
  });
});
