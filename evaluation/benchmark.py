from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
from agents.pipeline import HealthcarePipeline
from evaluation.metrics import compute_run_metrics, compute_aggregate_metrics
from agents.retrieval_agent import RetrievalResult, RetrievalChunk
from observability.metrics import compute_aggregate_latency

# Mock Agents (Deterministic): Deterministic structuring agent.
# Must match StructuredHealthOutput schema to support Issue 13 evaluation metrics.
class MockStructuringAgent:

    def run(self, intake_dict):

        return {
            "trace": {
                "input_id": intake_dict.get("input_id"),
                "user_id": intake_dict.get("user_id"),
                "timestamp": intake_dict.get("timestamp"),
                "source": intake_dict.get("source"),
                "input_type": intake_dict.get("input_type"),
            },

            "compliance": {
                "contains_phi": intake_dict.get("contains_phi", False),
                "consent_granted": intake_dict.get("consent_granted", True),
                "data_zone": "public_zone",
                "audit_required": False,
            },

            "clinical_structuring": {
                "chief_complaint": "general symptoms",
                "symptoms": ["fatigue"],
                "clinical_summary": "mock summary",
                "confidence_level": 0.9,
            },

            "agent_decisioning": {},

            "ehr_interoperability": {},

            "output_metadata": {
                "generated_at": "2025-01-01T00:00:00Z",
                "model_version": "mock",
                "prompt_version": "v1",
            },
        }


# Deterministic output agent.
class MockOutputAgent:

    def run(self, structured_data, retrieval_context=None):
        return {
            "report": {"summary": "mock report"},
            "_safety": None,
        }


# Always returns 2 chunks → deterministic retrieval hits.
class MockRetrievalAgent:

    def run(self, structured_data, top_k=3):
        chunks = [
            RetrievalChunk(text="doc1", source="kb", score=0.9),
            RetrievalChunk(text="doc2", source="kb", score=0.8),
        ]

        return RetrievalResult(
            query="mock query",
            chunks=chunks,
            k=top_k,
            hit_count=2,
        )


# Paths
ROOT = Path(__file__).resolve().parent
TEST_CASES_FILE = ROOT / "test_cases.json"
RESULT_DIR = ROOT / "results"


# Load deterministic test cases.
def load_cases() -> List[Dict[str, Any]]:
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


# Pipeline Factory
def create_pipeline(mode: str, rag_enabled: bool) -> HealthcarePipeline:

    if mode != "mock":
        raise NotImplementedError("live mode not implemented")

    return HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=MockRetrievalAgent() if rag_enabled else None,
        enable_retrieval=rag_enabled,
    )

def _standardize_pipeline_metrics(
    trace: Dict[str, Any],
    *,
    mode: str,
) -> Dict[str, Any]:
    """
    Normalize pipeline metrics for benchmark output.

    In mock mode, all latency values are forced to 0.0 to preserve
    deterministic benchmark behavior across runs.
    """
    raw_metrics = trace.get("metrics", {})

    metrics = {
        "intake_ms": float(raw_metrics.get("intake_ms", 0.0)),
        "structuring_ms": float(raw_metrics.get("structuring_ms", 0.0)),
        "retrieval_ms": float(raw_metrics.get("retrieval_ms", 0.0)),
        "output_ms": float(raw_metrics.get("output_ms", 0.0)),
        "safety_ms": float(raw_metrics.get("safety_ms", 0.0)),
        "persistence_ms": float(raw_metrics.get("persistence_ms", 0.0)),
        "latency_ms": float(raw_metrics.get("latency_ms", 0.0)),
        "safety_violation_count": int(raw_metrics.get("safety_violation_count", 0)),
        "retrieval_hit_count": int(raw_metrics.get("retrieval_hit_count", 0)),
    }

    if mode == "mock":
        metrics["intake_ms"] = 0.0
        metrics["structuring_ms"] = 0.0
        metrics["retrieval_ms"] = 0.0
        metrics["output_ms"] = 0.0
        metrics["safety_ms"] = 0.0
        metrics["persistence_ms"] = 0.0
        metrics["latency_ms"] = 0.0

    return metrics

