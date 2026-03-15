from __future__ import annotations
from typing import Any, Dict, List

# Per-Run Metrics
# Compute metrics for a single pipeline execution.
def compute_run_metrics(trace: Dict[str, Any], latency_ms: float) -> Dict[str, Any]:
    """
    Parameters:
    trace : Dict[str, Any]
        Trace dictionary returned by HealthcarePipeline.run()
    latency_ms : float
        Execution latency measured by the benchmark runner

    Returns:
    Dict[str, Any]
        Per-run metrics record
    """

    success = bool(trace.get("success", False))

    # Safety violations = number of guard actions
    safety = trace.get("safety") or {}
    actions = safety.get("actions", [])
    safety_violation_count = len(actions)

    # Retrieval hits = number of retrieved chunks
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
# Compute aggregated benchmark metrics across all runs.
def compute_aggregate_metrics(run_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parameters
    run_metrics : List[Dict[str, Any]]
        List of per-run metric dictionaries

    Returns
    Dict[str, Any]
        Aggregated metrics summary
    """

    total_runs = len(run_metrics)

    if total_runs == 0:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "total_safety_violations": 0,
            "total_retrieval_hits": 0,
        }

    success_count = sum(1 for r in run_metrics if r["success"])
    total_latency = sum(r.get("latency_ms", 0.0) for r in run_metrics)
    total_safety = sum(r.get("safety_violation_count", 0) for r in run_metrics)
    total_retrieval = sum(r.get("retrieval_hit_count", 0) for r in run_metrics)

    success_rate = success_count / total_runs
    avg_latency = total_latency / total_runs

    return {
        "total_runs": total_runs,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency,
        "total_safety_violations": total_safety,
        "total_retrieval_hits": total_retrieval,
    }