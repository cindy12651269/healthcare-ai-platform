# Project Status — Evidence-Based Capability Audit

**Audit date:** 2026-10-09 (Phase 6 closure)
**Audited commit:** `8affdfd` (main, merge of PR #58; #34–#36 closed, Phase 6 complete). §2 records the Phase 5 closure run at `eb92cac`; §2a adds the Phase 6 verification.
**Previous audit:** 2026-10-07 at `eb92cac`
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

* GitHub Actions push-to-`main` run for `eb92cac` (run 37623090041):
  * backend **194 passed**, including the PostgreSQL integration tests (10 executed, none skipped);
  * mock benchmark RAG off/on green, and the safety & escalation suite at its 1.0 baseline in all four categories;
  * frontend lint, typecheck, tests and build green.

  CI uses `LLM_MODE=mock` and no provider or webhook credentials.
* Local, `LLM_MODE=mock`, no OpenAI key:
  * `pytest` **184 passed, 10 skipped** (the PostgreSQL tests; no local database configured);
  * `python -m evaluation.benchmark --mode mock` 6/6 runs, success rate 1.00, schema-valid rate 1.00;
  * `--suite safety` 16/16 guard and escalation matches, byte-identical across two runs;
  * frontend 44 tests passed;
  * `git status` clean afterwards.

### 2a. Phase 6 verification (2026-10-09)

* CI green on `main` after every Phase 6 merge: `6202f4e` (#54), `3e984e3` (#55), `d2aae25` (#56), `827aaef` (#57), `8affdfd` (#58). At `8affdfd` (run 37922018957): backend **209 passed** with 11 PostgreSQL integration tests executed, including `tests/test_audit_no_raw_text.py` (#34) and `tests/test_deploy_demo.py` (#35); frontend 44 tests passed; benchmark and safety suite green.
* Hosted demo ([`deployment.md`](deployment.md) §7): `/health` 200 in mock mode; migrations and synthetic seed on deploy; `scripts/hosted_check.py` 8/8 PASS (flagged intake in clinic `default`'s queue, cross-clinic 403); exactly one webhook with a valid HMAC signature; no intake text in API logs; no secrets in the browser bundle.

Resolved earlier (Phase 3): `POST /api/ingest` returned HTTP 500 without an OpenAI key, and `AuditMiddleware` recorded handled HTTP errors as `success`. Both were fixed in PR #21 (Issue #20); `tests/test_ingest_e2e.py` exercises the unmocked path.

---

## 3. Capability Matrix

| Capability | Status | Evidence / notes |
| --- | --- | --- |
| Coherent end-to-end healthcare workflow | **COMPLETE** (demo scope) | Browser intake → `/api/ingest` → structuring → report → safety → escalation rules (#29) → clinic-owned `health_records` row, without an API key. Staff then sign in at `/staff` (#31), work the clinic's review queue and mark intakes reviewed or escalated (#30). Escalated intakes trigger a signed webhook when one is configured (#33). Tested in CI, checked in a local browser, and verified on the hosted demo (#35, [`deployment.md`](deployment.md) §7). |
| FastAPI backend | **PARTIAL** | `/health`, `/`, `POST /api/ingest`; staff endpoints `GET /api/staff/me` and `/api/clinics/{clinic_id}/members` (#28, [`auth.md`](auth.md)); clinic-scoped intake list, detail and transition endpoints (#30, [`review_queue_api.md`](review_queue_api.md)). PARTIAL because `IngestResponse` is declared but not applied: `/api/ingest` returns the full pipeline trace, including raw intake text and guard evidence (see PHI row). |
| PostgreSQL persistence | **PARTIAL** | `HealthRecord` ORM, idempotency via `input_hash`, clinic ownership and review status (data model v2, #27, [`data_model.md`](data_model.md)); ordered SQL migrations (`db/migrate.py`) tested on PostgreSQL in CI, including a v1 → v2 upgrade; models tested on SQLite. Persistence is best-effort: a database error does not fail the request, and the outcome (`saved` / `duplicate` / `skipped` / `disabled` / `failed`) is reported in the trace (PR #23). |
| Redis / background work | **NOT NEEDED** (currently) | Redis runs in `docker-compose.yml` but no code uses it. |
| External / third-party integration | **PARTIAL** | OpenAI provider behind `LLM_MODE=real` (#22): timeout, bounded retries, strict JSON-schema output, controlled 502/503/422 errors, no fallback to mock. Mock remains the default and the only mode used in CI. Signed escalation webhook (#33, [`escalation_webhook.md`](escalation_webhook.md)): HMAC-SHA256, idempotency key, bounded retries and a delivery log. It is one logical notification with bounded attempts, not a delivery guarantee: single receiver, no automatic resend. FHIR export is #42 (Phase 7). |
| Authentication | **PARTIAL** | HMAC-signed bearer tokens issued by an operator CLI, 401 for missing, invalid or expired tokens (#28, [`auth.md`](auth.md)). The staff UI (#31) uses the same token, pasted by the staff member and kept in browser memory only. PARTIAL because there is no login flow or SSO, and per-token revocation is limited. Patient intake is intentionally unauthenticated. |
| Authorization / RBAC | **COMPLETE** (current scope) | Reusable server-side `clinic_staff` / `clinic_admin` checks (403), re-read from the database on every request (#28). They are applied to membership management and to every intake review endpoint (#30). The UI makes no access decisions. |
| Tenant / organization isolation | **PARTIAL** | Clinic-owned records (#27). Staff access is scoped to the caller's own memberships, and every intake query filters on the authorized clinic, so another clinic's intake reads as 404. Cross-clinic denial is tested on SQLite (#28, #30) and PostgreSQL (#28). PARTIAL because all ingested intakes go to one seeded clinic; per-clinic intake routing is not defined. |
| PHI / privacy handling | **PARTIAL** | Keyword PHI heuristic + consent gate at intake (`agents/intake_agent.py`); regex PHI masking of rendered report text (`llm/safety_guard.py`). The escalation webhook payload carries no PHI (#33). Raw intake text is persisted unmasked. `/api/ingest` returns raw PHI to the browser in `intake.raw_text`, `structured.clinical_structuring.chief_complaint` and the guard evidence (`report.safety_checks.events[].reasons[].match`, `safety.reasons[].match`), a #32 finding that is not yet fixed. Heuristics are explicitly not a validated de-identification method. |
| Encryption / data protection | **ABSENT** | No application-level or field-level encryption; the hosted demo relies on the platform's defaults, which this project has not assessed. HTTPS is provided by the hosting platform. |
| Audit logging | **PARTIAL** | Per-run and per-request events (`observability/audit_logger.py`, `api/middleware/audit.py`); the JSONL file is not tracked (#26). Staff list, read and transition actions carry `actor_id`, `action` and `resource_id`, with no intake text (#30). `tests/test_audit_no_raw_text.py` verifies that pipeline, request and staff-action events contain no raw intake text (#34). PARTIAL because events go to a local JSONL file (ephemeral on the hosted demo; also printed to stdout) with no retention or tamper evidence. |
| AI safety guardrails | **COMPLETE** (rule-based scope) | Deterministic guard: diagnosis/prescription blocking, PHI masking of report text, emergency-language guidance; unit tested (`tests/test_safety_guard.py`). Measured against a small labelled synthetic set in mock mode (#32, [`evaluation_benchmark.md`](evaluation_benchmark.md)). Match rates of 1.00 mean behaviour agrees with the labelled current baseline, not safety accuracy or recall. 4 labelled gaps and a raw-PHI-evidence finding are recorded, not fixed. |
| Human escalation | **COMPLETE** (rule-based scope) | Emergency signals, blocked diagnosis/prescription output and low confidence (< 0.5) set `review_status = needs_review` with reason codes (#29, [`data_model.md`](data_model.md#escalation-rules-29)). A blocked report returns a safe acknowledgement instead of a 500. Staff resolve flagged intakes through the API and UI (#30, #31). The mock structuring agent always reports confidence 0.9, so `low_confidence` occurs only in real mode or tests. |
| RAG / retrieval quality | **PARTIAL** | Retrieval agent, in-memory vector store and seeding exist and are tested. Embeddings are SHA-256-derived mock vectors, so ranking carries no semantic meaning; RAG is not wired into the API pipeline (`api/deps.py`). Retrieval quality is unmeasured. |
| AI / LLM evaluation | **PARTIAL** | Deterministic benchmark harness, schema validity, field-presence and coverage proxies (`evaluation/`), run in CI with RAG off/on. In mock mode the scores measure contract stability, not model quality. Labelled safety & escalation suite (#32) with per-category match rates, gated in CI. `--mode real --limit N` is opt-in and never run in CI. Extraction evaluation is #40. |
| Observability (metrics / tracing) | **COMPLETE** (local scope) | Stage-level timings, p50/p95 aggregation in benchmark, run IDs (`observability/`). No exporter or dashboard. |
| Automated testing | **COMPLETE** (current scope) | Unit, contract, auth/RBAC, review-queue, escalation, safety-evaluation and webhook tests (webhook delivery uses fake and loopback receivers, no network). An unmocked API → pipeline → PostgreSQL integration suite (migrations 001–003, ingest, isolation) that CI fails if skipped. Frontend unit tests for the patient and staff UIs. All run in CI on every PR and push to `main` (counts in §2). No automated browser E2E test. |
| Deployment / CI/CD | **COMPLETE** (single demo environment) | GitHub Actions CI on every PR and push to `main` (#25). Dockerfiles and Docker Compose for local use, with automatic migrations. One hosted demo on Render free plans from `render.yaml`, with migrations, synthetic demo seed and health checks on deploy; hosted acceptance flow verified 2026-10-09 ([`deployment.md`](deployment.md), #35). Free-tier limits: services sleep when idle; the free database expires after 30 days. |
| Frontend / UI | **COMPLETE** (demo scope) | Next.js patient intake UI with a developer trace panel (#16) and a staff review workspace at `/staff` (#31, [`staff_review_ui.md`](staff_review_ui.md)). Both are linted, type-checked, tested and built in CI. The staff flow was checked manually in a browser; there is no automated browser E2E test. |
| Reliability / error handling | **PARTIAL** | Typed intake, structuring and report errors mapped to 400/422; provider failures to 502 and configuration errors to 503, with LLM timeouts and bounded retries (#22). A blocked safety output returns 200 with a safe acknowledgement (#29). Retrieval failure is non-fatal, persistence outcomes are reported, and webhook failures never fail the request (#33). Webhook delivery is synchronous, with no total deadline and no resend. |
| Documentation / handover | **COMPLETE** (portfolio scope) | Architecture, API, data-model, auth, review-queue, staff-UI, evaluation, webhook, security and deployment docs; Phase 1–6 journals. Handover (#36, PR #57): README, [`diagrams/architecture.md`](diagrams/architecture.md), [`decisions.md`](decisions.md), [`demo_walkthrough.md`](demo_walkthrough.md); the Step 2/4/5 documents are marked as historical with current-state notes. |
| FHIR / interoperability | **PLANNED** | Not implemented. FHIR R4 export of reviewed intakes is #42 (Phase 7). HL7 v2 and a general EHR router are out of scope (roadmap §8). |
| Explainability / evidence provenance | **PARTIAL** | Run trace exposes intake, structured output, retrieval chunks and safety reasons. Report output does not cite retrieval sources. |

---

## 4. Placeholder Files (Removed in #26)

The empty scaffold files listed at the audited commit were removed in #26; none contained code or content, and nothing imported or linked them. Their future work is owned as follows:

| Removed placeholders | Owner |
| --- | --- |
| `api/middleware/auth.py` | #28 Authentication, RBAC & Clinic Isolation |
| `api/routers/analyze.py`, `api/routers/report.py` | #30 Records & Review-Queue API (delivered as `api/routers/records.py`) |
| `app/components/AdminPanel.tsx` | #31 Staff Review UI (delivered as `app/components/StaffReview.tsx`) |
| `compliance/*.md` (BAA map, data flow, HIPAA overview, RBAC, threat model) | #34 Security & Data-Handling Notes — superseded by the single canonical [`security_data_handling.md`](security_data_handling.md); not recreated (BAA mappings and "HIPAA compliant" labels are out of scope, roadmap §8) |
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
| Phase 5 — Clinical Review & Escalation Workflow | #29–#33 | Closed | [`phase5_Clinical_Review_&_Escalation_Workflow.md`](project_journal/phase5_Clinical_Review_&_Escalation_Workflow.md) |
| Phase 6 — Security, Deployment & Handover | #34–#36 | Closed | [`phase6_Security_Deployment_&_Handover.md`](project_journal/phase6_Security_Deployment_&_Handover.md) |
| Phase 7 — Demo Experience, AI Evidence & FHIR Interoperability | #40–#43 | Open | See roadmap |

The journals are historical records written at the time each phase closed. Where this audit qualifies a journal statement (for example, mock-mode retrieval "improving grounding"), the qualification is recorded here rather than by editing the journal.
