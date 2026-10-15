import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IntakePage from "../pages/intake";
import { IngestOutcome, IngestRequest, MAX_TEXT_LENGTH, MESSAGES, PipelineResult, submitIntake } from "../services/api";
import { jsonResponse, pipelineResult, scenarioResults } from "./fixtures";
import { SCENARIO_PRESETS } from "../services/demo";

// The API answers /health at once; the cold-start polling itself is covered in ApiStatus.test.tsx
const apiReady = async () => "ready" as const;

const VALID_TEXT = "I have had a sore throat and a mild fever for two days.";

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

const success = (data: PipelineResult = pipelineResult()): IngestOutcome => ({ kind: "success", status: 200, data });

const textarea = () => screen.getByLabelText(/Your symptoms/) as HTMLTextAreaElement;
const consentBox = () => screen.getByRole("checkbox", { name: /I consent/ }) as HTMLInputElement;
const submitButton = () => screen.getByRole("button", { name: /Submit intake|Submitting…/ });

async function fillAndSubmit(text = VALID_TEXT) {
  const user = userEvent.setup();
  await user.type(textarea(), text);
  await user.click(consentBox());
  await user.click(screen.getByRole("button", { name: "Submit intake" }));
  return user;
}

const resultsHeading = () => screen.findByRole("heading", { name: "Your intake has been received" });

describe("IntakePage", () => {
  it("renders the intake form with consent as the only checkbox and no feature toggles", () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Pre-visit symptom intake" })).toBeInTheDocument();
    expect(textarea()).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(1);
    expect(checkboxes[0].closest("label")).toHaveTextContent(/consent/i);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByText(/enable[_ ]rag|enable[_ ]persistence/i)).not.toBeInTheDocument();
  });

  it("collects no patient identifiers: one text field and the consent checkbox only", () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(document.querySelectorAll("input:not([type=checkbox]), select")).toHaveLength(0);
    expect(screen.getByText(/do not include your name, contact details, date of birth/)).toBeInTheDocument();
  });

  it("shows a loading state and prevents duplicate submissions", async () => {
    const pending = deferred<IngestOutcome>();
    const submit = vi.fn().mockReturnValue(pending.promise);
    render(<IntakePage checkApi={apiReady} submit={submit} />);

    const user = await fillAndSubmit();
    const button = screen.getByRole("button", { name: "Submitting…" });
    expect(button).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Processing your intake");
    expect(textarea()).toBeDisabled();
    expect(consentBox()).toBeDisabled();
    // Scenario cards are disabled too, so the text cannot change mid-flight
    expect(screen.getByTestId("scenario-routine")).toBeDisabled();

    await user.click(button);
    fireEvent.submit(button.closest("form")!); // even a forced second submit is ignored
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({ text: VALID_TEXT, consent_granted: true });

    pending.resolve(success());
    expect(await resultsHeading()).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit intake" })).toBeEnabled();
  });

  it("renders the structured summary and report on success", async () => {
    const submit = vi.fn().mockResolvedValue(success());
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    await fillAndSubmit();

    await resultsHeading();
    expect(screen.getByText("Two-day history of sore throat with low-grade fever.")).toBeInTheDocument();
    expect(screen.getByText("sore throat")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Suggested next steps" })).toBeInTheDocument();
    expect(screen.getByText("Rest, fluids, and follow up with your care team.")).toBeInTheDocument();
    expect(screen.getByText(/checked for diagnostic language/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    for (const name of ["Outcome", "Intake summary", "Extracted information", "Safety findings", "Pre-visit report", "Next steps"]) {
      expect(screen.getByRole("heading", { name, level: 3 })).toBeInTheDocument();
    }
  });

  it("labels mock extraction as a rule-based baseline and shows duration (#40)", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.routine))} />);
    await fillAndSubmit();

    await resultsHeading();
    expect(screen.getByText("two days")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-baseline-note")).toHaveTextContent(/rule-based baseline, not LLM-generated/);
  });

  it("does not show the baseline label for non-mock output", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success())} />);
    await fillAndSubmit();
    await resultsHeading();
    expect(screen.queryByTestId("extraction-baseline-note")).not.toBeInTheDocument();
  });

  it("says so honestly when the backend returns no report", async () => {
    const submit = vi.fn().mockResolvedValue(success(pipelineResult({ report: null })));
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    await fillAndSubmit();
    expect(await screen.findByTestId("report-unavailable")).toBeInTheDocument();
  });

  it("shows emergency guidance when the safety trace requests it", async () => {
    const data = pipelineResult({
      safety: { allowed: true, actions: ["add_emergency_guidance"], reasons: [], severity: "high" },
    });
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(data))} />);
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent(/seek urgent medical care/);
  });

  it("shows the backend mode read-only, from the single /health check by default", async () => {
    const checkApi = vi.fn(async (opts: { onHealth?: (h: { environment: string; llmMode: string }) => void }) => {
      opts.onHealth?.({ environment: "demo", llmMode: "mock" });
      return "ready" as const;
    });
    render(<IntakePage checkApi={checkApi} submit={vi.fn()} />);
    expect(await screen.findByTestId("llm-mode")).toHaveTextContent("LLM Mode: Mock");
    expect(checkApi).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["mock", "LLM Mode: Mock"],
    ["real", "LLM Mode: Real"],
  ] as const)("shows the backend %s mode read-only", async (mode, label) => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} loadLlmMode={() => Promise.resolve(mode)} />);
    expect(await screen.findByTestId("llm-mode")).toHaveTextContent(label);
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(mock|real)$/i })).not.toBeInTheDocument();
  });
});

