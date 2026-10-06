# Phase 4 — Foundation & Provider Integration

Healthcare AI Platform
Timeline: Phase 4 (2026-10-05 – 2026-10-06)
Scope: Issues #22, #25, #26, #27, #28
Status: Completed

---

## 1. Phase Goal

Harden the Phase 3 prototype into a **CI-backed, provider-capable, multi-clinic foundation** for the clinical review workflow planned in Phase 5:

* An automated gate on every pull request and every push to `main`
* A repository that contains only real code and does not track runtime output
* A real LLM provider behind an explicit configuration flag, with mock mode kept as the default
* A data model that knows about clinics, users, roles and intake review status, with a reproducible migration path
* Authenticated staff access with server-side role checks and clinic isolation

Phase 3 made the system runnable and demonstrable. Phase 4 adds the foundations a clinic workflow needs. It does not build that workflow: the review queue, escalation rules and staff UI are Phase 5.

---

## 2. Summary of Accomplishments

Phase 4 progressed in three stages: put a gate in front of `main`, connect a real provider, then add the data and access boundaries.

### Delivery Foundation

* GitHub Actions CI: backend tests against PostgreSQL, a deterministic benchmark, and frontend checks and build
* Zero-byte placeholders removed; runtime audit logs and generated benchmark results untracked

### Provider Integration

* `LLM_MODE=mock|real` with a shared provider interface and an OpenAI implementation
* Real-mode output constrained to the agent JSON schemas, with controlled failures and no fallback to mock

### Multi-Clinic Foundation

* Data model v2: clinics, users, clinic memberships with roles, clinic-owned intake records with review status
* Staff bearer-token authentication, role checks and clinic isolation on the server

---

## 3. Completed Issues

All Phase 4 issues followed `Issue → branch → tests → PR → review → merge`. From #26 onward, every PR merged only after the #25 CI run passed on the exact PR head, and each merge was followed by a check of the push-to-`main` run for the merge commit.

Issues are listed in delivery order.

### Issue 22 — Real LLM Provider Integration (Configurable Mode)

