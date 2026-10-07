# Project Status — Evidence-Based Capability Audit

**Audit date:** 2026-10-06 (Phase 4 closure)
**Audited commit:** `7bec177` (main)
**Previous audit:** 2026-10-02 at `e12c923`
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

A file existing in the repository is not evidence of implementation. The empty placeholder files found by the previous audit were removed in #26 (see §4).

---

## 2. Verification Performed

* GitHub Actions push-to-`main` run for `7bec177` (run 37437371747): backend **127 passed**, including the PostgreSQL integration tests (10 executed, none skipped) and 18 auth/RBAC tests; mock benchmark RAG off/on green; frontend lint, typecheck, tests and build green. CI uses `LLM_MODE=mock` and no provider credentials.
* Local, `LLM_MODE=mock`, no OpenAI key: `pytest` **117 passed, 10 skipped** (the PostgreSQL tests; no local database configured); `python -m evaluation.benchmark --mode mock` 6/6 runs, success rate 1.00, schema-valid rate 1.00; `git status` clean afterwards.

Resolved since the previous audit: `POST /api/ingest` returned HTTP 500 without an OpenAI key, and `AuditMiddleware` recorded handled HTTP errors as `success`. Both were fixed in PR #21 (Issue #20); `tests/test_ingest_e2e.py` exercises the unmocked path.

---

## 3. Capability Matrix