describe("Scenario cards", () => {
  it.each(SCENARIO_PRESETS.map((p) => [p.label, p] as const))(
    "%s shows its text and expected outcome, fills the text only and never submits",
    async (_label, preset) => {
      const submit = vi.fn().mockResolvedValue(success());
      render(<IntakePage checkApi={apiReady} submit={submit} />);
      const user = userEvent.setup();

      const card = screen.getByTestId(`scenario-${preset.id}`);
      expect(card).toHaveTextContent(preset.label);
      expect(card).toHaveTextContent(preset.text);
      expect(card).toHaveTextContent(`Expected outcome: ${preset.expect}`);
      expect(card).toHaveAttribute("aria-pressed", "false");

      await user.click(card);
      expect(textarea()).toHaveValue(preset.text);
      expect(card).toHaveAttribute("aria-pressed", "true");
      expect(card).toHaveTextContent("Selected");
      expect(consentBox()).not.toBeChecked();
      expect(submit).not.toHaveBeenCalled();

      // The preset never grants consent: an unticked form submits consent_granted=false through the
      // normal path, where the backend enforces consent when it detects personal details
      await user.click(screen.getByRole("button", { name: "Submit intake" }));
      expect(submit).toHaveBeenLastCalledWith({ text: preset.text, consent_granted: false });
      await resultsHeading();

      await user.click(consentBox());
      await user.click(screen.getByRole("button", { name: "Submit intake" }));
      expect(submit).toHaveBeenLastCalledWith({ text: preset.text, consent_granted: true });
    },
  );

  it("selecting another card moves the selection; editing the text clears it", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByTestId("scenario-routine"));
    await user.click(screen.getByTestId("scenario-vague"));
    expect(screen.getByTestId("scenario-routine")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("scenario-vague")).toHaveAttribute("aria-pressed", "true");

    await user.type(textarea(), " More detail.");
    expect(screen.getByTestId("scenario-vague")).toHaveAttribute("aria-pressed", "false");
  });

  it("keeps a deliberately granted consent when a scenario is chosen afterwards", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(consentBox());
    await user.click(screen.getByTestId("scenario-emergency"));
    expect(consentBox()).toBeChecked();
  });

  // Each preset's expected outcome (SCENARIO_PRESETS.expect) as the outcome summary shows it
  it.each([
    ["routine", "Submitted", [], { emergency: false, blocked: false }],
    ["emergency", "Flagged for staff review", ["emergency_signal"], { emergency: true, blocked: false }],
    ["prescription", "Flagged for staff review", ["blocked_prescription"], { emergency: false, blocked: true }],
    ["vague", "Flagged for staff review", ["low_confidence"], { emergency: false, blocked: false }],
  ] as const)("the %s outcome states its status and reasons without the trace", async (id, status, reasons, flags) => {
    const preset = SCENARIO_PRESETS.find((p) => p.id === id)!;
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults[id]))} />);
    const user = userEvent.setup();
    await user.click(screen.getByTestId(`scenario-${id}`));
    await user.click(consentBox());
    await user.click(screen.getByRole("button", { name: "Submit intake" }));
    await resultsHeading();

    const summary = screen.getByTestId("outcome-summary");
    expect(within(summary).getByText(status)).toBeInTheDocument();
    for (const code of reasons) {
      expect(preset.expect).toContain(code);
      expect(within(summary).getByText(code)).toBeInTheDocument();
    }
    if (reasons.length === 0) expect(within(summary).queryByTestId("outcome-reasons")).not.toBeInTheDocument();
    expect(screen.queryByTestId("emergency-guidance") !== null).toBe(flags.emergency);
    expect(screen.queryByTestId("blocked-notice") !== null).toBe(flags.blocked);
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
  });
});