**Status:** Completed (PR #37, merge commit `f898f92`; follow-up PR #38, merge commit `8c17dad`)

**Objective**
Run the existing agents against a real LLM provider behind a configuration flag, while keeping deterministic mock mode as the default for tests and CI.

**Key Deliverables (PR #37)**

* `LLM_MODE=mock|real` in `api/config.py`. Missing or empty means `mock`, and any other value fails at startup.
* Shared provider interface `generate_json` (`llm/provider.py`), used by `StructuringAgent` and `OutputAgent` in both modes:
  * `MockLLMProvider` wraps the existing deterministic builders.
  * `OpenAIProvider` (`llm/providers/openai_client.py`) handles real mode.
* OpenAI wrapper:
  * explicit per-request timeout;
  * bounded retries (`LLM_MAX_RETRIES`), only for timeouts, connection errors, 429 and 5xx;
  * other errors fail immediately;
  * sanitized error messages, so neither the key nor the provider payload leaks.
* No real → mock fallback:
  * the API refuses to start with `LLM_MODE=real` and no `OPENAI_API_KEY`;
  * `/api/ingest` maps provider failures to 502 and configuration errors to 503.
* `/health` reports `llm_mode`, and the UI shows it read-only. The key is read only by the backend.
* `evaluation/benchmark.py --mode mock|real [--limit N]`. Real output goes to a gitignored file.
* `tests/conftest.py` keeps tests hermetic: they never read the developer's `.env`, and they default to mock.

**Follow-up — Strict schema adaptation (PR #38)**

A post-merge real-provider smoke test failed. The structuring prompt allowed `null` for unknown fields, the schema did not, and the provider was only asked for generic JSON. OpenAI returned `severity: null`, and validation correctly rejected it.

* Each agent now passes its own schema (`structured_output.json`, `report_output.json`) to the provider.
* `OpenAIProvider` sends it as a strict `json_schema` response format (OpenAI Structured Outputs). The strict form is generated from the existing schema files: all properties required, `additionalProperties: false`, and optional fields made nullable.
* Nulls are stripped only from fields the original schema marks optional. Nulls in required fields still fail validation.
* The agents' `jsonschema` validation against the original schemas is unchanged and still mandatory.
* Report schema failures raise `ReportSchemaValidationError`, which `/api/ingest` maps to 422. The error message carries only the path and reason, never the model output.

**Validation**

* PR #37: 82 passed, 3 skipped (PostgreSQL), including 18 new provider tests, all with fake OpenAI clients.
  * Live checks on the branch: mock `/health` and `/api/ingest` worked, and startup failed as intended with `LLM_MODE=real` and no key, and with an invalid mode.
* PR #38: 91 passed, 3 skipped, including 9 new tests (one reproduces `severity=null`). Mock benchmark unchanged.
* Real-mode validation was performed locally by the maintainer with synthetic intake text and a local key: one `/api/ingest` request and `benchmark --mode real --limit 1`, as the PR #37/#38 post-merge steps describe. Real output is gitignored, and the results are not recorded in the PR descriptions.

**Design Notes**

* Mock mode stays the default and is the only mode CI uses.
* Real mode never silently degrades to mock.
* Nested real-mode extraction evaluation was moved out of #22. It is now part of #40 (Phase 7).

---

### Issue 25 — CI Pipeline (Tests, Frontend Build, Deterministic Benchmark)

**Status:** Completed (PR #39, merge commit `f24d756`)

**Objective**
Run the backend tests, PostgreSQL integration tests, the deterministic benchmark and the frontend checks on every change.

**Key Deliverables**

`.github/workflows/ci.yml` runs on pull requests to `main` and pushes to `main` (`ubuntu-latest`). It has three jobs:

| Job | What it runs |
| --- | --- |
| Backend | Python 3.11. Full `pytest` against a `postgres:15` service container with `TEST_DATABASE_URL` set. A guard step fails the job if any `tests/test_persistence_postgres.py` test is skipped, or if none passed. |
| Benchmark | `python -m evaluation.benchmark --mode mock --rag off` and `--rag on`. Each run must report `mode == "mock"` and success rate 1.0; the RAG-on run must also have retrieval hits. |
| Frontend | In `app/` on Node 22: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. |

* `LLM_MODE=mock` at workflow level. There is no `OPENAI_API_KEY`, no `secrets.*` reference, and the token has `contents: read` permission only. Real-provider runs are excluded.
* Benchmark output goes to separate CI files rather than the default results file.
* README section describing CI.

**Design Notes**

* The PostgreSQL integration tests used to skip silently without a database. CI now fails if they don't run.

---

### Issue 26 — Repository Hygiene (Placeholders & Tracked Runtime Artifacts)

**Status:** Completed (PR #44, merge commit `4bae872`)

**Objective**
Make the repository contain only real code and documentation, and make normal test and benchmark runs leave the working tree clean.

**Key Deliverables**

* Removed the 29 zero-byte scaffold files listed in the issue (agents, API middleware and routers, compliance, infrastructure, interoperability, two empty test files). Nothing imported or linked them. Each future owner is recorded in `docs/project_status.md` §4.
* `audit.jsonl` untracked and gitignored. Application audit logging is unchanged (`AUDIT_LOG_PATH`, `ENABLE_AUDIT_JSONL`), and an autouse fixture writes each test's audit output to a temporary directory.
* `evaluation/results/` treated as generated output: tracked results removed and the directory gitignored.
* Documentation references to the removed files corrected.

**Validation**

* `pytest` and `python -m evaluation.benchmark --mode mock` leave `git status --short` empty. This was checked in a fresh worktree of the PR head and again after the merge.
* CI on the PR and on `main`: 94 passed; 3 PostgreSQL integration tests ran.

**Design Notes**

* No placeholder was kept as a stub. Future work is owned by issues, not by empty files.

---

### Issue 27 — Data Model v2 & Migrations

**Status:** Completed (PR #45, merge commit `734b3d1`)

**Objective**
Add clinics, users and roles, clinic ownership of intakes, and intake review status, using a reproducible migration path.

**Key Deliverables**

* `db/migrations/002_clinics_users_review_status.sql` (`001` unchanged):
  * `clinics`, seeded with `default`;
  * `users`, with a unique email;
  * `clinic_memberships`: key (user, clinic), FKs, and `role` limited to `clinic_staff` / `clinic_admin`;
  * `health_records` gains:
    * `clinic_id`: FK, required for new rows;
    * `review_status`: `submitted` / `needs_review` / `reviewed` / `escalated`, default `submitted`;
    * `escalation_reason`;
    * an index on (clinic, status).
* ORM models (`Clinic`, `User`, `ClinicMembership`, new `HealthRecord` columns) matching the SQL constraints.
* `/api/ingest` assigns every intake to the seeded `default` clinic. The request body is unchanged, because a clinic id sent by an unauthenticated client can't be trusted.
* `docs/data_model.md` records the schema, the clinic-assignment decision and the migration decision.

**Migration Approach**

* Kept the existing ordered SQL runner (`db/migrate.py`, one transaction per file, tracked in `schema_migrations`, run on every Compose start). No migration framework was added.
* v1 → v2 upgrade: `clinic_id` is added with a temporary default that backfills existing rows, then the default is dropped. Existing rows become `default` / `submitted` with no escalation reason. No rows are rewritten or deleted.

**Validation**

* PostgreSQL tests, each in its own throwaway schema:
  * a fresh database migrates to v2, and a repeat run applies nothing;
  * a v1 database holding a record upgrades with the record intact;
  * rows without a clinic are rejected after the upgrade;
  * the check and FK constraints are enforced.
* SQLite model tests run with foreign keys on.
* `python -m db.migrate` was checked against a fresh database and against a database migrated by the previous `main`, holding a record.
* CI on the PR and on `main`: 108 passed; 9 PostgreSQL integration tests ran.

**Design Notes**

* `submitted` is the starting status, so an unflagged intake is distinguishable from one waiting in the review queue. #29 moves intakes to `needs_review`.
* Phase 4 adds the review **fields** only. The logic that sets and changes them (escalation rules, review transitions) is Phase 5.

---

### Issue 28 — Authentication, RBAC & Clinic Isolation

**Status:** Completed (PR #46, merge commit `7bec177`)

**Objective**
Authenticate clinic users and enforce role and clinic boundaries on the server, with tests.

**Key Deliverables**

* Staff authenticate with `Authorization: Bearer <token>`:
  * The token is a signed `{user id, expiry}` payload (HMAC-SHA256), keyed by `AUTH_TOKEN_SECRET` from the server environment (at least 32 characters).
  * Tokens are issued by an operator from the command line (`python -m api.auth`). There is no login endpoint and no password storage.
  * Only the standard library is used: no new dependency and no migration.
* Reusable dependencies in `api/auth.py`:
  * `get_current_principal`: 401 handling, and loads the user's **current** memberships from the database on every request;
  * `require_clinic_role(*roles)`: 403 if the caller isn't a member of the clinic in the path or lacks the role.
* Staff endpoints (`api/routers/clinics.py`):
  * `GET /api/staff/me`;
  * `GET /api/clinics/{clinic_id}/members` (staff or admin of that clinic);
  * `PUT` / `DELETE /api/clinics/{clinic_id}/members/{user_id}` (admin of that clinic only).
* `docs/auth.md`: mechanism, configuration, role permissions, isolation rule.

**Security Behaviour**

* Missing, malformed, tampered, wrongly signed or expired tokens, and unknown users, get 401. Without a valid server secret, staff endpoints return 503; unsigned tokens are never accepted.
* The token carries no clinic or role data. Removing a membership or changing a role takes effect immediately.
* Clinic access always comes from the caller's own memberships. A `clinic_id` in the query string or body has no effect, and the admin request body rejects extra fields with 422.
* Admins manage only their own clinic and can't change their own membership (409), so a clinic can't lose its admin by accident.
* `/api/ingest` stays unauthenticated: same consent gate, same default-clinic behaviour.

**Final Gate Fix**

The final security review found that a token with a non-ASCII signature made `hmac.compare_digest` raise `TypeError`, returning 500 instead of 401. It failed closed, but broke the 401 contract. The fix compares the encoded bytes. A regression test sends a raw non-ASCII signature header and expects 401. That test failed on the previous code and passes with the fix.

**Validation**

* 18 auth/RBAC tests on SQLite, against the real endpoints and dependencies with no mocked authorization layer:
  * token tampering and expiry; the non-ASCII signature case;
  * 401 and 503 handling;
  * staff and admin permissions; cross-clinic reads and writes;
  * attempts to bypass isolation with a `clinic_id`;
  * removal of a membership taking effect immediately;
  * unauthenticated ingest.
* A PostgreSQL integration test of the same boundaries against the migrated schema.

**Known Limitations**

* No browser sign-in and no staff UI. CORS is unchanged; the browser auth flow belongs with the staff UI (#31).
* No external identity provider or SSO.
* Revocation is limited: a single token can't be revoked before it expires, except by deleting the user or rotating `AUTH_TOKEN_SECRET` (which invalidates every token).
* No staff endpoint reads intake records yet. The records and review-queue API (#30) is Phase 5 and must use `require_clinic_role`.

---

## 4. Architecture Progress After Phase 4

### Request Paths

```
Patient (unauthenticated)
   → POST /api/ingest  (consent gate unchanged)
   → HealthcarePipeline  (LLM_MODE=mock default | real: OpenAI, strict JSON schema)
        IntakeAgent → StructuringAgent → OutputAgent → Safety Guard
   → health_records  (clinic_id = 'default', review_status = 'submitted')

Clinic staff / admin (Authorization: Bearer <signed token>)
   → get_current_principal  (signature + expiry, user + memberships from DB)
   → require_clinic_role     (clinic from path, checked against own memberships)
   → /api/staff/me, /api/clinics/{clinic_id}/members[/{user_id}]
```

### Delivery Path

```
Issue → branch → tests → PR
   → GitHub Actions: backend + PostgreSQL | mock benchmark RAG off/on | frontend
   → review → merge → push-to-main CI on the merge commit
```

---

## 5. Phase 4 Acceptance Criteria

| Requirement                                                          | Status    |
| -------------------------------------------------------------------- | --------- |
| CI on every PR and push to `main`, no provider credentials            | Completed |
| PostgreSQL integration tests run in CI and cannot skip silently       | Completed |
| Mock benchmark (RAG off/on) and frontend lint/typecheck/test/build    | Completed |
| No zero-byte placeholders; runtime artifacts untracked                | Completed |
| Tests and benchmark leave the working tree clean                      | Completed |
| `LLM_MODE=mock\|real`; mock default; no silent fallback                | Completed |
| Real-mode output validated against the agent schemas                  | Completed |
| Clinics, users, memberships and roles in the data model               | Completed |
| Clinic-owned intakes with review status and escalation reason fields  | Completed |
| Fresh and v1 → v2 migration, existing records preserved               | Completed |
| Staff authentication (401), role checks (403), cross-clinic denial    | Completed |
| Minimal clinic-admin membership management                            | Completed |
| `/api/ingest` unchanged for patients                                  | Completed |

---

## 6. Phase Closure Validation

**Final Phase 4 `main`:** `7bec1771a4f6ba8b4c294e262cd528874cc4b2f3` (merge of PR #46)

**Push-to-`main` CI for that commit (run 37437371747): success**

* Backend: 127 passed, including 18 auth/RBAC tests
* PostgreSQL integration: 10 tests ran and passed
* Benchmark: RAG off and RAG on green in mock mode (RAG on: 12 retrieval hits)
* Frontend: lint, typecheck, tests and build green

**Local check on that commit** (`LLM_MODE=mock`, no `OPENAI_API_KEY`)

* `pytest`: 117 passed, 10 skipped. The 10 skips are the PostgreSQL integration tests, because no local database was configured. CI runs them.
* `python -m evaluation.benchmark --mode mock`: 6/6 runs, success rate 1.00, 0 safety violations, required-field pass rate 1.00, schema-valid rate 1.00
* `git status --short` empty afterwards

---

## 7. Known Limitations and Deferred Work

Phase 4 delivers a **foundation**, not the clinic workflow. It is not production healthcare software.

### Carried Forward

* **No review workflow yet.** `review_status` and `escalation_reason` exist, but nothing sets them except the default. Escalation rules (#29), the records and review-queue API (#30) and the staff review UI (#31) are Phase 5.
* **Staff access is API-only**, with operator-issued tokens. There is no browser sign-in, SSO or per-token revocation (see Issue 28).
* **All patient intakes go to one seeded clinic.** Per-clinic intake routing is not defined.
* **Mock structuring output** is still a placeholder (empty symptom list, `"mock summary"`). The deterministic extraction baseline is #40 (Phase 7).
* **RAG is not wired into the API pipeline**; embeddings are deterministic placeholders.
* **Raw intake text** is stored unmasked; there is no application-level encryption.
* **No deployed environment.** Deployment is #35 (Phase 6).

### Not Part of Phase 4

* Review queue, escalation rules, staff review UI, escalation webhook (Phase 5)
* Security notes, deployment, portfolio handover (Phase 6)
* FHIR R4 export (#42) and the other demo and evidence work (Phase 7)
* Rate limiting, HIPAA compliance, production patient data

---

## 8. Transition to Phase 5

| Phase   | Title                                                | Issues           | Status    |
| ------- | ---------------------------------------------------- | ---------------- | --------- |
| Phase 1 | Core Foundation                                      | #1–#6            | Completed |
| Phase 2 | RAG + Safety + Persistence                           | #7–#11           | Completed |
| Phase 3 | UI + Evaluation + Observability                      | #12–#17          | Completed |
| Phase 4 | Foundation & Provider Integration                    | #22, #25–#28     | Completed |
| Phase 5 | Clinical Review & Escalation Workflow                | #29–#33          | Next      |
| Phase 6 | Security, Deployment & Handover                      | #34–#36          | Planned   |
| Phase 7 | Demo Experience, AI Evidence & FHIR Interoperability | #40–#43          | Planned   |

Phase 1 built the system spine. Phase 2 added grounding, safety and memory. Phase 3 made the system measurable, observable and runnable. Phase 4 put CI in front of every change, connected a real provider without giving up deterministic defaults, and gave the system clinics, roles and enforced clinic boundaries. Phase 5 builds the clinical review and escalation workflow on that foundation.
