# Evaluation Design — Pre-Issue 13 Foundation

## Overview

This document describes the architectural changes introduced before Issue 13 to enable deterministic evaluation, structured scoring, and CI-safe benchmarking.

These updates ensure that the Healthcare AI pipeline produces consistent, schema-aligned outputs suitable for automated evaluation.

---

## Key Goals

* Enable deterministic benchmarking (CI-safe)
* Standardize structured output schema
* Prepare for field-level scoring (Issue 13)
* Ensure reproducibility across runs

---

## 1. Structured Output Alignment

### Before

Flat structure:

```json
{
  "chief_complaint": "...",
  "symptoms": [...],
  "duration": "...",
  "severity": "..."
}
```

### After

Schema-aligned structure:

```json
{
  "trace": {...},
  "compliance": {...},
  "clinical_structuring": {...},
  "agent_decisioning": {...},
  "ehr_interoperability": {...},
  "output_metadata": {...}
}
```

### Impact

* Enables schema validation
* Supports field-level metrics
* Aligns with system architecture

---

## 2. StructuringAgent Update

### File

```
agents/structuring_agent.py
```

### Changes

* Output updated to structured schema
* JSON schema validation enforced
* Deterministic mock output retained

### Result

* CI-safe
* Schema-consistent output

---

## 3. Benchmark Determinism

### File

```
evaluation/benchmark.py
```

### Deterministic Guarantees

* Fixed seed per case (`42 + index`)
* Stable run_id (`case_id:mode:rag|norag`)
* Ordered execution (no randomness in iteration)
* Latency fixed to 0 in mock mode
* JSON output sorted (`sort_keys=True`)

### Pipeline Mode

* Default: mock
* No persistence
* No external API calls

---

## 4. Mock Agents (CI-safe)

### Purpose

Ensure no external dependencies during evaluation.

### Components

* MockStructuringAgent
* MockOutputAgent
* MockRetrievalAgent

### Behavior

* Fully deterministic
* Fixed outputs
* Stable retrieval hit counts

---

## 5. Metrics Compatibility

### Current (Issue 12)

Per-run:

* success
* safety_violation_count
* retrieval_hit_count
* latency_ms

Aggregated:

* total_runs
* success_rate
* avg_latency_ms
* total_safety_violations
* total_retrieval_hits

### Prepared for Issue 13

Structured metrics will use:

* clinical_structuring
* compliance
* schema validity

---

## 6. Test Updates

### File

```
tests/test_agents.py
```

### Changes

* Updated to use structured schema
* Assertions moved from root → nested fields

Before:

```python
result["chief_complaint"]
```

After:

```python
result["clinical_structuring"]["chief_complaint"]
```

---

## 7. Why This Matters

These changes enable:

* Deterministic CI benchmarks
* Field-level evaluation scoring
* Reliable regression testing
* RAG on/off comparison
* Portfolio-ready evaluation system

---

## 8. Next Step

Proceed to: **Issue 13 — Structured Accuracy Scoring**

Add:

* required field presence rate
* schema validity rate
* coverage metrics
* symptom consistency checks

---

## Summary

This phase establishes the evaluation foundation:

* Structured schema 
* Deterministic benchmark 
* CI-safe execution 
* Metrics-ready pipeline 

System is now ready for structured scoring implementation.
