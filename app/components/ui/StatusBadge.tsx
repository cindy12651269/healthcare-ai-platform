// Review-status badge (#68). Known statuses get a readable label and a semantic colour;
// unknown values are shown as-is rather than hidden.

export type StatusTone = "neutral" | "info" | "warning" | "success" | "escalated" | "blocked" | "emergency";

export const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  needs_review: "Needs review",
  reviewed: "Reviewed",
  escalated: "Escalated",
};

const STATUS_TONES: Record<string, StatusTone> = {
  submitted: "info",
  needs_review: "warning",
  reviewed: "success",
  escalated: "escalated",
};

export const statusLabel = (status: string) => STATUS_LABELS[status] ?? status;

export default function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONES[status] ?? "neutral";
  return (
    <span className={`status-badge tone-${tone}`} data-status={status}>
      <span className="status-dot" aria-hidden="true" />
      {statusLabel(status)}
    </span>
  );
}