describe("Accessible field validation", () => {
  it("blocks too-short input, links the error to the field and moves focus to it", async () => {
    const submit = vi.fn();
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = userEvent.setup();
    await user.type(textarea(), "short");
    await user.click(screen.getByRole("button", { name: "Submit intake" }));

    expect(submit).not.toHaveBeenCalled();
    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent(/at least 10 characters/);
    expect(textarea()).toHaveAttribute("aria-invalid", "true");
    expect(textarea().getAttribute("aria-describedby")).toContain(error.id);
    expect(textarea()).toHaveFocus();

    // Fixing the text clears the error
    await user.type(textarea(), " throat ache");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(textarea()).not.toHaveAttribute("aria-invalid");
  });

  it("describes the field with its instructions and the live character counter", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    const ids = textarea().getAttribute("aria-describedby")!.split(" ");
    expect(ids).toEqual(expect.arrayContaining(["symptoms-hint", "symptoms-counter"]));
    expect(document.getElementById("symptoms-hint")).toHaveTextContent("At least 10 characters");
    expect(document.getElementById("symptoms-counter")).toHaveTextContent(`0 / ${MAX_TEXT_LENGTH} characters`);
    expect(textarea()).toHaveAttribute("maxLength", String(MAX_TEXT_LENGTH));

    await userEvent.setup().type(textarea(), "Headache");
    expect(document.getElementById("symptoms-counter")).toHaveTextContent(`8 / ${MAX_TEXT_LENGTH} characters`);
    // Not announced on every keystroke
    expect(screen.getByTestId("counter-announcement")).toHaveTextContent("");
  });

  it("announces the counter only near and at the limit", () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn()} />);
    fireEvent.change(textarea(), { target: { value: "a".repeat(MAX_TEXT_LENGTH - 400) } });
    expect(screen.getByTestId("counter-announcement")).toHaveTextContent("400 characters remaining.");
    fireEvent.change(textarea(), { target: { value: "a".repeat(MAX_TEXT_LENGTH) } });
    expect(screen.getByTestId("counter-announcement")).toHaveTextContent(`Character limit reached: ${MAX_TEXT_LENGTH} characters.`);
  });
});

