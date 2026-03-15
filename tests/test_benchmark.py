from evaluation.benchmark import run_benchmark

# Benchmark should run successfully without retrieval.
def test_benchmark_without_rag():
    results = run_benchmark(
        mode="mock",
        rag=False,
    )

    agg = results["aggregated"]

    assert agg["total_runs"] == 6
    assert agg["success_rate"] == 1.0
    assert agg["total_retrieval_hits"] == 0
    assert agg["total_safety_violations"] == 0
    assert agg["avg_latency_ms"] == 0.0

# Benchmark should count deterministic retrieval hits when RAG is enabled.
def test_benchmark_with_rag():
    results = run_benchmark(
        mode="mock",
        rag=True,
    )

    agg = results["aggregated"]

    assert agg["total_runs"] == 6
    assert agg["success_rate"] == 1.0

    # MockRetrievalAgent returns 2 chunks per case, 6 cases total.
    assert agg["total_retrieval_hits"] == 12
    assert agg["avg_latency_ms"] == 0.0

# Each benchmark run record should expose stable run metadata and metrics."
def test_benchmark_run_structure():
    results = run_benchmark(
        mode="mock",
        rag=False,
    )

    runs = results["runs"]

    assert isinstance(runs, list)
    assert len(runs) == 6

    first = runs[0]

    assert "run_id" in first
    assert "case_id" in first
    assert "metrics" in first

    metrics = first["metrics"]

    assert "success" in metrics
    assert "latency_ms" in metrics
    assert "retrieval_hit_count" in metrics
    assert "safety_violation_count" in metrics

# Two mock benchmark runs without RAG should produce identical results.
def test_benchmark_is_deterministic_without_rag():
    results_1 = run_benchmark(
        mode="mock",
        rag=False,
    )
    results_2 = run_benchmark(
        mode="mock",
        rag=False,
    )

    assert results_1 == results_2

# Two mock benchmark runs with RAG should produce identical results.
def test_benchmark_is_deterministic_with_rag():
    results_1 = run_benchmark(
        mode="mock",
        rag=True,
    )
    results_2 = run_benchmark(
        mode="mock",
        rag=True,
    )

    assert results_1 == results_2