# Evaluation Harness — Deterministic Benchmark

## Purpose

This document explains how the Healthcare AI pipeline evaluation harness works
and how to reproduce benchmark results.

The evaluation harness provides deterministic benchmarking for the
HealthcarePipeline and is designed to be CI-safe and reproducible.

---

# Benchmark Overview

The benchmark system executes predefined test cases against the
HealthcarePipeline and computes evaluation metrics.

Key goals:

* Deterministic execution
* CI reproducibility
* Metrics reporting
* RAG on/off comparison

---

# Benchmark Components

The evaluation system consists of the following files:

| File                         | Purpose                       |
| ---------------------------- | ----------------------------- |
| `evaluation/test_cases.json` | Deterministic input cases     |
| `evaluation/metrics.py`      | Metric computation logic      |
| `evaluation/benchmark.py`    | Benchmark runner CLI          |
| `tests/test_benchmark.py`    | Deterministic benchmark tests |

---

# Benchmark Execution

The benchmark runner executes all cases sequentially.

Execution steps:

1. Load test cases from `evaluation/test_cases.json`
2. For each case

   * Generate deterministic run_id
   * Set deterministic seed
   * Execute HealthcarePipeline
3. Compute per-run metrics
4. Compute aggregated metrics
5. Print summary
6. Save JSON results

---

# CLI Usage

Benchmark CLI entry point:

```
python -m evaluation.benchmark
```

## Run benchmark without RAG

```
python -m evaluation.benchmark --mode mock --rag off
```

## Run benchmark with RAG

```
python -m evaluation.benchmark --mode mock --rag on
```

## Custom output file

```
python -m evaluation.benchmark --mode mock --rag off --out results.json
```

Results will be written to:

```
evaluation/results/
```

---

# Deterministic Guarantees

The benchmark harness enforces deterministic behavior.

| Mechanism             | Implementation                  |
| --------------------- | ------------------------------- |
| Stable case order     | `test_cases.json` order         |
| Stable run_id         | `case_id:mode:rag`              |
| Fixed seed            | `42 + case_index`               |
| Deterministic latency | `latency_ms = 0.0` in mock mode |
| Sorted JSON output    | `json.dump(sort_keys=True)`     |

These guarantees ensure that benchmark outputs are reproducible across runs.

---

# Metrics

Metrics are computed in `evaluation/metrics.py`.

## Per-run metrics

| Metric                   | Description                |
| ------------------------ | -------------------------- |
| `success`                | Pipeline execution success |
| `latency_ms`             | Execution latency          |
| `safety_violation_count` | Safety guard actions       |
| `retrieval_hit_count`    | Retrieved knowledge chunks |

---

## Aggregated metrics

| Metric                    | Description              |
| ------------------------- | ------------------------ |
| `total_runs`              | Number of executed cases |
| `success_rate`            | Success ratio            |
| `avg_latency_ms`          | Average latency          |
| `total_safety_violations` | Sum of safety violations |
| `total_retrieval_hits`    | Total retrieved chunks   |

---

# Example Output

Console output example:

```
Benchmark Summary
----------------------------
Total runs: 6
Success rate: 1.00
Avg latency (ms): 0.00
Safety violations: 0
Retrieval hits: 12
----------------------------
```

Example JSON result:

```
{
  "runs": [...],
  "aggregated": {
    "total_runs": 6,
    "success_rate": 1.0,
    "avg_latency_ms": 0.0,
    "total_safety_violations": 0,
    "total_retrieval_hits": 12
  }
}
```

---

# Running Tests

Run deterministic benchmark tests:

```
pytest tests/test_benchmark.py
```

Run full test suite:

```
pytest
```

---

# CI Usage

The benchmark harness is designed to run safely in CI:

* Mock agents only
* No external API calls
* No database writes
* Deterministic outputs

This ensures consistent CI evaluation results.

---

# Future Extensions

Future improvements may include:

* Live model benchmarking
* RAG quality metrics
* hallucination detection
* retrieval precision metrics
* evaluation dataset expansion

These features will be implemented in future phases.
