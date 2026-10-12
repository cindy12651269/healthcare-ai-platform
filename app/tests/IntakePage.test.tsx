import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IntakePage from "../pages/intake";
import { IngestOutcome, MESSAGES } from "../services/api";
import { pipelineResult } from "./fixtures";
import { SCENARIO_PRESETS } from "../services/demo";

const VALID_TEXT = "I have had a sore throat and a mild fever for two days.";

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

async function fillAndSubmit(text = VALID_TEXT) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Your symptoms"), text);
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Submit intake" }));
  return user;
}

describe("IntakePage", () => {
  it("renders the intake form with consent as the only checkbox and no feature toggles", () => {
    render(<IntakePage submit={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Pre-visit symptom intake" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your symptoms")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(1);
    expect(checkboxes[0].closest("label")).toHaveTextContent(/consent/i);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByText(/enable[_ ]rag|enable[_ ]persistence/i)).not.toBeInTheDocument();
  });

  it("blocks submission of too-short input on the client", async () => {
    const submit = vi.fn();
    render(<IntakePage submit={submit} />);
    await fillAndSubmit("short");
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByText(/at least 10 characters/)).toBeInTheDocument();
  });

  it("shows a loading state and prevents duplicate submissions", async () => {
    const pending = deferred<IngestOutcome>();
    const submit = vi.fn().mockReturnValue(pending.promise);
    render(<IntakePage submit={submit} />);

    const user = await fillAndSubmit();
    const button = screen.getByRole("button", { name: "Submitting…" });
    expect(button).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Processing your intake");
    expect(screen.getByLabelText("Your symptoms")).toBeDisabled();

    await user.click(button);
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({ text: VALID_TEXT, consent_granted: true });

    pending.resolve({ kind: "success", status: 200, data: pipelineResult() });
    expect(await screen.findByRole("heading", { name: "Your intake has been received" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit intake" })).toBeEnabled();
  });

  it("renders the structured summary and report on success", async () => {
    const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data: pipelineResult() });
    render(<IntakePage submit={submit} />);
    await fillAndSubmit();

    await screen.findByRole("heading", { name: "Your intake has been received" });
    expect(screen.getByText("Two-day history of sore throat with low-grade fever.")).toBeInTheDocument();
    expect(screen.getByText("sore throat")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Suggested next steps" })).toBeInTheDocument();
    expect(screen.getByText("Rest, fluids, and follow up with your care team.")).toBeInTheDocument();
    expect(screen.getByText(/checked for diagnostic language/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("labels mock extraction as a rule-based baseline and shows duration (#40)", async () => {
    const data = pipelineResult({
      structured: {
        clinical_structuring: {
          chief_complaint: VALID_TEXT,
          symptoms: ["sore throat", "fever"],
          duration: "two days",
          severity: "mild",
          clinical_summary: "Rule-based baseline (not LLM-generated). Reported symptoms: sore throat, fever.",
          confidence_level: 1,
        },
        output_metadata: { generated_at: "2025-01-01T00:00:00Z", model_version: "mock", prompt_version: "v1" },
      },
    });
    render(<IntakePage submit={vi.fn().mockResolvedValue({ kind: "success", status: 200, data })} />);
    await fillAndSubmit();

    await screen.findByRole("heading", { name: "Your intake has been received" });
    expect(screen.getByText("two days")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-baseline-note")).toHaveTextContent(/rule-based baseline, not LLM-generated/);
  });

  it("does not show the baseline label for non-mock output", async () => {
    render(<IntakePage submit={vi.fn().mockResolvedValue({ kind: "success", status: 200, data: pipelineResult() })} />);
    await fillAndSubmit();
    await screen.findByRole("heading", { name: "Your intake has been received" });
    expect(screen.queryByTestId("extraction-baseline-note")).not.toBeInTheDocument();
  });

  it("says so honestly when the backend returns no report", async () => {
    const submit = vi
      .fn()
      .mockResolvedValue({ kind: "success", status: 200, data: pipelineResult({ report: null }) });
    render(<IntakePage submit={submit} />);
    await fillAndSubmit();
    expect(await screen.findByTestId("report-unavailable")).toBeInTheDocument();
  });

  it("shows emergency guidance when the safety trace requests it", async () => {
    const data = pipelineResult({
      safety: { allowed: true, actions: ["add_emergency_guidance"], reasons: [], severity: "high" },
    });
    const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data });
    render(<IntakePage submit={submit} />);
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent(/seek urgent medical care/);
  });

  it("renders the developer trace collapsed by default with metrics, retrieval, safety and JSON", async () => {
    const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data: pipelineResult() });
    render(<IntakePage submit={submit} />);
    const user = await fillAndSubmit();

    await user.click(await screen.findByRole("checkbox", { name: /Reviewer \/ developer/ }));
    const summary = await screen.findByText("Developer trace");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");

    const panel = within(details);
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
    const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data });
    render(<IntakePage submit={submit} />);
    const user = await fillAndSubmit();
    await user.click(await screen.findByRole("checkbox", { name: /Reviewer \/ developer/ }));
    await screen.findByText("Developer trace");
    for (const id of ["metrics-section", "retrieval-section", "safety-section"]) {
      expect(screen.getByTestId(id)).toHaveTextContent("Not returned by the API for this run.");
    }
  });

  it("shows a validation error state", async () => {
    const submit = vi.fn().mockResolvedValue({
      kind: "validation",
      message: MESSAGES.consentRequired,
      diagnostics: { status: 400, body: { detail: "PHI detected but patient consent has not been granted." } },
    });
    render(<IntakePage submit={submit} />);
    await fillAndSubmit();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Please check your intake");
    expect(alert).toHaveTextContent(MESSAGES.consentRequired);
  });

  it("shows a safe pipeline failure state and keeps backend detail in the developer panel only", async () => {
    const submit = vi.fn().mockResolvedValue({
      kind: "failure",
      message: MESSAGES.processing,
      diagnostics: { status: 500, body: "Traceback (most recent call last): secret internals" },
    });
    render(<IntakePage submit={submit} />);
    const user = await fillAndSubmit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent(MESSAGES.processing);
    expect(alert).not.toHaveTextContent(/Traceback/);
    expect(screen.queryByRole("heading", { name: "Your intake has been received" })).not.toBeInTheDocument();
    // Backend detail is hidden from the patient view until a reviewer opts in
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Reviewer \/ developer/ }));

    const details = screen.getByText("Developer trace").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByTestId("raw-json")).toHaveTextContent("Traceback");
  });

  it.each([
    ["mock", "LLM Mode: Mock"],
    ["real", "LLM Mode: Real"],
  ] as const)("shows the backend %s mode read-only", async (mode, label) => {
    render(<IntakePage submit={vi.fn()} loadLlmMode={() => Promise.resolve(mode)} />);
    expect(await screen.findByTestId("llm-mode")).toHaveTextContent(label);
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mock|real/i })).not.toBeInTheDocument();
  });

  it("hides the developer trace from the patient view by default", async () => {
    const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data: pipelineResult() });
    render(<IntakePage submit={submit} />);
    await fillAndSubmit();
    await screen.findByRole("heading", { name: "Your intake has been received" });
    expect(screen.queryByText("Developer trace")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Reviewer \/ developer/ })).not.toBeChecked();
  });

  it.each(SCENARIO_PRESETS.map((p) => [p.label, p] as const))(
    "preset %s fills the form but keeps consent and the normal submission",
    async (_label, preset) => {
      const submit = vi.fn().mockResolvedValue({ kind: "success", status: 200, data: pipelineResult() });
      render(<IntakePage submit={submit} />);
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: preset.label }));
      expect(screen.getByLabelText("Your symptoms")).toHaveValue(preset.text);
      expect(screen.getByTestId("preset-expectation")).toHaveTextContent(preset.expect);
      expect(screen.getByRole("checkbox", { name: /I consent/ })).not.toBeChecked();

      // The preset never grants consent: an unticked form submits consent_granted=false through the
      // normal path, where the backend rejects it (consent is enforced server-side)
      await user.click(screen.getByRole("button", { name: "Submit intake" }));
      expect(submit).toHaveBeenLastCalledWith({ text: preset.text, consent_granted: false });

      await user.click(screen.getByRole("checkbox", { name: /I consent/ }));
      await user.click(screen.getByRole("button", { name: "Submit intake" }));
      expect(submit).toHaveBeenLastCalledWith({ text: preset.text, consent_granted: true });
    },
  );
});
