# Step 5 — Demo & Evaluation Guide (Updated After Phase 2)

Healthcare AI Platform — Phase 1–2 Evaluation Documentation

This document presents formal evaluation outputs for the system after:

• Phase 1 — Core system spine
• Phase 2 — RAG, Safety Guard, and Persistence

All evaluations in this document are based on **deterministic mode** (mock LLM + mock embeddings), ensuring reproducibility and CI stability.

---

# 1. Evaluation Scope

Current deterministic execution flow:

```
Raw Text
   → IntakeAgent
   → StructuringAgent
   → RetrievalAgent (optional)
   → OutputAgent
   → Safety Guard
   → Persistence (optional)
   → API Response
```

Evaluation demonstrates:

• validation behavior
• pipeline sequencing
• RAG trace behavior
• deterministic safety enforcement
• persistence behavior
• API contract stability

---

# 2. Phase 1 — Core Spine Evaluation

## 2.1 Successful Intake → Structuring → Output

Input:

```json
{
  "text": "Feeling chest tightness and fatigue for 3 days.",
  "source": "web",
  "input_type": "chat",
  "consent_granted": true
}
```

Response (deterministic mock):

```json
{
  "success": true,
  "intake": {"raw_text": "Feeling chest tightness and fatigue for 3 days."},
  "structured": {"symptoms": ["fatigue", "chest tightness"]},
  "report": {"summary": "dummy report"},
  "retrieval_trace": null,
  "safety_trace": {"violations": []},
  "errors": []
}
```

Verified:

• Intake validation works
• Structuring schema enforced
• Output schema valid
• Safety guard executed (no violations)

---

## 2.2 Missing Required Field → FastAPI 422

Input missing `text`.

Result:

```
422 Unprocessable Entity
```

Verified:

• FastAPI schema validation blocks request before pipeline execution

---

## 2.3 Empty Text → IntakeValidationError (400)

Input:

```json
{
  "text": "",
  "consent_granted": true
}
```

Response:

```json
{
  "detail": "raw_text cannot be empty."
}
```

Verified:

• Intake agent validation
• Error mapped to HTTP 400

---

# 3. Phase 2 — Retrieval (RAG) Evaluation

RAG operates in deterministic mode using mock embeddings and in-memory vector store.

## 3.1 RAG Enabled Execution

When `enable_rag = True`, pipeline attaches retrieval trace.

Example response:

```json
{
  "retrieval_trace": [
    {
      "doc_id": "doc_001",
      "score": 0.92,
      "snippet": "Chest tightness may relate to cardiac or anxiety causes."
    }
  ]
}
```

Verified:

• RetrievalAgent executed between Structuring and Output
• Ranked documents returned
• Deterministic ordering preserved
• Retrieval failures are non-fatal

---

## 3.2 RAG Disabled Execution

When `enable_rag = False`:

• `retrieval_trace` is null or absent
• Pipeline behavior remains stable

Verified:

• Feature toggle works
• Backward compatibility maintained

---

# 4. Phase 2 — Safety Guard Evaluation

Safety Guard is deterministic and rule-based.

## 4.1 PHI Masking

Input containing email or phone:

"Contact me at [john@example.com](mailto:john@example.com)"

Output summary:

• Email masked or removed

Verified:

• PHI patterns detected
• Masking applied before API response

---

## 4.2 Diagnosis Enforcement

If output attempts diagnosis-like language:

Example trigger:

"You likely have pneumonia."

Result:

• Safety guard flags violation
• Response modified or blocked

Verified:

• No direct diagnosis allowed
• GuardResult attached to `safety_trace`

---

## 4.3 Crisis Detection

If input contains emergency language:

"I cannot breathe and feel like collapsing."

Verified:

• Crisis flag detected
• Trace includes safety indicator

---

# 5. Phase 2 — Persistence Evaluation

When `enable_persistence = True`:

• Structured output stored in `HealthRecord`
• Report stored as JSON
• `input_hash` enforces idempotency

## 5.1 Successful Persistence

Verified via:

• Database record count increment
• Reload of stored record matches structured payload

---

## 5.2 Idempotency Check

Submitting identical input twice:

• Second execution does not duplicate record
• Unique constraint on `input_hash` enforced

Verified:

• Transaction boundary respected
• No duplicate rows

---

# 6. End‑to‑End API Contract Evaluation

## 6.1 Successful Response (Phase 2)

```json
{
  "success": true,
  "intake": {...},
  "structured": {...},
  "report": {...},
  "retrieval_trace": [...],
  "safety_trace": {"violations": []},
  "errors": []
}
```

Verified:

• Response schema stable
• Safety always executed
• Retrieval trace conditional
• Errors consistently structured

---

# 7. Error Model Summary (Extended)

| Stage       | Trigger Example   | Error Type               | HTTP |
| ----------- | ----------------- | ------------------------ | ---- |
| Intake      | Empty text        | IntakeValidationError    | 400  |
| Intake      | Missing field     | FastAPI validation error | 422  |
| Structuring | Schema failure    | StructuringError         | 422  |
| Safety      | Hard violation    | SafetyViolation          | 422  |
| Output      | Runtime exception | Exception                | 500  |

---

# 8. Deterministic Mode Guarantee

Phase 2 evaluation is executed under deterministic mode:

• Mock LLM
• Mock embeddings
• No external APIs
• CI reproducible

This ensures:

• Stable automated testing
• Predictable portfolio demonstration
• Controlled experimentation before real LLM integration

---

# 9. Phase 1–2 Evaluation Conclusion

After Phase 2, the system is:

• RAG-capable (deterministic)
• Safety-enforced (rule-based)
• Persistence-enabled (audit-ready)
• API-exposed
• Feature-toggle controlled
• Fully testable in CI

Phase 3 will introduce:

• Real LLM provider integration
• Evaluation metrics harness
• Observability expansion

---

Document Status: Updated after Phase 2 completion
