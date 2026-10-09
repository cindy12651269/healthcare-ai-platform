# Phase 6 — Security, Deployment & Handover

Healthcare AI Platform
Timeline: Phase 6 (2026-10-09)
Scope: Issues #34, #35, #36
Status: #34 and #35 closed; #36 (handover) in review — this journal is part of its PR and Phase 6 closes only after that PR is merged and validated.

---

## 1. Phase Goal

Finish the portfolio on top of the Phase 5 workflow ([`step3_roadmap.md`](../step3_roadmap.md) §6):

* An accurate security and data-handling document, with a test that audit logs contain no raw intake text (#34)
* One hosted, synthetic-data demo of the complete workflow, verified end to end (#35)
* Reviewer-ready handover documentation (#36)

---

## 2. Completed Issues

### Issue 34 — Security & Data-Handling Notes (PR #54, merge `6202f4e`)

* `docs/security_data_handling.md`: data flow (browser → API → pipeline → PostgreSQL, audit logs, webhook), masked vs stored data, threat model, and what HIPAA compliance would require. States that `intake_json.raw_text` is stored unmasked; makes no compliance claim. Supersedes the `compliance/*.md` stubs removed in #26.
* `tests/test_audit_no_raw_text.py`: the pipeline, API middleware and staff-action audit events written to the JSONL file contain no raw intake text, while the stored `intake_json` does. A mutation (raw text added to audit flags) makes the tests fail.
* Review fix before merge: corrected two over-broad claims (real-mode schema-validation errors can quote model output in audit `error` fields; legacy HIPAA wording exists in prompt/schema files).

### Issue 35 — Deployment: Hosted Demo Environment (PRs #55 `3e984e3`, #56 `d2aae25`)

* `render.yaml` (Render Blueprint): API and frontend from the existing Dockerfiles, managed PostgreSQL, free plans, health checks, `LLM_MODE=mock`, generated or dashboard-entered secrets.
* `scripts/start_api.sh`: migrate → idempotent synthetic seed (`db/seed_demo.py`) → server, stopping on failure.
* `scripts/hosted_check.py` and `scripts/verify_webhook.py`: the hosted acceptance flow and HMAC verification; also run in-process in CI (`tests/test_deploy_demo.py`), plus a migrate-then-seed test on PostgreSQL.
* Readiness review found that Render's `postgresql://` connection string selects psycopg v3 under SQLAlchemy 2.1, which is not installed; the start script pins `postgresql+psycopg2://`. Verified by running both images locally against PostgreSQL 15.
* Deployment incidents (no code change): the URLs initially used had mistyped Render suffixes (`-lovn`/`-l2s3` instead of `-tovn`/`-1s23`), and an environment-only deploy did not rebuild the frontend, so the bundle kept the Blueprint's default API URL. Fixed in the Render dashboard (`NEXT_PUBLIC_API_BASE_URL` with rebuild, `CORS_ALLOWED_ORIGINS`); the procedure was corrected in PR #56.
* Hosted verification (2026-10-09): `/health` 200 in mock mode; migrations and seed logged; `hosted_check` 8/8 PASS including cross-clinic 403; exactly one webhook delivered with a valid signature; no intake text in API logs; no secrets in the browser bundle ([`deployment.md`](../deployment.md) §7).

### Issue 36 — Portfolio Handover (in review)

README rewrite, architecture diagram ([`diagrams/architecture.md`](../diagrams/architecture.md)), decision records ([`decisions.md`](../decisions.md)), hosted walkthrough ([`demo_walkthrough.md`](../demo_walkthrough.md)), scope and contribution statement, status/roadmap updates, resolved accuracy notes in the Step 2/4/5 documents, and this journal.

---

## 3. Known Limitations Carried Forward

* Raw intake text stored unmasked and returned by `/api/ingest` (#32 finding); application logs not covered by the audit test.
* Rule-based safety and PHI heuristics; RAG not wired into the API; mock embeddings.
* Free-tier hosting: cold starts, 30-day database, ephemeral audit file; single environment and receiver.
* No login flow, MFA, token revocation or rate limiting.

## 4. Closure Status

Phase 6 closes when the #36 PR is reviewed and merged with green CI. Phase 7 (#40–#43) remains optional.
