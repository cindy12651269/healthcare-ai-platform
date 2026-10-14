import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import SystemCardPage from "../pages/system-card";
import Landing from "../pages/index";

// The API answers /health at once; cold-start behaviour is covered in ApiStatus.test.tsx
const apiReady = async () => "ready" as const;

// The committed snapshot served by GET /api/system-card (evaluation/system_card_results.json)
const SNAPSHOT = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "evaluation", "system_card_results.json"), "utf8"),
);

const CARD = {
  not_a_medical_device: "Not a medical device. Portfolio demonstration.",
  execution_mode: "mock",
  pipeline_stages: [{ stage: "Intake", description: "Validates the submission." }],
  safety_rules: [{ action: "block_diagnosis", description: "Blocks diagnostic certainty." }],
  escalation_rules: [
    { reason: "emergency_signal", rule: "Emergency language" },
    { reason: "low_confidence", rule: "Structuring confidence below 0.5" },
  ],
  low_confidence_threshold: 0.5,
  evaluation: SNAPSHOT,
  known_limitations: ["Rules can miss paraphrases."],
};

describe("System card page", () => {
  it("shows the not-a-medical-device statement, mode, rules and the committed evaluation numbers", async () => {
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(CARD)} />);

    expect(screen.getByTestId("not-a-medical-device")).toHaveTextContent("Not a medical device");
    expect(await screen.findByTestId("execution-mode")).toHaveTextContent("mock");
    expect(screen.getByTestId("threshold")).toHaveTextContent("0.5");
    expect(within(screen.getByTestId("escalation-rules")).getByText("low_confidence")).toBeInTheDocument();

    const agg = SNAPSHOT.safety_escalation.aggregate;
    const total = within(screen.getByTestId("safety-table")).getByText("Total").closest("tr")!;
    expect(total).toHaveTextContent(
      `Total${agg.cases}${agg.guard_match_rate.toFixed(2)}${agg.escalation_match_rate.toFixed(2)}${agg.known_gaps}`,
    );
    const ext = SNAPSHOT.extraction.aggregate;
    expect(screen.getByTestId("extraction-metrics")).toHaveTextContent(
      `${ext.cases} cases · micro precision ${ext.micro_precision.toFixed(2)} · micro recall ${ext.micro_recall.toFixed(2)}`,
    );
    expect(screen.getByText(SNAPSHOT.extraction.limitation)).toBeInTheDocument();
  });

  it("shows loading and then an error state when the API is unavailable", async () => {
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(null)} />);
    expect(screen.getByText("Loading system card…")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    // The statement does not depend on the API
    expect(screen.getByTestId("not-a-medical-device")).toBeInTheDocument();
  });
});

describe("Guided demo landing", () => {
  it("offers patient, staff and system card entry points and explains the workflow", () => {
    render(<Landing checkApi={apiReady} demoMode={false} />);
    const entry = within(screen.getByRole("heading", { name: "Start here" }).closest("section")!);
    expect(entry.getByRole("link", { name: /^Patient/ })).toHaveAttribute("href", "/intake");
    expect(entry.getByRole("link", { name: /^Staff/ })).toHaveAttribute("href", "/staff");
    // #67: visitors are told up front that staff access needs an operator-issued token
    expect(entry.getByRole("link", { name: /^Staff/ })).toHaveTextContent("access token issued on request by the demo operator");
    expect(entry.getByRole("link", { name: /^System card/ })).toHaveAttribute("href", "/system-card");
    expect(within(screen.getByRole("navigation", { name: "Demo sections" })).getAllByRole("link")).toHaveLength(4);
    const steps = within(screen.getByTestId("workflow")).getAllByRole("listitem").map((li) => li.textContent);
    expect(steps.map((t) => t!.split(" — ")[0])).toEqual([
      "Patient intake", "AI processing", "Safety & escalation", "Staff review", "Evidence timeline", "FHIR export",
    ]);
  });

  it("shows demo staff identities only when the demo flag is set, and never a token", () => {
    const { unmount } = render(<Landing checkApi={apiReady} demoMode={false} />);
    expect(screen.queryByTestId("demo-staff")).not.toBeInTheDocument();
    unmount();

    render(<Landing checkApi={apiReady} demoMode />);
    const panel = screen.getByTestId("demo-staff");
    expect(panel).toHaveTextContent("demo-staff-a");
    expect(panel).toHaveTextContent("demo-clinic-b");
    expect(panel.textContent).not.toMatch(/v1\.[A-Za-z0-9_-]{20,}/);
  });
});
