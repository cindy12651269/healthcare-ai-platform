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

Phases 1–5 are complete. In Phase 6, security and data-handling notes (#34) and the hosted demo (#35) are complete; portfolio handover (#36) is in review. Synthetic data only; not production software; no HIPAA compliance claim.

**Implemented and tested**

* FastAPI service with `POST /api/ingest`, working end to end without an LLM key (deterministic mock mode by default)
* Next.js patient intake UI with a developer trace panel, and a staff review workspace at `/staff` ([`staff_review_ui.md`](staff_review_ui.md))
* Intake validation, PHI keyword detection and consent gate
* Schema-validated structuring and reports; opt-in real OpenAI provider (`LLM_MODE=real`) with strict JSON-schema output and no fallback to mock
* Deterministic safety guard: diagnosis/prescription blocking, PHI masking, emergency guidance
* PostgreSQL persistence with ordered SQL migrations: clinics, users, clinic memberships (`clinic_staff` / `clinic_admin`), and clinic-owned intake records with review-status fields ([`data_model.md`](data_model.md))
* Staff bearer-token authentication, server-side role checks and clinic isolation, plus minimal clinic-admin membership management ([`auth.md`](auth.md))
* Deterministic escalation rules (emergency, blocked output, low confidence → `needs_review`) and a clinic-scoped, audited review-queue API ([`data_model.md`](data_model.md), [`review_queue_api.md`](review_queue_api.md))
* Signed escalation webhook (HMAC-SHA256, idempotency key, bounded retries, delivery log; PHI-minimal payload) ([`escalation_webhook.md`](escalation_webhook.md))
* Labelled safety & escalation evaluation set in CI. Its 1.00 match rates mean agreement with the labelled current baseline, not safety accuracy; known gaps are recorded ([`evaluation_benchmark.md`](evaluation_benchmark.md))
* Retrieval agent and vector store abstraction (mock embeddings; not wired into the API)
* Deterministic benchmark harness, per-run audit events, stage-level latency metrics
* GitHub Actions CI: backend and PostgreSQL integration tests, mock benchmark (RAG off/on), frontend lint/typecheck/tests/build
* Security and data-handling notes: data flow, what is masked vs stored (raw intake text is stored unmasked), threat model, HIPAA gap list without a compliance claim; a regression test that pipeline, request and staff-action audit events contain no raw intake text ([`security_data_handling.md`](security_data_handling.md))
* One hosted demo on Render free plans (API, frontend, PostgreSQL) with migrations, synthetic demo seed and health checks on deploy; the flagged-intake → clinic queue → signed webhook flow verified on 2026-10-09 ([`deployment.md`](deployment.md), [`demo_walkthrough.md`](demo_walkthrough.md))

**Planned**

* Phase 6: portfolio handover documentation (#36, in review)
* Phase 7: deterministic extraction baseline, intake evidence timeline, FHIR R4 export of reviewed intakes, guided demo

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
| `agents/` | Intake, structuring, retrieval, output agents; escalation rules; pipeline orchestrator | Implemented |
| `api/` | FastAPI app, routers, middleware, escalation webhook | `ingest`, staff auth / clinic membership endpoints ([`auth.md`](auth.md)), review-queue endpoints ([`review_queue_api.md`](review_queue_api.md)), webhook delivery ([`escalation_webhook.md`](escalation_webhook.md)) and audit middleware implemented; no rate limiting |
| `llm/` | Prompts, JSON schemas, safety guard | Implemented |
| `rag/` | Embeddings, vector store, retriever, document loader | Implemented with mock embeddings |
| `db/` | ORM models (clinics, users, memberships, health records), session, ordered SQL migrations | Implemented ([`data_model.md`](data_model.md)) |
| `observability/` | Audit logger, tracing context, metrics | Implemented (local) |
| `evaluation/` | Benchmark runner, metrics, test cases, labelled safety & escalation set | Implemented (mock mode in CI; real mode opt-in) |
| `tests/` | Unit, contract, auth/RBAC and PostgreSQL integration tests | Run in CI on every PR and push to `main` |
| `app/` | Next.js patient intake UI and staff review UI (`/staff`) | Implemented |
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
| [`data_model.md`](data_model.md), [`auth.md`](auth.md) | Data model v2 and migrations; escalation rules; staff authentication, roles and clinic isolation |
| [`review_queue_api.md`](review_queue_api.md), [`staff_review_ui.md`](staff_review_ui.md), [`escalation_webhook.md`](escalation_webhook.md) | Review-queue API, staff review UI, escalation webhook (Phase 5) |
| [`project_status.md`](project_status.md) | Evidence-based capability audit |
| [`project_journal/`](project_journal/) | Historical records of completed phases |

Implementation progress is tracked in GitHub Issues and Projects.
