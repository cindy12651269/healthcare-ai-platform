from __future__ import annotations
from typing import Any, Dict, List
from jsonschema import validate, ValidationError
import json
from pathlib import Path

# Structured Output Config
REQUIRED_TOP_LEVEL_FIELDS = [
    "trace",
    "compliance",
    "clinical_structuring",
    "agent_decisioning",
    "ehr_interoperability",
    "output_metadata",
]

# Load schema once (deterministic, no runtime variability)
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "llm" / "schemas" / "structured_output.json"
try:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        STRUCTURED_SCHEMA = json.load(f)
except Exception:
    STRUCTURED_SCHEMA = None

# Structured Metrics (Issue 13)
def required_field_presence_rate(output: Dict[str, Any]) -> float:
    present = sum(1 for f in REQUIRED_TOP_LEVEL_FIELDS if f in output)
    return present / len(REQUIRED_TOP_LEVEL_FIELDS)


def compute_coverage(obj: Any) -> float:
    total = 0
    filled = 0

    def walk(x):
        nonlocal total, filled

        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        else:
            total += 1
            if x not in (None, "", [], {}):
                filled += 1

    walk(obj)
    return filled / total if total > 0 else 0.0


def is_schema_valid(output: Dict[str, Any]) -> bool:
    if STRUCTURED_SCHEMA is None:
        return False
    try:
        validate(instance=output, schema=STRUCTURED_SCHEMA)
        return True
    except ValidationError:
        return False

# V1 deterministic safe version: Only checks if symptoms field exists and is non-empty
# No dependency on expected yet → keeps benchmark unchanged
def symptom_consistency(output: Dict[str, Any]) -> float:
    symptoms = output.get("clinical_structuring", {}).get("symptoms", [])
    return 1.0 if isinstance(symptoms, list) and len(symptoms) > 0 else 0.0


# Per-Run Metrics
# Compute metrics for a single pipeline execution.
def compute_run_metrics(
    trace: Dict[str, Any],
    latency_ms: float,
    expected: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    
    success = bool(trace.get("success", False))

    # Safety violations
    safety = trace.get("safety") or {}
    actions = safety.get("actions", [])
    safety_violation_count = len(actions)

    # Retrieval hits
    rag = trace.get("rag") or {}
    chunks = rag.get("chunks", [])
    retrieval_hit_count = len(chunks)

    return {
        "success": success,
        "safety_violation_count": safety_violation_count,
        "retrieval_hit_count": retrieval_hit_count,
        "latency_ms": latency_ms,
    }

# Aggregated Metrics
def compute_aggregate_metrics(run_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:

    total_runs = len(run_metrics)

    if total_runs == 0:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "total_safety_violations": 0,
            "total_retrieval_hits": 0,

            # Issue 13
            "avg_coverage": 0.0,
            "required_field_pass_rate": 0.0,
            "schema_valid_rate": 0.0,
            "avg_symptom_consistency": 0.0,
        }

    success_count = sum(1 for r in run_metrics if r["success"])
    total_latency = sum(r.get("latency_ms", 0.0) for r in run_metrics)
    total_safety = sum(r.get("safety_violation_count", 0) for r in run_metrics)
    total_retrieval = sum(r.get("retrieval_hit_count", 0) for r in run_metrics)

    # Aggregation
    total_coverage = sum(r.get("coverage", 0.0) for r in run_metrics)
    total_required = sum(r.get("required_field_presence", 0.0) for r in run_metrics)
    total_schema_valid = sum(1 for r in run_metrics if r.get("schema_valid"))
    total_symptom = sum(r.get("symptom_consistency", 0.0) for r in run_metrics)

    return {
        "total_runs": total_runs,
        "success_rate": success_count / total_runs,
        "avg_latency_ms": total_latency / total_runs,
        "total_safety_violations": total_safety,
        "total_retrieval_hits": total_retrieval,

        # New metrics
        "avg_coverage": total_coverage / total_runs,
        "required_field_pass_rate": total_required / total_runs,
        "schema_valid_rate": total_schema_valid / total_runs,
        "avg_symptom_consistency": total_symptom / total_runs,
    }