describe("Staged submission", () => {
  it("reports an already-awake server and then processing, never a percentage", async () => {
    const pending = deferred<IngestOutcome>();
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockReturnValue(pending.promise)} />);
    await fillAndSubmit();

    const progress = screen.getByTestId("submission-progress");
    expect(progress).toHaveAttribute("data-stage", "processing");
    expect(progress).toHaveTextContent("Demo server ready");
    expect(progress).not.toHaveTextContent("%");
    pending.resolve(success());
    await resultsHeading();
    expect(screen.getByTestId("submission-progress")).toHaveTextContent("Submission completed.");
  });

  it("waits for a slow /health before sending, then processes (cold start)", async () => {
    const wake = deferred<"ready">();
    const checkApi = vi.fn((opts: { onAttempt?: (a: number, m: number) => void }) => {
      opts.onAttempt?.(1, 6);
      opts.onAttempt?.(2, 6);
      return wake.promise;
    });
    const pending = deferred<IngestOutcome>();
    const submit = vi.fn().mockReturnValue(pending.promise);
    render(<IntakePage checkApi={checkApi} submit={submit} />);
    await fillAndSubmit();

    const progress = screen.getByTestId("submission-progress");
    expect(progress).toHaveAttribute("data-stage", "waking");
    expect(within(progress).getByRole("status")).toHaveTextContent("attempt 2 of 6");
    expect(within(progress).getByRole("status")).toHaveTextContent("Your intake has not been sent yet.");
    expect(submitButton()).toBeDisabled();
    // Processing is not claimed and nothing is sent before the server answers
    expect(submit).not.toHaveBeenCalled();
    expect(progress).not.toHaveTextContent("Processing your intake");
    // The page-level cold-start banner gives way to the submission's own progress
    expect(screen.queryByTestId("api-status")).not.toBeInTheDocument();

    wake.resolve("ready");
    await waitFor(() => expect(screen.getByTestId("submission-progress")).toHaveAttribute("data-stage", "processing"));
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submitButton()).toBeDisabled();
    expect(screen.getByTestId("submission-progress")).toHaveTextContent("Wake the demo server");
    expect(checkApi).toHaveBeenCalledTimes(1); // no extra health polling for the submission

    pending.resolve(success());
    await resultsHeading();
  });

  it("does not send the intake when the server never wakes, and offers a retry", async () => {
    const checkApi = vi.fn(async () => "unavailable" as const);
    const submit = vi.fn();
    render(<IntakePage checkApi={checkApi} submit={submit} />);
    await screen.findByText("The demo server did not respond.");
    await fillAndSubmit();

    const alert = await screen.findByTestId("intake-error");
    expect(alert).toHaveAttribute("data-error-class", "unavailable");
    expect(alert).toHaveTextContent("your intake was not sent");
    expect(submit).not.toHaveBeenCalled();
    expect(checkApi).toHaveBeenCalledTimes(2); // the page check, and one re-check for this submission
    expect(textarea()).toHaveValue(VALID_TEXT);
    expect(consentBox()).toBeChecked();
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("explains a slow response without resubmitting", async () => {
    const pending = deferred<IngestOutcome>();
    const submit = vi.fn().mockReturnValue(pending.promise);
    render(<IntakePage checkApi={apiReady} submit={submit} slowProcessingMs={20} />);
    await fillAndSubmit();
    expect(await screen.findByText(/taking longer than usual/)).toBeInTheDocument();
    expect(submit).toHaveBeenCalledTimes(1);
    pending.resolve(success());
    await resultsHeading();
  });
});

