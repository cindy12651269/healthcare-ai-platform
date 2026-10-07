# Step 1 — Product Definition 

> **Revision note (2026-10-02):** §3 now defines the single target workflow for the remaining roadmap. Sections 4–9 are the original Phase 1 product definition, annotated where the implementation differs. Current status: [`project_status.md`](project_status.md).

## 1. Product Name

Healthcare AI Platform — Agentic Health LLM Infrastructure

---

## 2. Core Objective

Transform unstructured healthcare inputs into:

* Structured clinical-ready data
* Safe, non-diagnostic summaries
* AI-assisted decision context

---

## 3. Primary Use Case

**Pre-Visit Symptom Intake for an Outpatient Clinic**

**Workflow:**

1. A patient submits a free-text symptom description and grants consent.
2. The system validates the input, detects likely PHI, and structures it against a JSON schema.
3. A non-diagnostic summary is generated for clinic staff; safety rules block diagnosis or prescription language and mask PHI.
4. If emergency language is detected, the patient is shown urgent-care guidance.
5. Emergency signals, blocked outputs and low-confidence results are routed to a review queue for that clinic's staff *(implemented in Phase 5: #29, #30)*.
6. Staff review and resolve flagged intakes; escalations notify an external clinic system *(implemented in Phase 5: #31, #33)*.

**Users:** patient (submitter), clinic staff (reviewer), clinic admin (access management, Phase 4).

**Input:**

* Patient free-text self-reports (implemented)
* Structured intake forms *(not implemented)*
* Voice transcripts *(out of scope — see roadmap §8)*

**Output:**

* Structured health JSON
* Safety-bounded summary report
* Review status and escalation reason *(columns added in Phase 4, #27; set by escalation rules in Phase 5, #29)*

---

## 4. Unified Input Schema (Minimal)

```json
{
  "patient_id": "string",
  "input_type": "text | voice | form",
  "content": "string",
  "timestamp": "ISO-8601"
}
```

---

## 5. Unified Output Schema (Minimal)

```json
{
  "patient_id": "string",
  "symptoms": [],
  "conditions": [],
  "risk_flags": [],
  "summary": "string",
  "confidence_score": 0.0
}
```

---

## 6. Agent Responsibilities

| Agent             | Responsibility                   |
| ----------------- | -------------------------------- |
| Intake Agent      | Input validation & normalization |
| Structuring Agent | Convert to structured schema     |
| Retrieval Agent   | Medical knowledge lookup (RAG)   |
| Reasoning Agent   | Pattern & correlation analysis *(not implemented; out of scope)* |
| Output Agent      | Safe summary & report generation |

---

## 7. Compliance Partition

*Design intent. At the audited commit no zone separation, encryption or deployed storage exists; see `project_status.md`.*

| Zone            | Description             |
| --------------- | ----------------------- |
| Public Zone     | Demo UI, synthetic data |
| Protected Zone  | PHI only                |
| Processing Zone | LLM + Agents            |
| Storage Zone    | Encrypted DB            |
| Audit Zone      | Logs & monitoring       |

---

## 8. Safety Boundaries

* No medical diagnosis
* No treatment recommendations
* Strict hallucination control
* Full PHI auditability

---

## 9. Success Metrics

*Original targets. None has been measured against a real model yet; the current benchmark runs in mock mode and measures contract stability only.*

* Structured output accuracy ≥ 85%
* Hallucination rate < 5%
* Inference latency < 3s
* All PHI flows auditable

Portfolio completion is defined by the Phase 4 exit criteria in [`step3_roadmap.md`](step3_roadmap.md), not by these model-quality targets.

