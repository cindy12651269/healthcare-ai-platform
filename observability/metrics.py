from typing import Dict, List, Any
import math


# 1. Per-run Metrics Contract (STRICT)
def build_run_metrics(
    *,
    intake_ms: float,
    structuring_ms: float,
    retrieval_ms: float,
    output_ms: float,
    safety_ms: float,
    persistence_ms: float,
    latency_ms: float,
    safety_violation_count: int,
    retrieval_hit_count: int,
) -> Dict[str, Any]:
    """
    Strict metrics contract for Issue 15. All fields are REQUIRED.
    Pipeline must always provide values (use 0.0 if stage not executed).
    """
    return {
        # Stage-level latency 
        "intake_ms": intake_ms,
        "structuring_ms": structuring_ms,
        "retrieval_ms": retrieval_ms,
        "output_ms": output_ms,
        "safety_ms": safety_ms,
        "persistence_ms": persistence_ms,

        # Total 
        "latency_ms": latency_ms,

        # Existing metrics 
        "safety_violation_count": safety_violation_count,
        "retrieval_hit_count": retrieval_hit_count,
    }


# 2. Percentile Helper (deterministic)
def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0

    values = sorted(values)

    k = (len(values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return values[int(k)]

    return values[f] + (values[c] - values[f]) * (k - f)


# 3. Aggregate Metrics
def compute_aggregate_latency(run_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [m["latency_ms"] for m in run_metrics]

    if not latencies:
        return {
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "num_runs": 0,
        }

    return {
        "avg_latency_ms": sum(latencies) / len(latencies),
        "p50_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "num_runs": len(latencies),
    }