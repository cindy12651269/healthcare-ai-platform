# Healthcare AI Platform — Overview

## 1. What This Project Is

A portfolio project demonstrating production-style engineering of a patient-facing healthcare AI workflow:

> **AI-assisted pre-visit symptom intake for an outpatient clinic.**
> Patients describe symptoms in free text. The system validates and structures the input, produces a non-diagnostic summary for clinic staff, applies deterministic safety rules, and routes risky or uncertain submissions to a human reviewer.

The emphasis is on engineering practice — explicit contracts, deterministic testing, safety boundaries, observability, and an issue-driven delivery workflow — rather than on the number of AI components.

All data is synthetic. This project does not provide medical diagnosis or treatment advice and makes no HIPAA compliance claim.

---

## 2. Current State (Summary)

Full evidence: [`project_status.md`](project_status.md).

**Implemented and tested**

* FastAPI service with `POST /api/ingest`
* Intake validation, PHI keyword detection and consent gate
* Schema-validated structuring (deterministic mock mode)
* Deterministic safety guard: diagnosis/prescription blocking, PHI masking, emergency guidance
* PostgreSQL `HealthRecord` model with idempotency
* Retrieval agent and vector store abstraction (mock embeddings)
* Deterministic benchmark harness, per-run audit events, stage-level latency metrics

**In progress (Phase 3)**

* Making the default API path run end-to-end without an LLM key
* CI pipeline
* Real LLM provider behind a configuration flag
* Patient intake UI

**Planned (Phase 4)**

* Authentication, roles and clinic-level data isolation
* Human review queue and escalation rules
* Signed escalation webhook to an external system
* Deployed demo environment and handover documentation

---

## 3. Design Principles

* **Deterministic by default.** Mock LLM and mock embeddings keep CI reproducible; real providers are opt-in.
* **Safety outside the model.** Rule-based guards run on every output regardless of provider.
* **Humans own clinical decisions.** The system summarises and routes; it does not diagnose.
* **Traceable runs.** Each run carries an ID, stage timings, retrieval trace and safety reasons.
* **Honest documentation.** Docs distinguish implemented, partial and planned work.

---

## 4. Repository Layout

| Path | Contents | State |
| --- | --- | --- |
| `agents/` | Intake, structuring, retrieval, output agents; pipeline orchestrator | Implemented (`reasoning_agent.py` empty) |
| `api/` | FastAPI app, routers, middleware | `ingest` + audit middleware implemented; auth, rate limit and other routers empty |
| `llm/` | Prompts, JSON schemas, safety guard | Implemented |
| `rag/` | Embeddings, vector store, retriever, document loader | Implemented with mock embeddings |
| `db/` | ORM model, session, SQL migration | Implemented |
| `observability/` | Audit logger, tracing context, metrics | Implemented (local) |
| `evaluation/` | Benchmark runner, metrics, test cases | Implemented (mock mode) |
| `tests/` | Unit and contract tests | 39 passing at last audit |
| `app/` | Frontend | Empty placeholders — Phase 3 |
| `interoperability/`, `infra/aws/`, `compliance/` | Early scaffold | Empty placeholders — see roadmap |
| `docs/` | Product, architecture, API, evaluation, roadmap, journals | — |

---

## 5. Documentation Map

| Document | Purpose |
| --- | --- |
| [`step1_product.md`](step1_product.md) | Product definition and target workflow |
| [`step2_architecture.md`](step2_architecture.md) | Architecture as of Phase 2 |
| [`step3_roadmap.md`](step3_roadmap.md) | Roadmap, remaining scope and rationale |
| [`step4_repo_api.md`](step4_repo_api.md) | Repository and API reference as of Phase 2 |
| [`step5_demo_eval.md`](step5_demo_eval.md) | Phase 1–2 behaviour walkthrough |
| [`evaluation_design.md`](evaluation_design.md), [`evaluation_benchmark.md`](evaluation_benchmark.md) | Evaluation harness design and usage |
| [`project_status.md`](project_status.md) | Evidence-based capability audit |
| [`project_journal/`](project_journal/) | Historical records of completed phases |

Implementation progress is tracked in GitHub Issues and Projects.
