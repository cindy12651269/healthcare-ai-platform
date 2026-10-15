import { Spinner } from "./ui";

// Staged submission feedback (#70). No percentages: neither the cold start (#67) nor the pipeline
// reports progress, so the steps only say what is actually happening.
export type SubmissionPhase =
  | { stage: "waking"; attempt: number; maxAttempts: number }
  | { stage: "processing"; slow: boolean }
  | { stage: "done" };

type StepState = "done" | "current" | "pending";

const ORDER = ["waking", "processing", "done"] as const;

export default function SubmissionProgress({ phase, woke }: { phase: SubmissionPhase; woke: boolean }) {
  const index = ORDER.indexOf(phase.stage);
  const stateOf = (i: number): StepState => (i < index || phase.stage === "done" ? "done" : i === index ? "current" : "pending");

  const steps = [
    // The server was already awake: the step is complete without a wait, and says so
    woke || phase.stage === "waking" ? "Wake the demo server" : "Demo server ready",
    "Process your intake",
    "Submission completed",
  ];

  let message: string;
  if (phase.stage === "waking") {
    message = `Waking the demo server (can take up to a minute)… attempt ${phase.attempt} of ${phase.maxAttempts}. Your intake has not been sent yet.`;
  } else if (phase.stage === "processing") {
    message = phase.slow
      ? "Processing your intake… This is taking longer than usual. Please keep this page open and do not submit again."
      : "Processing your intake…";
  } else {
    message = "Submission completed.";
  }

  return (
    <div className="submission-progress" data-testid="submission-progress" data-stage={phase.stage}>
      <ol className="progress-steps" aria-label="Submission progress">
        {steps.map((label, i) => {
          const state = stateOf(i);
          return (
            <li key={label} data-state={state} aria-current={state === "current" ? "step" : undefined}>
              <span className="progress-marker" aria-hidden="true">
                {state === "done" ? "✓" : i + 1}
              </span>
              <span>
                {label}
                <span className="visually-hidden">{state === "done" ? " (done)" : state === "pending" ? " (not started)" : " (in progress)"}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="status-loading" role="status">
        {phase.stage !== "done" && <Spinner />} {message}
      </p>
    </div>
  );
}
