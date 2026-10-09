# Step 3 — Development Roadmap

**Last revised:** 2026-10-06 (Phase 4 closure: phase overview synchronized with the GitHub Projects for Phases 4–7)
**Previous revision:** 2026-10-02 (roadmap realignment after the Phase 2 / Issue 15 checkpoint)

GitHub Issues and Projects are the source of truth for implementation progress. This document explains **what the remaining work is and why it exists**. It does not duplicate issue checklists.

* Current capability status with evidence: [`project_status.md`](project_status.md)
* Completed-phase records: [`project_journal/`](project_journal/)

---

## 1. Product Focus

The original plan described a broad "agentic health LLM infrastructure" with EHR interoperability. The 2026-10 revision narrows the remaining scope to **one complete, bounded workflow**:

> **AI-assisted pre-visit symptom intake for an outpatient clinic.**
> A patient submits a free-text description of symptoms before a visit. The system validates and structures it, produces a non-diagnostic summary for clinic staff, applies safety rules, and routes anything risky or uncertain to a human reviewer at that clinic.

| Actor | What they do |
| --- | --- |
| Patient | Submits symptoms with consent; receives an acknowledgement, plus urgent-care guidance when emergency language is detected. Never receives a diagnosis or treatment advice. |
| Clinic staff | Sees only their own clinic's intakes; works a review queue of flagged submissions; marks them reviewed or escalated. |
| Clinic admin | Manages staff access for the clinic (minimal). |
| External clinic system | Receives a signed notification when an intake is escalated. |

This uses the components built in Phases 1–2 (intake, structuring, safety guard, persistence, observability) rather than replacing them.

### Why narrow the scope

In a September 2026 review of a small sample of healthcare software engagement requirements, most emphasised whole-workflow delivery, backend APIs and integrations, data model and access boundaries, security appropriate to health data, testing and deployment, and — for patient-facing AI — explicit escalation to humans. Named AI techniques (RAG, LLM evaluation frameworks, FHIR, AI scribe) were requested far less often. The roadmap therefore prioritises a working, secured, deployed workflow over additional AI components. This review was a small sample and is used only as a prioritisation input.

---

## 2. Phase Overview

| Phase | Theme | Status |
| --- | --- | --- |
| 1 | Core Foundation (System Spine) | **COMPLETE** — Issues #1–#6 |
| 2 | RAG + Safety + Persistence | **COMPLETE** — Issues #7–#11 |
| 3 | UI + Evaluation + Observability | **COMPLETE** — Issues #12–#17 |
| 4 | Foundation & Provider Integration | **COMPLETE** — Issues #22, #25–#28 |
| 5 | Clinical Review & Escalation Workflow | **COMPLETE** — Issues #29–#33 |
| 6 | Security, Deployment & Handover | **IN REVIEW** — #34, #35 complete; #36 handover PR open |
| 6 | Security, Deployment & Handover | **NEXT** — Issues #34–#36 |
| 7 | Demo Experience, AI Evidence & FHIR Interoperability | **PLANNED** — Issues #40–#43 |
| — | Optional enhancements | Not required for portfolio completion |

Each phase is tracked as a GitHub Project of the same name, and GitHub Issues remain authoritative wherever this document and an issue differ. The work items in §5–§6 were written on 2026-10-02, before the issues existed; they are now delivered by Phases 3–6 as mapped below.

The original Phase 4 ("Interoperability + Portfolio Hardening": FHIR mock, consent flow, diagrams, demo video) has been replaced. Documentation and demo work are in Phases 6–7; FHIR R4 export is #42 (Phase 7).

---

## 3. Phase 1 — Core Foundation (COMPLETE)

Runnable FastAPI service, Docker Compose stack, and the Intake → Structuring → Output pipeline with deterministic mocks.
Record: [`project_journal/phase1_core_foundation.md.md`](project_journal/phase1_core_foundation.md.md)

## 4. Phase 2 — RAG + Safety + Persistence (COMPLETE)

