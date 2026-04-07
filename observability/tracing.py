from dataclasses import dataclass
from typing import Optional


@dataclass
class TraceContext:
   
    # Core metrics 
    safety_violation_count: int = 0
    retrieval_hit_count: int = 0
    latency_ms: Optional[int] = None

    # Stage-level latency (Issue 15)
    intake_ms: float = 0.0
    structuring_ms: float = 0.0
    retrieval_ms: float = 0.0
    output_ms: float = 0.0
    safety_ms: float = 0.0
    persistence_ms: float = 0.0


    # Metadata (keep unchanged)
    run_id: Optional[str] = None
    error: Optional[str] = None

    # Reset (CRITICAL: must include new fields)
    def reset(self) -> None:
        # Core
        self.safety_violation_count = 0
        self.retrieval_hit_count = 0
        self.latency_ms = None

        # Stage-level
        self.intake_ms = 0.0
        self.structuring_ms = 0.0
        self.retrieval_ms = 0.0
        self.output_ms = 0.0
        self.safety_ms = 0.0
        self.persistence_ms = 0.0

        # Metadata
        self.error = None