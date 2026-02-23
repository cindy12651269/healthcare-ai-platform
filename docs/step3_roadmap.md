# Step 3 — Development Roadmap (Sprint Plan)

This roadmap is designed for a fast MVP build targeting healthcare AI projects** with clear Phasely deliverables.

---

## Phase 1 — Core Foundation (System Spine)

**Goal:** Make the system runnable end-to-end with dummy data.

### Deliverables

* Project bootstrap (Docker, env, Makefile)
* FastAPI backend running
* Agent pipeline wired (Intake → Structuring → Output)
* Basic LLM call working (single prompt)
* Unified input/output schema connected

### Tasks

* Create `.env` and config loader
* Implement `intake_agent.py`
* Implement `structuring_agent.py`
* Implement `output_agent.py`
* Add basic `/ingest` API endpoint

### Acceptance Criteria

* API accepts raw input
* Returns structured JSON output
* Single-click local startup

---

## Phase 2 — RAG + Safety + Persistence

**Goal:** Introduce memory, knowledge grounding, and safety controls.

### Deliverables

* Vector database integration (FAISS / Chroma)
* Medical retrieval agent active
* Safety guard active
* Encrypted database persistence

### Tasks

* Implement `retrieval_agent.py`
* Connect `rag/vector_store.py`
* Implement `llm/safety_guard.py`
* Save structured outputs to PostgreSQL

### Acceptance Criteria

* Retrieval improves structured output
* Safety filter blocks risky responses
* Data saved and reloadable from DB

---

## Phase 3 — UI + Evaluation + Observability

**Goal:** Make the system demo-ready and measurable.

### Deliverables

* Basic frontend demo UI
* Automated evaluation harness
* Audit logging & metrics enabled

### Tasks

* Build `app/pages/index.tsx`
* Implement `evaluation/benchmark.py`
* Add observability audit logger
* Track latency & structured accuracy

### Acceptance Criteria

* User can submit data via browser
* See structured report in UI
* Metrics printed per run

---

## Phase 4 — Interoperability + Portfolio Hardening

### Deliverables

* FHIR mock integration
* Consent flow active
* Architecture diagrams & documentation complete
* Final demo video + README polish

### Tasks

* Implement `interoperability/fhir_client.py`
* Implement `interoperability/consent.py`
* Finalize docs & diagrams
* Record demo walkthrough

### Acceptance Criteria

* FHIR read/write simulation works
* Consent enforcement verified
* Repo is fully portfolio-ready

---

## Final Output After 4 Phases

* ✅ Full Health LLM + Mini Agent System
* ✅ RAG + Safety + Observability
* ✅ FHIR-ready Integration Layer
* ✅ Demo UI + Benchmarks

---

## Risk Control

* Keep medical logic non-diagnostic
* All PHI flows isolated
* Prompt changes version-controlled
* Evaluation mandatory for all changes
