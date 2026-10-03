import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IntakePage from "../pages/index";
import { IngestOutcome, MESSAGES } from "../services/api";
import { pipelineResult } from "./fixtures";

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
    await fillAndSubmit();

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
    await fillAndSubmit();
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
    await fillAndSubmit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent(MESSAGES.processing);
    expect(alert).not.toHaveTextContent(/Traceback/);
    expect(screen.queryByRole("heading", { name: "Your intake has been received" })).not.toBeInTheDocument();

    const details = screen.getByText("Developer trace").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByTestId("raw-json")).toHaveTextContent("Traceback");
  });
});
