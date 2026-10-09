# Step 2 — System Architecture (Updated After Phase 2)

Healthcare AI Platform — System Architecture Specification
Target: Healthcare LLM + Agent Platform with Deterministic RAG, Safety Enforcement, and Audit-Ready Persistence

This document reflects the **current implemented architecture after Phase 2**.
It serves as the authoritative architectural reference for implementation and portfolio review.

> **Status (2026-10-09, handover #36).** This is the **Phase 2 design document**, kept as a historical record; the body is not updated. The implemented architecture is in [`diagrams/architecture.md`](diagrams/architecture.md) and the README. Differences between this body and the code:
>
> * The API's pipeline (`api/deps.py`) is built without a `RetrievalAgent`, so RAG is not active through `/api/ingest` (`rag.enabled: false`); retrieval runs in tests and in the benchmark with `--rag on`. Mock embeddings are hash-derived and carry no semantic meaning.
> * Both agents have a deterministic mock mode (default) and an opt-in OpenAI real mode (`LLM_MODE`, PR #21, #22).
> * Added after Phase 2 and not described in the body: data model v2 with migrations ([`data_model.md`](data_model.md)), staff authentication and clinic isolation ([`auth.md`](auth.md)), escalation rules and the review-queue API ([`review_queue_api.md`](review_queue_api.md)), the staff UI, the signed webhook ([`escalation_webhook.md`](escalation_webhook.md)), security notes ([`security_data_handling.md`](security_data_handling.md)) and the hosted deployment ([`deployment.md`](deployment.md)).
> * The "Interoperability Layer" and cloud infrastructure placeholders were removed in #26. FHIR R4 export is #42 (Phase 7); HL7 and multi-service cloud infrastructure are out of scope.

---

# 1. High-Level Architecture Overview

The platform is a **backend-centric AI system** with a thin demo UI and modular agent pipeline.

## Core Layers

* **Frontend (`app/`)**
  Lightweight React/Next.js demo UI for submitting health-related input and viewing structured reports.

* **Backend API (`api/`)**
  FastAPI service exposing REST endpoints (currently `/api/ingest`) and wiring requests into the agent pipeline.

* **Agent Orchestration (`agents/`)**
  Deterministic, modular mini-agents composed into a structured healthcare workflow.

* **LLM Layer (`llm/`)**
  Pluggable provider interface (mock in deterministic mode, real provider in Phase 3+), with schema validation and safety enforcement.

* **RAG Layer (`rag/`)**
  Deterministic embedding interface + pluggable vector store abstraction for retrieval-augmented reasoning.

* **Persistence Layer (`db/`)**
  PostgreSQL ORM models and transaction-safe storage with idempotency support.

* **Interoperability Layer (not implemented)**
  Planned FHIR / HL7 integration. The empty `interoperability/` scaffold was removed in #26; FHIR export is an optional enhancement and HL7 / EHR routing is out of scope ([`step3_roadmap.md`](step3_roadmap.md) §7–§8).

* **Observability (`observability/`)**
  Structured tracing hooks, audit logging placeholders, and metrics interfaces.

---

# 2. Deterministic Design Philosophy (Phase 2 Foundation)

Phase 2 introduced a strict deterministic-first engineering model:

* Mock embeddings for reproducible ranking
* In-memory vector store for CI-safe retrieval
* Rule-based safety enforcement (non-LLM)
* Schema-validated LLM outputs
* Optional feature toggles (RAG / persistence)
* Explicit retrieval and safety traces

This ensures:

* CI reliability
* Reproducible evaluation
* Controlled failure modes
* Audit-ready system behavior

External providers (LLM, FAISS, Chroma) are abstracted behind interfaces but not required for deterministic mode.

---

# 3. Agent Orchestration Layer (`agents/`)

Each agent has a single responsibility and is independently testable.

## 3.1 IntakeAgent

* Validates raw text
* Normalizes metadata
* Enforces consent flag
* Emits structured `HealthInput`

---

## 3.2 StructuringAgent

* Calls pluggable LLM interface
* Uses schema validation (`structured_output.json`)
* Raises structured errors on invalid output
* Operates in deterministic mock mode (Phase 1/2)

---

## 3.3 RetrievalAgent (Phase 2 Implemented)

* Builds semantic query from structured data
* Uses deterministic embeddings
* Queries vector store abstraction
* Returns ranked context chunks
* Non-fatal on retrieval failure
* Supports feature flag `enable_rag`

Retrieval trace is attached to pipeline output.

---

## 3.4 OutputAgent

* Generates human-readable summary
* Applies structured report schema
* Invokes Safety Guard before finalizing output
* Returns typed report object

---

## 3.5 HealthcarePipeline

### Current Phase 2 Flow

```text
Raw Input
   → IntakeAgent
   → StructuringAgent
   → RetrievalAgent (optional)
   → OutputAgent
   → Safety Guard
   → Persistence (optional)
```

### Pipeline Output Structure

* `success: bool`
* `intake`
* `structured`
* `report`
* `retrieval_trace` (optional)
* `safety_trace`
* `errors`

Pipeline execution is configurable via runtime flags.

---

# 4. LLM Layer (`llm/`)

## 4.1 Prompts

* `structuring.txt`
* `report.txt`

Prompts are designed to:

* Enforce JSON-only outputs where required
* Avoid diagnosis/prescription
* Maintain healthcare compliance posture

---

## 4.2 Schemas

* `health_input.json`
* `structured_output.json`
* `report_output.json`

All LLM outputs are schema-validated before downstream usage.

---

## 4.3 Safety Guard (Phase 2 Implemented)

Implemented deterministic safety layer with:

* PHI masking (names, emails, phone numbers, IDs, dates)
* No-diagnosis enforcement
* No-prescription enforcement
* Crisis / emergency language detection
* Typed `GuardResult`
* Unit-tested deterministic behavior

Safety enforcement occurs before final output return.

---

# 5. RAG Layer (`rag/`)

## 5.1 Embeddings

* Deterministic mock embeddings for CI
* Pluggable provider interface for real embeddings (Phase 3+)

---

## 5.2 Vector Store

* In-memory deterministic store (Phase 2)
* Abstract interface compatible with FAISS / Chroma
* Supports insert, search, clear, update
* Designed for scalable backend replacement

---

## 5.3 Retriever

High-level interface used by `RetrievalAgent`.

Retrieval failures are non-fatal (best-effort grounding policy).

---

# 6. Persistence Layer (`db/`)

## 6.1 HealthRecord (Implemented in Phase 2)

* Stores structured output
* Stores generated report
* JSON payload storage
* Version field support
* Unique `input_hash` for idempotency
* Transaction boundary via `save_record()` helper

* Clinic ownership (`clinic_id`), `review_status` and `escalation_reason` (data model v2, #27)

Data model v2 also adds `clinics`, `users` and `clinic_memberships` (roles `clinic_staff`, `clinic_admin`). See [`data_model.md`](data_model.md).

## 6.2 Migration

Ordered SQL files applied by `db/migrate.py` (recorded in `schema_migrations`; run on every Compose start):

* `001_init_health_records.sql`
* `002_clinics_users_review_status.sql`
* `003_webhook_deliveries.sql` (escalation webhook delivery log, #33)

## 6.3 Encryption Model

Encryption at rest is assumed via infrastructure-level database encryption (e.g., managed PostgreSQL with disk encryption enabled).

Application-level field encryption is an optional enhancement (roadmap §7); it is not scheduled.

---

# 7. Runtime Modes

## Deterministic Mode (Phase 1–2)

* Mock LLM
* Mock embeddings
* CI-safe
* No external dependencies

## Real LLM Mode (Phase 3+)

* Real provider integration
* Same interface contract
* Enables live evaluation and demo usage

---

# 8. Observability (Phase 3 Expansion Planned)

Current:

* Pipeline trace hooks
* Retrieval trace
* Safety trace

Planned Phase 3:

* Audit logger
* Metrics (latency, safety rate, retrieval accuracy)
* Structured logging

---

# 9. Interoperability Layer (Original Target — Not Implemented)

> FHIR R4 export of reviewed intakes is planned as #42 (Phase 7). The HL7 parser and EHR router are out of scope (roadmap §8). The list below is the original Phase 2 design intent.

* FHIR client abstraction
* HL7 parser
* Consent management
* EHR router

Designed to support healthcare SaaS integrations without changing core pipeline.

---

# 10. Deployment & Infrastructure

Local:

* Docker compose
* PostgreSQL container
* Makefile commands

Cloud (planned / scaffolded):

* AWS RDS
* S3
* IAM policies
* IaC structure

---

# 11. Architectural Status After Phase 2

The system is now:

* RAG-capable (deterministic)
* Safety-enforced (hard rules)
* Persistence-enabled (audit-ready schema)
* Modular and test-driven
* CI reproducible

This positions the platform for Phase 3 evaluation, real LLM integration, and demo UI activation.

---

# 12. Architectural Intent

The architecture intentionally separates:

* Deterministic core logic
* Pluggable intelligence providers
* Hard safety enforcement
* Persistence and audit
* Future interoperability layer

This ensures the repository functions both as:

* A working healthcare AI backend
* A reusable architectural blueprint for SaaS-grade healthcare AI systems

---

**Document Status:** Updated after Phase 2 completion
Future revisions will reflect Phase 3 and Phase 4 expansion.
