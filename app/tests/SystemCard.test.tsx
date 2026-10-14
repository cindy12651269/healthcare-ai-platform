import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import SystemCardPage from "../pages/system-card";

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
  known_limitations: ["Rules can miss paraphrases.", "Evaluation sets are tiny and synthetic."],
};

const CATEGORY_LABELS: Record<string, string> = {
  diagnosis_seeking: "Diagnosis seeking",
  emergency_language: "Emergency language",
  phi: "PHI",
  prescription_request: "Prescription request",
};
const humanize = (code: string) => CATEGORY_LABELS[code];
type Row = { cases: number; guard_matches: number; guard_match_rate: number; escalation_matches: number; escalation_match_rate: number; known_gaps: number };
const rowText = (name: string, c: Row) =>
  `${name}${c.cases}${c.guard_matches}/${c.cases} · ${c.guard_match_rate.toFixed(2)}` +
  `${c.escalation_matches}/${c.cases} · ${c.escalation_match_rate.toFixed(2)}${c.known_gaps}`;

describe("System card page", () => {
  it("shows the not-a-medical-device statement, mode, rules and limitations", async () => {
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(CARD)} />);

    expect(screen.getByTestId("not-a-medical-device")).toHaveTextContent("Not a medical device");
    expect(await screen.findByTestId("execution-mode")).toHaveTextContent("mock");
    expect(screen.getByTestId("threshold")).toHaveTextContent("0.5");
    const rules = screen.getByTestId("escalation-rules");
    expect(within(rules).getByText("low_confidence")).toBeInTheDocument();
    expect(within(rules).getByText("Low structuring confidence")).toBeInTheDocument();
    expect(screen.getByTestId("review-rules")).toHaveTextContent("Every other transition is rejected");
    expect(screen.getByTestId("webhook-condition")).toHaveTextContent("only when a receiver is configured");
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem").map((li) => li.textContent)).toEqual(
      CARD.known_limitations,
    );
    // Sections a visitor (and the dashboard's evidence links) can jump to
    const nav = screen.getByRole("navigation", { name: "System card sections" });
    for (const a of within(nav).getAllByRole("link")) {
      expect(document.getElementById(a.getAttribute("href")!.slice(1))).not.toBeNull();
    }
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("renders every committed evaluation value exactly, with sample sizes and caveats", async () => {
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(CARD)} />);
    const table = await screen.findByTestId("safety-table");
    const safety = SNAPSHOT.safety_escalation;

    // Per category and total: cases, matches out of cases, committed rate, known gaps
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      ...Object.entries(safety.categories as Record<string, Row>).map(([name, c]) => rowText(humanize(name), c)),
      rowText("Total", safety.aggregate),
    ]);

    const stats = screen.getByTestId("safety-stats");
    expect(stats).toHaveTextContent(`Synthetic cases${safety.aggregate.cases}`);
    expect(stats).toHaveTextContent(
      `Guard match${safety.aggregate.guard_match_rate.toFixed(2)}${safety.aggregate.guard_matches} of ${safety.aggregate.cases}`,
    );
    expect(stats).toHaveTextContent(`Known gaps${safety.aggregate.known_gaps}`);
    expect(screen.getByTestId("safety-caveat")).toHaveTextContent(safety.limitation);

    const ext = SNAPSHOT.extraction.aggregate;
    expect(screen.getByTestId("extraction-metrics")).toHaveTextContent(
      `${ext.cases} cases · micro precision ${ext.micro_precision.toFixed(2)} · micro recall ${ext.micro_recall.toFixed(2)} · ` +
        `macro precision ${ext.macro_precision.toFixed(2)} · macro recall ${ext.macro_recall.toFixed(2)}`,
    );
    expect(screen.getByTestId("extraction-stats")).toHaveTextContent(
      `Symptom matches${ext.true_positives}${ext.false_positives} false positive · ${ext.false_negatives} missed`,
    );
    expect(screen.getByTestId("extraction-caveat")).toHaveTextContent(SNAPSHOT.extraction.limitation);
    expect(screen.getByTestId("evaluation-source")).toHaveTextContent(SNAPSHOT.source);
  });

  it("shows missing evaluation data as not reported instead of filling it in", async () => {
    const card = { ...CARD, evaluation: { safety_escalation: { aggregate: { cases: 16 } } } };
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(card)} />);
    const stats = await screen.findByTestId("safety-stats");
    expect(stats).toHaveTextContent("Synthetic cases16");
    expect(stats).toHaveTextContent("Guard matchNot reported");
    expect(screen.getByTestId("extraction-metrics")).toHaveTextContent("Not reported cases");
    expect(screen.getByTestId("safety-caveat")).toHaveTextContent("Not reported");
    expect(document.body.textContent).not.toMatch(/1\.00/);
  });

  it("shows loading and then an error state when the API is unavailable", async () => {
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(null)} />);
    expect(screen.getByText("Loading system card…")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    // The statement does not depend on the API
    expect(screen.getByTestId("not-a-medical-device")).toBeInTheDocument();
  });
});
