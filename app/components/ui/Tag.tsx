import { ReactNode } from "react";
import { StatusTone } from "./StatusBadge";

// Small label in one of the semantic status tones (#69: maturity and real-vs-mock labels)
export default function Tag({ tone = "neutral", children }: { tone?: StatusTone; children: ReactNode }) {
  return <span className={`tag tone-${tone}`}>{children}</span>;
}
