from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Allow `python evaluation/benchmark.py` as well as `python -m evaluation.benchmark`
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from typing import Any, Dict, List
from agents.pipeline import HealthcarePipeline
from agents.structuring_agent import StructuringAgent
from agents.output_agent import OutputAgent
from api.config import get_settings
from llm.provider import LLMConfigurationError, check_llm_config
from evaluation.metrics import (
    compute_run_metrics,
    compute_aggregate_metrics,
    compute_safety_case_metrics,
    compute_safety_category_metrics,
)
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
SAFETY_CASES_FILE = ROOT / "safety_cases.json"
RESULT_DIR = ROOT / "results"


# Load deterministic test cases.
def load_cases() -> List[Dict[str, Any]]:
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


# Pipeline Factory
# mock: deterministic benchmark doubles (CI). real: the production agents on the OpenAI provider;
# refuses to start without valid provider configuration (opt-in, never part of CI).
def create_pipeline(mode: str, rag_enabled: bool) -> HealthcarePipeline:

    if mode == "mock":
        structuring_agent, output_agent = MockStructuringAgent(), MockOutputAgent()
    elif mode == "real":
        check_llm_config(get_settings().model_copy(update={"llm_mode": "real"}))
        structuring_agent, output_agent = StructuringAgent(mode="real"), OutputAgent(mode="real")
    else:
        raise LLMConfigurationError(f"Unsupported benchmark mode {mode!r}; expected mock or real")

    return HealthcarePipeline(
        structuring_agent=structuring_agent,
        output_agent=output_agent,
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
def run_benchmark(mode: str, rag: bool, limit: int | None = None) -> Dict[str, Any]:

    pipeline = create_pipeline(mode=mode, rag_enabled=rag)
    cases = load_cases()[:limit] if limit else load_cases()

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
        "mode": mode,
        "runs": run_results,
        "aggregated": aggregated,
    }


# Safety & Escalation Suite (Issue #32)
REQUIRED_SAFETY_CATEGORIES = ("diagnosis_seeking", "prescription_request", "emergency_language", "phi")
SAFETY_CASE_FIELDS = ("id", "category", "input", "expected_guard_actions", "expected_escalation")


class SafetyCasesError(ValueError):
    pass


# Load the labelled set; refuses to run if a required category or a label is missing.
def load_safety_cases(path: Path = SAFETY_CASES_FILE) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    for case in cases:
        missing = [k for k in SAFETY_CASE_FIELDS if k not in case]
        if missing:
            raise SafetyCasesError(f"Safety case {case.get('id', '?')!r} is missing {missing}")
        esc = case["expected_escalation"]
        if not isinstance(esc, dict) or "required" not in esc or "reasons" not in esc:
            raise SafetyCasesError(f"Safety case {case['id']!r} has no expected escalation required/reasons")

    absent = sorted(set(REQUIRED_SAFETY_CATEGORIES) - {c["category"] for c in cases})
    if absent:
        raise SafetyCasesError(f"Safety set is missing required categories: {absent}")
    return cases


# The production agents in deterministic mock mode, so the real output guard and escalation rules run.
# (The benchmark doubles above bypass the guard, so they cannot measure it.) No API key, no network.
def create_safety_pipeline() -> HealthcarePipeline:
    return HealthcarePipeline(
        structuring_agent=StructuringAgent(mode="mock"),
        output_agent=OutputAgent(mode="mock"),
        retrieval_agent=None,
        enable_retrieval=False,
    )


def run_safety_benchmark(cases: List[Dict[str, Any]] | None = None, pipeline: HealthcarePipeline | None = None) -> Dict[str, Any]:
    cases = load_safety_cases() if cases is None else cases
    pipeline = pipeline or create_safety_pipeline()

    case_metrics: List[Dict[str, Any]] = []
    for idx, case in enumerate(cases):
        trace = pipeline.run(
            raw_text=case["input"],
            meta={
                "input_id": f"safety_{idx:03d}",
                "user_id": "safety_eval",
                "source": "web",
                "input_type": "chat",
                "timestamp": "2025-01-01T00:00:00Z",
                "consent_granted": True,
            },
            enable_rag=False,
            persistence_enabled=False,
            seed=42 + idx,
            run_id=f"{case['id']}:mock:safety",
        )
        case_metrics.append(compute_safety_case_metrics(trace, case))

    summary = compute_safety_category_metrics(case_metrics)
    return {
        "mode": "mock",
        "suite": "safety",
        "runs": case_metrics,
        "categories": summary["categories"],
        "aggregated": summary["aggregate"],
    }


def print_safety_summary(results: Dict[str, Any]):

    print("\nSafety & Escalation Summary")
    print("----------------------------")
    print(f"{'category':<22}{'cases':>6}{'guard':>8}{'rate':>7}{'escal.':>8}{'rate':>7}{'gaps':>6}")
    rows = list(results["categories"].items()) + [("TOTAL", results["aggregated"])]
    for name, c in rows:
        print(
            f"{name:<22}{c['cases']:>6}{c['guard_matches']:>8}{c['guard_match_rate']:>7.2f}"
            f"{c['escalation_matches']:>8}{c['escalation_match_rate']:>7.2f}{c['known_gaps']:>6}"
        )
    print("----------------------------\n")


# Output
def print_summary(results: Dict[str, Any]):

    agg = results["aggregated"]

    print("\nBenchmark Summary")
    print("----------------------------")
    print(f"mode: {results.get('mode', 'mock')}")
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

    parser.add_argument("--suite", choices=["pipeline", "safety"], default="pipeline", help="safety: labelled safety & escalation set (Issue #32, mock only)")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--rag", choices=["on", "off"], default="off")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases (keeps real-mode API usage small)")
    parser.add_argument("--out", default=None, help="default: benchmark_results.json (mock) / benchmark_results_real.json (real)")

    args = parser.parse_args()

    if args.suite == "safety":
        if args.mode != "mock" or args.rag != "off":
            raise SystemExit("The safety suite runs in mock mode with RAG off only")
        try:
            results = run_safety_benchmark()
        except SafetyCasesError as e:
            raise SystemExit(f"Safety benchmark refused to start: {e}")
        print_safety_summary(results)
        save_results(results, args.out or "safety_results.json")
        return

    try:
        results = run_benchmark(
            mode=args.mode,
            rag=(args.rag == "on"),
            limit=args.limit,
        )
    except LLMConfigurationError as e:
        raise SystemExit(f"mode: {args.mode}\nBenchmark refused to start: {e}")

    print_summary(results)
    save_results(results, args.out or ("benchmark_results.json" if args.mode == "mock" else "benchmark_results_real.json"))


if __name__ == "__main__":
    main()