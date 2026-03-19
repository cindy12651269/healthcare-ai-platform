from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
from agents.pipeline import HealthcarePipeline
from evaluation.metrics import compute_run_metrics, compute_aggregate_metrics


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
        return {
            "query": "mock query",
            "chunks": [
                {"text": "doc1", "score": 0.9, "source": "kb"},
                {"text": "doc2", "score": 0.8, "source": "kb"},
            ],
        }

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

# Benchmark Runner
def run_benchmark(mode: str, rag: bool) -> Dict[str, Any]:

    cases = load_cases()
    pipeline = create_pipeline(mode=mode, rag_enabled=rag)

    run_results: List[Dict[str, Any]] = []
    run_metrics: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases):

        case_id = case["id"]
        case_input = case["input"]

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

        # Deterministic latency (CI-safe)
        latency_ms = 0.0

        metrics = compute_run_metrics(trace, latency_ms)

        run_metrics.append(metrics)

        run_results.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "metrics": metrics,
            }
        )

    aggregated = compute_aggregate_metrics(run_metrics)

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
    print(f"Safety violations: {agg['total_safety_violations']}")
    print(f"Retrieval hits: {agg['total_retrieval_hits']}")
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