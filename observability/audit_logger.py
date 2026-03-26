from __future__ import annotations
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os


# Audit Event Schema Definition
@dataclass
class AuditEvent:
    run_id: str
    timestamp: str
    status: str  # "success" | "failure"
    flags: Dict[str, Any]
    latency_ms: int
    safety_violation_count: int
    retrieval_hit_count: int
    error: Optional[str] = None

# Helpers
# Return current UTC time in ISO format
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Build a standardized audit event.
def build_event(
    run_id: str,
    status: str,
    latency_ms: int,
    safety_violation_count: int,
    retrieval_hit_count: int,
    flags: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> AuditEvent:
    
    return AuditEvent(
        run_id=run_id,
        timestamp=now_iso(),
        status=status,
        latency_ms=latency_ms,
        safety_violation_count=safety_violation_count,
        retrieval_hit_count=retrieval_hit_count,
        flags=flags or {},
        error=error,
    )


# Logger Configuration
ENABLE_FILE_LOG = os.getenv("ENABLE_AUDIT_JSONL", "true").lower() == "true"
JSONL_PATH = os.getenv("AUDIT_LOG_PATH", "audit.jsonl")


# Logger
# Log audit event to console and optional JSONL file.
def log_run(event: AuditEvent) -> None:
   
    try:
        record = asdict(event)
        line = json.dumps(record, ensure_ascii=False)

        # Console output
        print(line)

        # Optional JSONL persistence
        if ENABLE_FILE_LOG:
            with open(JSONL_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    except Exception as e:
        # Fail-safe: logging should never break the pipeline
        print(f"[AuditLoggerError] Failed to log event: {e}")
