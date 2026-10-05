# Project Status — Evidence-Based Capability Audit

**Audit date:** 2026-10-02
**Audited commit:** `e12c923` (main)
**Source of truth for implementation progress:** GitHub Issues / Projects. This document records what the repository *actually does* at the audited commit, so that reviewers can distinguish working code from planned work.

Related documents:

* Roadmap and remaining scope: [`step3_roadmap.md`](step3_roadmap.md)
* Historical records of completed work: [`project_journal/`](project_journal/)

---

## 1. Status Legend

| Status | Meaning |
| --- | --- |
| **COMPLETE** | Implemented, exercised by tests or verified manually at the audited commit |
| **PARTIAL** | Implemented in part, or implemented but not reachable through the default runtime path |
| **PLANNED** | Scheduled in the roadmap; not implemented |
| **ABSENT** | Not implemented and not currently scheduled in the minimum scope |
| **NOT NEEDED** | Deliberately out of scope for this portfolio |

A file existing in the repository is not evidence of implementation. Several directories contain empty placeholder files (see §4).

---

## 2. Verification Performed

* `pytest` — **39 passed** (mock agents / SQLite; no network).
* `POST /api/ingest` through the real app with default dependencies and no OpenAI key — **HTTP 500**. `OutputAgent` always calls the OpenAI API; there is no mock path for report generation. The API tests pass because they monkeypatch `HealthcarePipeline.run`.
* The same failed request was recorded by `AuditMiddleware` with `"status": "success"`, because handled HTTP errors are returned as responses rather than raised.

---

## 3. Capability Matrix