describe("Outcome-first results", () => {
  it("states a submitted intake and the next step first", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.routine))} />);
    await fillAndSubmit();
    const heading = await resultsHeading();
    await waitFor(() => expect(heading).toHaveFocus());

    const summary = screen.getByTestId("outcome-summary");
    expect(within(summary).getByText("Submitted").closest("[data-status]")).toHaveAttribute("data-status", "submitted");
    expect(screen.getByTestId("next-step")).toHaveTextContent("stored as submitted");
    // Outcome comes before the detailed report
    const report = screen.getByRole("heading", { name: "Pre-visit report" });
    expect(summary.compareDocumentPosition(report) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("explains that a flagged intake is in the clinic staff queue", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.vague))} />);
    await fillAndSubmit();
    await resultsHeading();
    const summary = screen.getByTestId("outcome-summary");
    expect(within(summary).getByText("Flagged for staff review").closest("[data-status]")).toHaveAttribute(
      "data-status",
      "needs_review",
    );
    expect(within(summary).getByText("Low structuring confidence")).toBeInTheDocument();
    expect(screen.getByTestId("next-step")).toHaveTextContent(
      "Authorized clinic staff can review this record in their queue",
    );
  });

  it("puts emergency guidance above everything else in the result", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.emergency))} />);
    await fillAndSubmit();
    await resultsHeading();
    const guidance = screen.getByTestId("emergency-guidance");
    expect(guidance).toHaveAttribute("role", "alert");
    expect(guidance).toHaveTextContent(/seek urgent medical care now/);
    const results = guidance.closest("section")!;
    // First element after the results heading
    expect(results.children[1]).toBe(guidance);
    expect(within(screen.getByTestId("outcome-summary")).getByText("Emergency signal")).toBeInTheDocument();
  });

  it("shows the safe acknowledgement for a blocked report, not a generated report", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.prescription))} />);
    await fillAndSubmit();
    await resultsHeading();
    expect(screen.getByTestId("blocked-notice")).toHaveTextContent(
      "No automated report was generated for you. The safety check withheld it because it would have included prescription or dosing advice.",
    );
    expect(screen.getByRole("heading", { name: "Safe acknowledgement (report withheld)" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Pre-visit report" })).not.toBeInTheDocument();
    expect(screen.getByText(/A member of your care team will review it before your visit/)).toBeInTheDocument();
    expect(within(screen.getByTestId("safety-findings")).getByText(/replaced with a safe acknowledgement/)).toBeInTheDocument();
  });

  it.each([
    ["duplicate", "An identical description was received earlier, so no new record was created."],
    ["disabled", "This intake was not stored (storage is turned off on this server)"],
    ["failed", "This intake was not stored (the record could not be saved)"],
  ])("does not claim a queue entry when storage is %s", async (status, text) => {
    const data = { ...scenarioResults.vague, persistence: { status, record_id: null } };
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(data))} />);
    await fillAndSubmit();
    await resultsHeading();
    expect(screen.getByTestId("next-step")).toHaveTextContent(text);
    expect(screen.getByTestId("next-step")).not.toHaveTextContent("can review this record in their queue");
  });
});

// Each HTTP error class end to end: the real submitIntake against a mocked fetch
const BASE = "https://api.example.test";
const hang = (_url: string, init: RequestInit) =>
  new Promise<Response>((_r, reject) =>
    init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
  );

const ERROR_CASES = [
  {
    name: "400 validation",
    errorClass: "validation",
    first: () => Promise.resolve(jsonResponse(400, { detail: "raw_text is too short to be meaningful." })),
    message: MESSAGES.invalidInput,
    recovery: "Review your description",
    focus: "text",
  },
  {
    name: "400 consent",
    errorClass: "consent",
    first: () => Promise.resolve(jsonResponse(400, { detail: "PHI detected but patient consent has not been granted." })),
    message: MESSAGES.consentRequired,
    recovery: "Review consent",
    focus: "consent",
  },
  {
    name: "422 request validation",
    errorClass: "validation",
    first: () => Promise.resolve(jsonResponse(422, { detail: [{ loc: ["body", "text"], msg: "Field required" }] })),
    message: MESSAGES.invalidInput,
    recovery: "Review your description",
    focus: "text",
  },
  {
    name: "502 provider",
    errorClass: "provider",
    first: () => Promise.resolve(jsonResponse(502, { detail: "LLM provider error: upstream timeout" })),
    message: MESSAGES.provider,
    recovery: "Try again",
  },
  {
    name: "503 configuration",
    errorClass: "configuration",
    first: () => Promise.resolve(jsonResponse(503, { detail: "LLM configuration error: missing key" })),
    message: MESSAGES.configuration,
    recovery: "Try again",
  },
  {
    name: "network",
    errorClass: "network",
    first: () => Promise.reject(new TypeError("Failed to fetch")),
    message: MESSAGES.unreachable,
    recovery: "Send again",
  },
  {
    name: "timeout",
    errorClass: "timeout",
    first: hang,
    message: MESSAGES.timeout,
    recovery: "Send again",
  },
] as const;