| Capability | Status | Evidence / notes |
| --- | --- | --- |
| Coherent end-to-end healthcare workflow | **PARTIAL** | Browser intake → `/api/ingest` → structuring → report → safety → clinic-owned `health_records` row works without an API key. Staff authentication and clinic boundaries exist (#28). There is no review step yet: escalation rules, review queue and staff review UI are Phase 5 (#29–#31). |
| FastAPI backend | **PARTIAL** | `/health`, `/`, `POST /api/ingest`, and the staff endpoints `GET /api/staff/me` and `/api/clinics/{clinic_id}/members` (#28, [`auth.md`](auth.md)). No read endpoints for stored records (#30, Phase 5). Response model `IngestResponse` is declared but not applied. |
| PostgreSQL persistence | **PARTIAL** | `HealthRecord` ORM, idempotency via `input_hash`, clinic ownership and review status (data model v2, #27, [`data_model.md`](data_model.md)); ordered SQL migrations (`db/migrate.py`) tested on PostgreSQL in CI, including a v1 → v2 upgrade; models tested on SQLite. Persistence is best-effort: a database error does not fail the request, and the outcome (`saved` / `duplicate` / `skipped` / `disabled` / `failed`) is reported in the trace (PR #23). |
| Redis / background work | **NOT NEEDED** (currently) | Redis runs in `docker-compose.yml` but no code uses it. |
| External / third-party integration | **PARTIAL** | OpenAI provider behind `LLM_MODE=real` (#22): timeout, bounded retries, strict JSON-schema output, controlled 502/503/422 errors, no fallback to mock. Mock remains the default and the only mode used in CI. The escalation webhook is #33 (Phase 5). |
| Authentication | **PARTIAL** | Backend complete for the staff API: HMAC-signed bearer tokens issued by an operator CLI, 401 for missing, invalid or expired tokens (#28, [`auth.md`](auth.md)). PARTIAL because there is no browser sign-in (with the staff UI, #31), no SSO, and per-token revocation is limited. Patient intake is intentionally unauthenticated. |
| Authorization / RBAC | **PARTIAL** | Reusable server-side `clinic_staff` / `clinic_admin` checks (403), re-read from the database on every request (#28). PARTIAL because the only staff operations so far are viewing and (admin) managing clinic membership; intake review operations are #30 (Phase 5). |
| Tenant / organization isolation | **PARTIAL** | Clinic-owned records (#27). Staff access is scoped to the caller's own clinic memberships, with cross-clinic denial tested on SQLite and PostgreSQL (#28). PARTIAL because no staff endpoint reads intakes yet (#30) and all ingested intakes go to one seeded clinic. |
| PHI / privacy handling | **PARTIAL** | Keyword PHI heuristic + consent gate at intake (`agents/intake_agent.py`); regex PHI masking of report output (`llm/safety_guard.py`). Raw intake text is persisted unmasked. Heuristics are explicitly not a validated de-identification method. |
| Encryption / data protection | **ABSENT** | Encryption at rest is assumed at infrastructure level only; nothing is deployed. No field-level encryption. |
| Audit logging | **PARTIAL** | Per-run and per-request events (`observability/audit_logger.py`, `api/middleware/audit.py`); the JSONL file is not tracked (#26). No actor identity and no user-action audit (#30). |
| AI safety guardrails | **COMPLETE** (rule-based scope) | Deterministic guard: diagnosis/prescription blocking, PHI masking, emergency-language guidance; unit tested (`tests/test_safety_guard.py`). Evaluated against a small labelled synthetic set in mock mode (#32, `docs/evaluation_benchmark.md`), with 4 known gaps recorded. |
| Human escalation | **PLANNED** | `review_status` and `escalation_reason` columns exist (#27), but nothing sets them beyond the default `submitted`. Emergency detection appends guidance text only. Escalation rules are #29 (Phase 5). |
| RAG / retrieval quality | **PARTIAL** | Retrieval agent, in-memory vector store and seeding exist and are tested. Embeddings are SHA-256-derived mock vectors, so ranking carries no semantic meaning; RAG is not wired into the API pipeline (`api/deps.py`). Retrieval quality is unmeasured. |
| AI / LLM evaluation | **PARTIAL** | Deterministic benchmark harness, schema validity, field-presence and coverage proxies (`evaluation/`), run in CI with RAG off/on. In mock mode the scores measure contract stability, not model quality. `--mode real --limit N` is opt-in and never run in CI. Extraction evaluation is #40, and the safety/escalation set is #32. |
| Observability (metrics / tracing) | **COMPLETE** (local scope) | Stage-level timings, p50/p95 aggregation in benchmark, run IDs (`observability/`). No exporter or dashboard. |
| Automated testing | **COMPLETE** (current scope) | Unit, contract and auth/RBAC tests; an unmocked API → pipeline → PostgreSQL integration suite (migrations, ingest, isolation) that CI fails if skipped; frontend unit tests. All run in CI on every PR and push to `main` (counts in §2). No automated browser E2E test. |
| Deployment / CI/CD | **PARTIAL** | GitHub Actions CI on every PR and push to `main` (#25). Dockerfiles and Docker Compose for local use, with automatic migrations. No deployed environment (#35, Phase 6). |
| Frontend / UI | **PARTIAL** | Next.js patient intake UI with a developer trace panel (#16), linted, type-checked, tested and built in CI. No staff UI (#31, Phase 5). |
| Reliability / error handling | **PARTIAL** | Typed intake, structuring and report errors mapped to 400/422; provider failures to 502 and configuration errors to 503, with LLM timeouts and bounded retries (#22). Retrieval failure is non-fatal, and persistence outcomes are reported. A blocked safety output still surfaces as a 500. |
| Documentation / handover | **PARTIAL** | Architecture, API, data-model, auth and evaluation docs; Phase 1–4 journals; README covers setup, CI and LLM mode. Some reference docs describe Phase 2 behaviour (accuracy banners added to them). Full handover documentation is #36 (Phase 6). |
| FHIR / interoperability | **PLANNED** | Not implemented. FHIR R4 export of reviewed intakes is #42 (Phase 7). HL7 v2 and a general EHR router are out of scope (roadmap §8). |
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
| `api/middleware/rate_limit.py` | Optional enhancement, roadmap §7 (rate limiting) |
| `interoperability/fhir_client.py`, `docs/interoperability/fhir_mapping.md` | #42 FHIR R4 Export of Reviewed Intakes (Phase 7) |
| `agents/reasoning_agent.py`, `llm/prompts/reasoning.txt`; `interoperability/hl7_parser.py`, `ehr_router.py`, `consent.py`; `docs/interoperability/hl7_notes.md`, `ehr_router_design.md`; `tests/test_ehr.py`, `tests/test_llm.py` | Not planned, roadmap §8 (extra agents, HL7 v2, general EHR router); the empty test files had no tests |

The runtime audit log (`audit.jsonl`) and generated benchmark results (`evaluation/results/`) are no longer tracked (#26).

---

## 5. Completed Work by Phase

| Phase | Issues | Status | Record |
| --- | --- | --- | --- |
| Phase 1 — Core Foundation | #1–#6 | Closed | [`phase1_core_foundation.md.md`](project_journal/phase1_core_foundation.md.md) |
| Phase 2 — RAG + Safety + Persistence | #7–#11 | Closed | [`phase2_rag_safety_persistence.md`](project_journal/phase2_rag_safety_persistence.md) |
| Phase 3 — UI + Evaluation + Observability | #12–#17 | Closed | [`phase3_UI_Evaluation_Observability.md`](project_journal/phase3_UI_Evaluation_Observability.md) |
| Phase 4 — Foundation & Provider Integration | #22, #25–#28 | Closed | [`phase4_Foundation_&_Provider_Integration.md`](project_journal/phase4_Foundation_&_Provider_Integration.md) |
| Phase 5 — Clinical Review & Escalation Workflow | #29–#33 | Open | See roadmap |
| Phase 6 — Security, Deployment & Handover | #34–#36 | Open | See roadmap |
| Phase 7 — Demo Experience, AI Evidence & FHIR Interoperability | #40–#43 | Open | See roadmap |

The journals are historical records written at the time each phase closed. Where this audit qualifies a journal statement (for example, mock-mode retrieval "improving grounding"), the qualification is recorded here rather than by editing the journal.