# Benchmark Runner
def run_benchmark(mode: str, rag: bool) -> Dict[str, Any]:

    cases = load_cases()
    pipeline = create_pipeline(mode=mode, rag_enabled=rag)

    run_results: List[Dict[str, Any]] = []
    evaluation_run_metrics: List[Dict[str, Any]] = []
    pipeline_run_metrics: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases):

        case_id = case["id"]
        case_input = case["input"]

        # Expected output for structured scoring (Issue 13)
        expected = case.get("expected", {})

        raw_text = case_input["raw_text"]
        meta = case_input

        # Stable deterministic run_id
        run_id = f"{case_id}:{mode}:{'rag' if rag else 'norag'}"

        # Fixed seed per case
        seed = 42 + idx

        trace = pipeline.run(
            raw_text=raw_text,
            meta=meta,
            enable_rag=rag,
            persistence_enabled=False,
            seed=seed,
            run_id=run_id,
        )

        # Benchmark-facing pipeline metrics (Issue 15)
        standardized_metrics = _standardize_pipeline_metrics(
            trace,
            mode=mode,
        )
        pipeline_run_metrics.append(standardized_metrics)

        # Keep Issue 12 + Issue 13 evaluation metrics deterministic
        evaluation_latency_ms = standardized_metrics["latency_ms"]

        evaluation_metrics = compute_run_metrics(
            trace,
            evaluation_latency_ms,
            expected=expected,
        )
        evaluation_run_metrics.append(evaluation_metrics)

        run_results.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "metrics": standardized_metrics,
                "evaluation_metrics": evaluation_metrics,
            }
        )

    aggregated = compute_aggregate_metrics(evaluation_run_metrics)

    latency_aggregated = compute_aggregate_latency(pipeline_run_metrics)
    aggregated.update(latency_aggregated)

    return {
        "runs": run_results,
        "aggregated": aggregated,
    }


# Output
def print_summary(results: Dict[str, Any]):

    agg = results["aggregated"]

    print("\nBenchmark Summary")
    print("----------------------------")
    print(f"Total runs: {agg['total_runs']}")
    print(f"Success rate: {agg['success_rate']:.2f}")
    print(f"Avg latency (ms): {agg['avg_latency_ms']:.2f}")
    print(f"P50 latency (ms): {agg.get('p50_latency_ms', 0.0):.2f}")
    print(f"P95 latency (ms): {agg.get('p95_latency_ms', 0.0):.2f}")
    print(f"Safety violations: {agg['total_safety_violations']}")
    print(f"Retrieval hits: {agg['total_retrieval_hits']}")

    # Issue 13 metrics
    print(f"Avg coverage: {agg.get('avg_coverage', 0.0):.2f}")
    print(f"Required field pass rate: {agg.get('required_field_pass_rate', 0.0):.2f}")
    print(f"Schema valid rate: {agg.get('schema_valid_rate', 0.0):.2f}")
    print(f"Avg symptom consistency: {agg.get('avg_symptom_consistency', 0.0):.2f}")

    print("----------------------------\n")


def save_results(results: Dict[str, Any], output_file: str):

    RESULT_DIR.mkdir(exist_ok=True)

    path = RESULT_DIR / output_file

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print(f"Results saved to {path}")


# CLI
def main():

    parser = argparse.ArgumentParser(
        description="HealthcarePipeline benchmark harness"
    )

    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--rag", choices=["on", "off"], default="off")
    parser.add_argument("--out", default="benchmark_results.json")

    args = parser.parse_args()

    results = run_benchmark(
        mode=args.mode,
        rag=(args.rag == "on"),
    )

    print_summary(results)
    save_results(results, args.out)


if __name__ == "__main__":
    main()