describe("Error handling and recovery", () => {
  it.each(ERROR_CASES.map((c) => [c.name, c] as const))("%s: specific message, kept input and a recovery path", async (_n, c) => {
    const fetchImpl = vi
      .fn()
      .mockImplementationOnce(c.first)
      .mockResolvedValue(jsonResponse(200, scenarioResults.routine));
    const submit = (req: IngestRequest) =>
      submitIntake(req, { baseUrl: BASE, fetchImpl: fetchImpl as unknown as typeof fetch, timeoutMs: 20 });
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = await fillAndSubmit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("data-error-class", c.errorClass);
    expect(alert).toHaveTextContent(c.message);
    expect(alert).not.toHaveTextContent(/LLM|upstream|missing key/); // backend detail stays in the trace
    expect(textarea()).toHaveValue(VALID_TEXT);
    expect(consentBox()).toBeChecked();
    expect(screen.queryByRole("heading", { name: "Your intake has been received" })).not.toBeInTheDocument();

    const recovery = within(alert).getByRole("button", { name: c.recovery });
    if ("focus" in c) {
      // Validation: the field is marked, described by the message and focused; nothing is resent
      const field = c.focus === "consent" ? consentBox() : textarea();
      await waitFor(() => expect(field).toHaveFocus());
      expect(field).toHaveAttribute("aria-invalid", "true");
      expect(field.getAttribute("aria-describedby")).toMatch(/error/);
      expect(screen.getAllByRole("alert")).toHaveLength(1); // announced once, by the page alert
      textarea().blur();
      await user.click(recovery);
      expect(field).toHaveFocus();
      expect(fetchImpl).toHaveBeenCalledTimes(1);
    } else {
      await waitFor(() => expect(alert).toHaveFocus());
      // Never retried automatically
      await new Promise((r) => setTimeout(r, 50));
      expect(fetchImpl).toHaveBeenCalledTimes(1);
      await user.click(recovery);
      await resultsHeading();
      expect(fetchImpl).toHaveBeenCalledTimes(2);
      expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toMatchObject({ text: VALID_TEXT, consent_granted: true });
    }
  });

  it.each(["network", "timeout"] as const)(
    "%s: explains the ambiguity and that resending the same text creates no second record",
    async (errorClass) => {
      const c = ERROR_CASES.find((e) => e.errorClass === errorClass)!;
      const duplicate = { ...scenarioResults.routine, persistence: { status: "duplicate", record_id: null } };
      const fetchImpl = vi.fn().mockImplementationOnce(c.first).mockResolvedValue(jsonResponse(200, duplicate));
      const submit = (req: IngestRequest) =>
        submitIntake(req, { baseUrl: BASE, fetchImpl: fetchImpl as unknown as typeof fetch, timeoutMs: 20 });
      render(<IntakePage checkApi={apiReady} submit={submit} />);
      const user = await fillAndSubmit();

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("We couldn't confirm your submission");
      expect(alert).toHaveTextContent("Nothing is resent automatically");
      await user.click(within(alert).getByRole("button", { name: "Send again" }));
      await resultsHeading();
      expect(screen.getByTestId("next-step")).toHaveTextContent("no new record was created");
    },
  );

  it("a retry cannot overlap another submission", async () => {
    const pending = deferred<IngestOutcome>();
    const submit = vi
      .fn()
      .mockResolvedValueOnce({ kind: "failure", errorClass: "provider", message: MESSAGES.provider, diagnostics: { status: 502 } })
      .mockReturnValue(pending.promise);
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = await fillAndSubmit();

    const retry = await screen.findByRole("button", { name: "Try again" });
    await user.click(retry);
    // The alert is replaced by the progress of the retry; the form stays locked
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    fireEvent.submit(textarea().closest("form")!);
    expect(submit).toHaveBeenCalledTimes(2);
    pending.resolve(success());
    await resultsHeading();
  });

  it("keeps backend detail of a 500 in the developer panel only", async () => {
    const submit = vi.fn().mockResolvedValue({
      kind: "failure",
      errorClass: "server",
      message: MESSAGES.processing,
      diagnostics: { status: 500, body: "Traceback (most recent call last): secret internals" },
    });
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = await fillAndSubmit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent(MESSAGES.processing);
    expect(alert).not.toHaveTextContent(/Traceback/);
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Reviewer \/ developer/ }));

    const details = screen.getByText("Developer trace").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByTestId("raw-json")).toHaveTextContent("Traceback");
  });
});

