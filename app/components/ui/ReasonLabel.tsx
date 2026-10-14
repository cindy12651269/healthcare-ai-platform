import { StatusTone } from "./StatusBadge";

// Escalation reason codes (agents/escalation.py, #29) → readable labels. The code stays visible
// next to the label so staff and reviewers can match it to the rules and audit records.
export const REASON_LABELS: Record<string, { label: string; tone: StatusTone }> = {
  emergency_signal: { label: "Emergency signal", tone: "emergency" },
  blocked_diagnosis: { label: "Blocked: diagnostic language", tone: "blocked" },
  blocked_prescription: { label: "Blocked: prescription or dosing", tone: "blocked" },
  low_confidence: { label: "Low structuring confidence", tone: "warning" },
};

export default function ReasonLabel({ code }: { code: string }) {
  const known = REASON_LABELS[code];
  if (!known) {
    return (
      <span className="reason tone-neutral">
        <code className="reason-code">{code}</code>
      </span>
    );
  }
  return (
    <span className={`reason tone-${known.tone}`}>
      <span className="reason-label">{known.label}</span> <code className="reason-code">{code}</code>
    </span>
  );
}

// Stored reasons are comma-separated (health_records.escalation_reason)
export function ReasonList({ reasons, empty = "—" }: { reasons: string | string[] | null | undefined; empty?: string }) {
  const codes = (Array.isArray(reasons) ? reasons : (reasons ?? "").split(",")).map((r) => r.trim()).filter(Boolean);
  if (codes.length === 0) return <>{empty}</>;
  return (
    <span className="reason-list">
      {codes.map((c) => (
        <ReasonLabel key={c} code={c} />
      ))}
    </span>
  );
}
