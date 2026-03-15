from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
from agents.pipeline import HealthcarePipeline
from evaluation.metrics import compute_run_metrics, compute_aggregate_metrics

# Mock agents for deterministic benchmark mode
# Deterministic structuring stub for CI-safe benchmark runs
class MockStructuringAgent:
    
    def run(self, intake_dict):
        return {
            "chief_complaint": "general symptoms",
            "symptoms": ["fatigue"],
            "clinical_summary": "mock summary",
            "confidence_level": 0.9,
        }

# Deterministic output stub for CI-safe benchmark runs.
class MockOutputAgent:
    
    def run(self, structured_data, retrieval_context=None):
        return {
            "report": {"summary": "mock report"},
            "_safety": None,
        }

# Deterministic retrieval stub that always returns two chunks.
class MockRetrievalAgent:

    def run(self, structured_data, top_k=3):
        return {
            "query": "mock query",
            "chunks": [
                {"text": "doc1", "score": 0.9, "source": "kb"},
                {"text": "doc2", "score": 0.8, "source": "kb"},
            ],
        }



# File system paths
ROOT = Path(__file__).resolve().parent
TEST_CASES_FILE = ROOT / "test_cases.json"
RESULT_DIR = ROOT / "results"


# Case loading
# Load deterministic benchmark cases from JSON.
def load_cases() -> List[Dict[str, Any]]:
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]



# Pipeline factory
# Create a pipeline instance for benchmark execution.

def create_pipeline(mode: str, rag_enabled: bool) -> HealthcarePipeline:
    if mode != "mock":
        raise NotImplementedError("live mode is not implemented yet")

    struct_agent = MockStructuringAgent()
    output_agent = MockOutputAgent()
    retrieval_agent = MockRetrievalAgent() if rag_enabled else None

    return HealthcarePipeline(
        structuring_agent=struct_agent,
        output_agent=output_agent,
        retrieval_agent=retrieval_agent,
        enable_retrieval=rag_enabled,
    )



# Benchmark runner: Run all benchmark cases sequentially and return deterministic results.
# Determinism guarantees:fixed seed per case, stable run_id, stable case order from test_cases.json, fixed latency in mock mode
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

        # Stable run_id for deterministic CI output
        run_id = f"{case_id}:{mode}:{'rag' if rag else 'norag'}"

        # Fixed seed per case for deterministic execution
        seed = 42 + idx

        trace = pipeline.run(
            raw_text=raw_text,
            meta=meta,
            enable_rag=rag,
            persistence_enabled=False,
            seed=seed,
            run_id=run_id,
        )

        # In mock mode, latency must be deterministic for CI reproducibility.
        latency_ms = 0.0 if mode == "mock" else trace["telemetry"]["latency_ms"]

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

# Console output: Print a compact human-readable benchmark summary.
def print_summary(results: Dict[str, Any]) -> None:

    agg = results["aggregated"]

    print("\nBenchmark Summary")
    print("----------------------------")
    print(f"Total runs: {agg['total_runs']}")
    print(f"Success rate: {agg['success_rate']:.2f}")
    print(f"Avg latency (ms): {agg['avg_latency_ms']:.2f}")
    print(f"Safety violations: {agg['total_safety_violations']}")
    print(f"Retrieval hits: {agg['total_retrieval_hits']}")
    print("----------------------------\n")


# JSON output: Save benchmark results as sorted JSON under evaluation/results/.
def save_results(results: Dict[str, Any], output_file: str) -> None:

    RESULT_DIR.mkdir(exist_ok=True)

    path = RESULT_DIR / output_file

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print(f"Results saved to {path}")


# CLI entry point for running deterministic benchmark harness.
def main() -> None:
    parser = argparse.ArgumentParser(
        description="HealthcarePipeline benchmark harness"
    )

    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="Execution mode (default: mock)",
    )

    parser.add_argument(
        "--rag",
        choices=["on", "off"],
        default="off",
        help="Enable RAG retrieval",
    )

    parser.add_argument(
        "--out",
        default="benchmark_results.json",
        help="Output JSON file name",
    )

    args = parser.parse_args()
    rag_enabled = args.rag == "on"

    results = run_benchmark(
        mode=args.mode,
        rag=rag_enabled,
    )

    print_summary(results)
    save_results(results, args.out)


if __name__ == "__main__":
    main()