describe("Start a new intake", () => {
  it("clears the form, scenario, consent, result and trace, and returns focus to the form", async () => {
    const submit = vi.fn().mockResolvedValue(success(scenarioResults.emergency));
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = userEvent.setup();
    await user.click(screen.getByTestId("scenario-emergency"));
    await user.click(consentBox());
    await user.click(screen.getByRole("button", { name: "Submit intake" }));
    await resultsHeading();
    await user.click(screen.getByRole("checkbox", { name: /Reviewer \/ developer/ }));

    await user.click(screen.getByRole("button", { name: "Start a new intake" }));
    expect(textarea()).toHaveValue("");
    expect(consentBox()).not.toBeChecked();
    expect(screen.getByTestId("scenario-emergency")).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("heading", { name: "Your intake has been received" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("submission-progress")).not.toBeInTheDocument();
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Reviewer \/ developer/ })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Tell us what brings you in" })).toHaveFocus());
    expect(submit).toHaveBeenCalledTimes(1); // nothing is sent or deleted
  });

  it("also clears an error and the field error state", async () => {
    const submit = vi.fn().mockResolvedValue({
      kind: "validation",
      errorClass: "consent",
      message: MESSAGES.consentRequired,
      diagnostics: { status: 400 },
    });
    render(<IntakePage checkApi={apiReady} submit={submit} />);
    const user = await fillAndSubmit();
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Start a new intake" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(consentBox()).not.toHaveAttribute("aria-invalid");
    expect(textarea()).toHaveValue("");
  });
});

describe("Developer trace", () => {
  it("is hidden from the patient view by default", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success())} />);
    await fillAndSubmit();
    await resultsHeading();
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Reviewer \/ developer/ })).not.toBeChecked();
  });

  it("renders collapsed behind the toggle with run, escalation, metrics, retrieval, safety and JSON", async () => {
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(scenarioResults.vague))} />);
    const user = await fillAndSubmit();

    await user.click(await screen.findByRole("checkbox", { name: /Reviewer \/ developer/ }));
    const summary = await screen.findByText("Developer trace");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveClass("card");

    const panel = within(details);
    expect(panel.getByText("Review status").nextSibling).toHaveTextContent("needs_review");
    expect(panel.getByText("Storage").nextSibling).toHaveTextContent("saved");
    const metrics = panel.getByTestId("metrics-section");
    expect(within(metrics).getByText("Structuring").nextSibling).toHaveTextContent("3.4 ms");
    expect(within(metrics).getByText("Total").nextSibling).toHaveTextContent("12.0 ms");
    expect(within(panel.getByTestId("retrieval-section")).getByText("Enabled (server config)")).toBeInTheDocument();
    expect(within(panel.getByTestId("safety-section")).getByText("Severity").nextSibling).toHaveTextContent("low");
    expect(panel.getByTestId("raw-json")).toHaveTextContent('"run_id": "run-123"');
    expect(panel.getByRole("button", { name: "Copy JSON" })).toBeInTheDocument();
    // read-only: no form controls besides Copy JSON
    expect(panel.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(panel.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("does not fabricate trace data the backend did not return", async () => {
    const data = pipelineResult({ metrics: undefined, rag: undefined, safety: undefined, report: null });
    render(<IntakePage checkApi={apiReady} submit={vi.fn().mockResolvedValue(success(data))} />);
    const user = await fillAndSubmit();
    await user.click(await screen.findByRole("checkbox", { name: /Reviewer \/ developer/ }));
    await screen.findByText("Developer trace");
    for (const id of ["metrics-section", "retrieval-section", "safety-section"]) {
      expect(screen.getByTestId(id)).toHaveTextContent("Not returned by the API for this run.");
    }
  });
});