| Capability | Status | Evidence / notes |
| --- | --- | --- |
| Coherent end-to-end healthcare workflow | **PARTIAL** | Intake → structuring → report → safety pipeline exists (`agents/pipeline.py`). No defined end user beyond "submitter", no review step, no UI, and the default API path does not complete without an OpenAI key. |
| FastAPI backend | **PARTIAL** | `/health`, `/`, `POST /api/ingest`. No read endpoints for stored records. Empty `api/routers/analyze.py` / `report.py` placeholders removed in #26; read endpoints are #30. Response model `IngestResponse` is declared but not applied. |
| PostgreSQL persistence | **PARTIAL** | `HealthRecord` ORM, idempotency via `input_hash`, raw SQL migration; model tested on SQLite. Pipeline persistence is best-effort and swallows errors; `HealthRecord.from_pipeline_trace` expects `report.clinical_structuring.clinical_summary`, which the real `OutputAgent` report schema does not produce. No migration tool. |
| Redis / background work | **NOT NEEDED** (currently) | Redis runs in `docker-compose.yml` but no code uses it. |
| External / third-party integration | **PARTIAL** | OpenAI client call in `OutputAgent` (no timeout/retry/fallback). No other integrations. |
| Authentication | **ABSENT** | Not implemented (#28); the empty `api/middleware/auth.py` placeholder was removed in #26. |
| Authorization / RBAC | **ABSENT** | No roles or permission checks. |
| Tenant / organization isolation | **ABSENT** | No organization concept in the data model. |
| PHI / privacy handling | **PARTIAL** | Keyword PHI heuristic + consent gate at intake (`agents/intake_agent.py`); regex PHI masking of report output (`llm/safety_guard.py`). Raw intake text is persisted unmasked. Heuristics are explicitly not a validated de-identification method. |
| Encryption / data protection | **ABSENT** | Encryption at rest is assumed at infrastructure level only; nothing is deployed. No field-level encryption. |
| Audit logging | **PARTIAL** | Per-run and per-request JSONL events (`observability/audit_logger.py`, `api/middleware/audit.py`). No actor identity, no user-action audit, status bug noted in §2. |
| AI safety guardrails | **COMPLETE** (rule-based scope) | Deterministic guard: diagnosis/prescription blocking, PHI masking, emergency-language guidance; unit tested (`tests/test_safety_guard.py`). Not evaluated against a labelled safety set. |
| Human escalation | **ABSENT** | Emergency detection appends guidance text only. `escalation_required` exists in the structuring schema but nothing routes or reviews it. |
| RAG / retrieval quality | **PARTIAL** | Retrieval agent, in-memory vector store and seeding exist and are tested. Embeddings are SHA-256-derived mock vectors, so ranking carries no semantic meaning; RAG is not wired into the API pipeline (`api/deps.py`). Retrieval quality is unmeasured. |
| AI / LLM evaluation | **PARTIAL** | Deterministic benchmark harness, schema validity, field-presence and coverage proxies (`evaluation/`). In mock mode the scores measure contract stability, not model quality. |
| Observability (metrics / tracing) | **COMPLETE** (local scope) | Stage-level timings, p50/p95 aggregation in benchmark, run IDs (`observability/`). No exporter or dashboard. |
| Automated testing | **PARTIAL** | 39 unit/contract tests. No un-mocked API → pipeline → DB integration test. |
| Deployment / CI/CD | **ABSENT** | Dockerfile + docker-compose for local use. No `.github/workflows`, no deployed environment; empty `infra/` Terraform placeholders removed in #26 (deployment is #35). `requirements.txt` omits packages the code imports (e.g. SQLAlchemy, jsonschema, openai). |
| Frontend / UI | **ABSENT** | All files under `app/` are empty. Tracked as open Issue #16. |
| Reliability / error handling | **PARTIAL** | Typed intake/structuring errors mapped to 400/422; retrieval failure is non-fatal. No LLM timeouts/retries; persistence failures are silent. |
| Documentation / handover | **PARTIAL** | Architecture, API, evaluation docs and Phase 1–2 journals exist. README is a single heading. Some reference docs describe behaviour the code does not have (banners added to those docs). |
| FHIR / interoperability | **ABSENT** (deferred) | Not implemented; empty `interoperability/` and `docs/interoperability/` placeholders removed in #26. FHIR export is optional (roadmap §7). |
| Explainability / evidence provenance | **PARTIAL** | Run trace exposes intake, structured output, retrieval chunks and safety reasons. Report output does not cite retrieval sources. |

---

## 4. Placeholder Files (Removed in #26)

The empty scaffold files listed at the audited commit were removed in #26; none contained code or content, and nothing imported or linked them. Their future work is owned as follows:

| Removed placeholders | Owner |
| --- | --- |
| `api/middleware/auth.py` | #28 Authentication, RBAC & Clinic Isolation |
| `api/routers/analyze.py`, `api/routers/report.py` | #30 Records & Review-Queue API |
| `app/components/AdminPanel.tsx` | #31 Staff Review UI |
| `compliance/*.md` (BAA map, data flow, HIPAA overview, RBAC, threat model) | #34 Security & Data-Handling Notes (BAA mappings and "HIPAA compliant" labels are out of scope, roadmap §8) |
| `docs/infra/*.md`, `infra/aws/*.tf`, `infra/docker/services.yml` | #35 Deployment (multi-service Terraform is out of scope, roadmap §8) |
| `api/middleware/rate_limit.py`; `interoperability/fhir_client.py`, `docs/interoperability/fhir_mapping.md` | Optional enhancements, roadmap §7 (rate limiting, FHIR export) |
| `agents/reasoning_agent.py`, `llm/prompts/reasoning.txt`; `interoperability/hl7_parser.py`, `ehr_router.py`, `consent.py`; `docs/interoperability/hl7_notes.md`, `ehr_router_design.md`; `tests/test_ehr.py`, `tests/test_llm.py` | Not planned, roadmap §8 (extra agents, HL7 v2, general EHR router); the empty test files had no tests |

The runtime audit log (`audit.jsonl`) and generated benchmark results (`evaluation/results/`) are no longer tracked (#26).

---

## 5. Completed Work by Phase

| Phase | Issues | Status | Record |
| --- | --- | --- | --- |
| Phase 1 — Core Foundation | #1–#6 | Closed | [`phase1_core_foundation.md.md`](project_journal/phase1_core_foundation.md.md) |
| Phase 2 — RAG + Safety + Persistence | #7–#11 | Closed | [`phase2_rag_safety_persistence.md`](project_journal/phase2_rag_safety_persistence.md) |
| Phase 3 — evaluation & observability portion | #12–#15 | Closed | Journal to be written when Phase 3 closes |
| Phase 3 — remaining | #16, #17 open; further items proposed, not yet issues | Open | See roadmap |

The journals are historical records written at the time each phase closed. Where this audit qualifies a journal statement (for example, mock-mode retrieval "improving grounding"), the qualification is recorded here rather than by editing the journal.
