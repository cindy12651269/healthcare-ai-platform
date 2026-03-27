from dataclasses import dataclass, field
from typing import Optional


@dataclass
# Centralized trace context for observability. This object is intended to collect metrics during pipeline execution
# Serve as single source of truth for observability, and can Be passed across agents if needed (future extension)
class TraceContext:
    # Core metrics
    safety_violation_count: int = 0
    retrieval_hit_count: int = 0
    latency_ms: Optional[int] = None

    # Optional metadata (future use)
    run_id: Optional[str] = None
    error: Optional[str] = None

    # Reset context (useful for reuse or testing)
    def reset(self) -> None:
        self.safety_violation_count = 0
        self.retrieval_hit_count = 0
        self.latency_ms = None
        self.error = None


#