Retrieval agent and vector store abstraction, deterministic safety guard, PostgreSQL `HealthRecord` persistence, RAG-aware pipeline execution.
Record: [`project_journal/phase2_rag_safety_persistence.md`](project_journal/phase2_rag_safety_persistence.md)

Known limitations carried forward (see `project_status.md`): mock embeddings carry no semantic signal; RAG is not wired into the API; field-level encryption was deferred.

---

## 5. Phase 3 — Working Demo Baseline (COMPLETE)

> **Outcome (2026-10-06).** Phase 3 closed with #12–#17 (record: [`project_journal/phase3_UI_Evaluation_Observability.md`](project_journal/phase3_UI_Evaluation_Observability.md)). The deterministic end-to-end path landed in #20 / PR #21, during Phase 3. CI (#25), repository hygiene (#26) and the real LLM provider (#22) landed in Phase 4 (record: [`project_journal/phase4_Foundation_&_Provider_Integration.md`](project_journal/phase4_Foundation_&_Provider_Integration.md)). The text below is the 2026-10-02 plan, kept for context.

**Goal:** a reviewer can clone the repository, run one command, submit an intake through a browser, and get a safe result — with CI proving it on every change.

### Completed in Phase 3

* #12 Evaluation harness v1 (deterministic benchmarks)
* #13 Structured accuracy scoring v1 (field-level proxy metrics)
* #14 Audit logger (per-run events)
* #15 Stage-level latency instrumentation

### Remaining in Phase 3

Only #16 and #17 exist as issues today. The other items below are proposed and will be created as separate issues. The changes described for #16 and #17 are **proposed re-scopes**: neither issue has been edited yet, and both still contain their original scope.

