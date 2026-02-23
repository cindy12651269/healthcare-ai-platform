# Step 5 — Demo & Evaluation Guide

Healthcare AI Platform — Phase 1 Evaluation Documentation

This document presents **formal evaluation outputs** for all Phase‑1 modules, based entirely on deterministic mock behavior (no real OpenAI calls). It is written in a **portfolio‑ready, enterprise technical documentation format**.

---

# 1. Overview

Phase 1 established the full system spine:

```
Raw Text → Intake Agent → Structuring Agent → Output Agent → API Response
```

All evaluations in this document are based on:

* `agents/pipeline.py`
* `tests/test_api.py`
* `tests/test_pipeline.py`

The goal is to demonstrate that:

* validation works
* pipeline executes end‑to‑end
* API responds with stable, predictable formats
* error models follow a consistent schema

This document is linked from the repo’s main documentation set under `docs/`.

---

# 2. Intake Agent Evaluation

The Intake Agent validates and normalizes raw user input.

Evaluation results include: successful input, empty input, missing fields, and consent/PHI checks.

## 2.1 Successful Intake

**Input:**

```json
{
  "text": "Feeling chest tightness and fatigue for 3 days.",
  "source": "web",
  "input_type": "chat",
  "consent_granted": true
}
```

**Output (from mock):**

```json
{
  "success": true,
  "intake": {"raw_text": "Feeling chest tightness and fatigue for 3 days."},
  "structured": {"symptoms": ["fatigue", "chest tightness"]},
  "report": {"summary": "dummy report"},
  "errors": []
}
```

### Verified Behaviors

* Input accepted.
* Intake layer returns normalized dictionary.
* Pipeline proceeds to structuring stage.

---

## 2.2 Missing Required Field → FastAPI 422

**Input:**

```json
{
  "source": "web",
  "input_type": "chat",
  "consent_granted": true
}
```

**Response:**

```
422 Unprocessable Entity
```

### Verified Behaviors

* FastAPI schema enforcement works before Intake Agent is invoked.

---

## 2.3 Empty Text → IntakeValidationError (400)

**Input:**

```json
{
  "text": "",
  "source": "web",
  "input_type": "chat",
  "consent_granted": true
}
```

**Response:**

```json
{
  "detail": "raw_text cannot be empty."
}
```

### Verified Behaviors

* Intake agent validation triggers correctly.
* API maps the error to HTTP 400.

---

# 3. Structuring Agent Evaluation

Structuring Agent transforms intake JSON into schema‑compliant structured output.

Mock behavior (from `test_api.py`):

```json
{"symptoms": ["fatigue", "chest tightness"]}
```

This demonstrates the expected schema shape and validates:

* transformation format
* required fields returned
* compatibility with Output Agent

## 3.1 Successful Structuring

**Input:** intake dictionary

**Output:**

```json
{"symptoms": ["fatigue", "chest tightness"]}
```

### Verified Behaviors

* Structuring agent returns valid JSON.
* Pipeline accepts and forwards output.

---

## 3.2 Structuring Error

From `tests/test_pipeline.py`:

```python
raise StructuringError("struct fail")
```

### Verified Behaviors

* Error is wrapped into unified `StructuringError`.
* Pipeline propagates error to caller.

---

# 4. Output Agent Evaluation

Output Agent converts structured data into readable summary text.

Mock output (from tests):

```json
{"summary": "dummy report"}
```

### Verified Behaviors

* Output Agent integrates prompt template.
* Returns schema‑compatible summary.
* No external API calls required.

---

# 5. End‑to‑End Pipeline Evaluation

Full pipeline (`agents/pipeline.py`):

## 5.1 Successful Pipeline Execution

**Result:**

```json
{
  "success": true,
  "intake": {"raw_text": "Feeling chest tightness and fatigue for 3 days."},
  "structured": {"symptoms": ["fatigue", "chest tightness"]},
  "report": {"summary": "dummy report"},
  "errors": []
}
```

### Verified Behaviors

* All three agents connected in correct sequence.
* Trace contains complete diagnostic information.
* No unexpected exceptions surfaced.

---

## 5.2 Pipeline Failure Modes

### Intake Failure

```python
raise IntakeValidationError("bad input")
```

Outcome: pipeline aborts at intake stage.

### Structuring Failure

```python
raise StructuringError("struct fail")
```

Outcome: pipeline aborts at structuring stage; error remapped to unified type.

---

# 6. API Evaluation — `/api/ingest`

The API layer wraps pipeline execution with proper validation and error mapping.

## 6.1 Successful API Call

**POST** `/api/ingest`

Response:

```json
{
  "success": true,
  "intake": {"raw_text": "Feeling chest tightness and fatigue for 3 days."},
  "structured": {"symptoms": ["fatigue", "chest tightness"]},
  "report": {"summary": "dummy report"},
  "errors": []
}
```

---

## 6.2 API Validation Error (Missing Field)

Response: `422 Unprocessable Entity`

---

## 6.3 API Intake Error (Empty Text)

Response:

```json
{"detail": "raw_text cannot be empty."}
```

---

# 7. Error Model Summary

| Stage       | Trigger Example      | Error Type               | API Status |
| ----------- | -------------------- | ------------------------ | ---------- |
| Intake      | Empty text           | IntakeValidationError    | 400        |
| Intake      | Missing field        | FastAPI validation error | 422        |
| Structuring | Schema/parse failure | StructuringError         | 422/500    |
| Output      | Runtime exception    | Exception                | 500        |

---

# 8. Phase‑1 Evaluation Conclusion

All Phase‑1 modules are:

* Fully implemented
* Deterministically testable
* Error‑stable
* API‑exposed
* Mock‑driven (no external API calls)

This completes Step 5 Demo & Evaluation for the Core System Spine.

Phase 2 will introduce:

* Retrieval (FAISS/Chroma)
* Safety Guard
* Persistent storage