| Work item | Why it exists |
| --- | --- |
| Deterministic end-to-end path through the real API | The default `/api/ingest` path currently fails without an OpenAI key, and agent output contracts do not match the pipeline and persistence model. Nothing downstream is credible until the unmocked path works and is tested. |
| CI pipeline and complete dependency manifest | Demonstrates that tests and the benchmark run on every change; starts the Issue → branch → PR → review → merge workflow with an automated gate. |
| Repository hygiene | Empty placeholder files and a tracked runtime log make the repository look larger than it is. Remove or explicitly mark them. |
| Real LLM provider behind a configuration flag (#17; proposed narrowing) | Shows a production-style third-party integration: timeouts, retries, schema validation, safe failure. Mock mode stays the default for CI. #17 as written also includes nested field scoring and UI mode display; the proposal moves nested scoring to optional enhancements. |
| Patient intake UI (#16; proposed re-scope) | Makes the workflow demonstrable in a browser. #16 as written is a trace + metrics viewer with browser-side feature-flag toggles; the proposal makes intake submission the primary purpose, keeps the trace as a collapsible developer panel, and leaves feature flags as server configuration. |

**Phase 3 exit criteria**

* `make up` → browser intake → response, with no API key required.
* CI green on `main`; at least one unmocked API → pipeline → database integration test.
* Real-LLM mode documented and opt-in.

---

## 6. Clinic Workflow, Access Control & Delivery (Phases 4–6)

> **Status (2026-10-07).** This section was written as a single "Phase 4". It is now delivered across three phases. Data model v2 (#27) and authentication, RBAC and clinic isolation (#28) are **complete** in Phase 4. The clinic workflow items (#29–#33) are **complete** in Phase 5 (2026-10-07, [journal](project_journal/phase5_Clinical_Review_&_Escalation_Workflow.md)). In Phase 6, security notes (#34) and the hosted demo deployment (#35, [`deployment.md`](deployment.md)) are **complete** (2026-10-09); portfolio handover (#36) is in review. The issue for each row is shown in brackets.

**Goal:** turn the demo into a believable small product: identified users, clinic-scoped data, a human review step, one external integration, a deployed environment, and handover-quality documentation.

| Work item | Why it exists |
| --- | --- |
| Data model v2 with migrations [#27, Phase 4 — complete] | Clinics, users/roles and intake review status are prerequisites for access control and escalation. Introduces a migration tool in place of a single raw SQL file. |
| Authentication, RBAC and clinic isolation [#28, Phase 4 — complete] | Healthcare clients expect role and tenant boundaries. Enforced server-side and tested, including cross-clinic denial. |
| Records and review-queue API [#30, Phase 5 — complete] | There is currently no way to read stored data back. Staff need list/get/transition endpoints; every staff action is audited with actor identity. |
| Escalation rules [#29, Phase 5 — complete] | Emergency signals, blocked outputs and low-confidence structuring move an intake to `needs_review` with a recorded reason. This is the human-in-the-loop boundary for patient-facing AI. |
| Safety and escalation evaluation set [#32, Phase 5 — complete] | A small labelled set (diagnosis-seeking, prescription requests, emergency language, PHI) that measures guard and escalation behaviour, so safety claims are backed by numbers. |
| Staff review UI [#31, Phase 5 — complete] | Makes the human review step visible in the demo. |
| Escalation notification webhook [#33, Phase 5 — complete] | One concrete outbound integration: HMAC-signed payload, retries, idempotency key, delivery log. No PHI in the payload beyond an intake reference. |
| Security and data-handling notes [#34, Phase 6 — complete] | Replaces empty compliance stubs with one accurate document: data flow, what is masked or stored, threat model summary, and what would be required for HIPAA compliance. No compliance claim is made. Includes a test that audit logs contain no raw intake text. |
| Deployment [#35, Phase 6 — complete] | One hosted demo environment with synthetic data only, migrations on deploy, health checks and environment-managed secrets. |
| Portfolio handover [#36, Phase 6 — in review] | README, architecture diagram, decision records, demo walkthrough, scope and personal-contribution statement; Phase 3 and Phase 4 journals. |

**Exit criteria (portfolio complete, end of Phase 6)**

* A deployed demo where a patient submission flagged by safety rules appears in the correct clinic's review queue and triggers a signed webhook.
* Authorization and isolation covered by tests; CI green.
* README and docs accurately describe what is and is not implemented.

---

## 7. Optional Enhancements (Not Required for Completion)

Pursue only after the clinic workflow (§6), and only if they support the intake workflow. Items that are now scheduled as Phase 7 issues are marked.

* **Meaningful retrieval with provenance** — replace hash-based mock embeddings with a deterministic lexical baseline or real embeddings, cite sources in staff-facing summaries, and measure hit rate on labelled cases. Until this is done, documentation should not claim retrieval improves output quality.
* **Real-mode extraction evaluation** — nested field scoring and symptom precision/recall against labelled synthetic cases. Moved out of #22; extraction evaluation is now #40 (Phase 7).
* **FHIR R4 export** of a reviewed intake (e.g. `QuestionnaireResponse`). Now scheduled as #42, FHIR R4 Export of Reviewed Intakes (Phase 7).
* **Application-level encryption** of stored raw intake text.
* **Rate limiting** on the public intake endpoint.
* **Trace export** to an OpenTelemetry-compatible backend.

---

## 8. Explicitly Out of Scope

These would expand the project without materially improving it as evidence of production engineering:

* Voice agents, AI scribe, ambient documentation
* HL7 v2 parsing, a general EHR router, scheduling, billing, payments
* Additional agents (e.g. a reasoning agent; its empty placeholder was removed in #26) without a workflow need
* Multi-service cloud infrastructure (Lambda/RDS/S3/IAM Terraform) beyond the single deployed demo
* Vector database migration (FAISS/Chroma) without a measured retrieval problem
* Mobile apps
* "HIPAA compliant" labels, BAA mappings, or any processing of real patient data

---

## 9. Delivery Workflow

Each remaining work item is a PR-sized GitHub Issue:

```
Issue → branch → implementation → tests → PR → review → merge → project journal
```

* CI must pass before merge.
* Each phase closes with a journal entry under `docs/project_journal/` written from the closed issues.
* `project_status.md` is updated when a phase closes.

---

## 10. Risk Control

* Medical output stays non-diagnostic; safety rules run on every output.
* Synthetic data only, in all environments.
* Prompt and schema changes are version-controlled and run through the benchmark.
* Documentation is updated in the same PR as behaviour changes it describes.
