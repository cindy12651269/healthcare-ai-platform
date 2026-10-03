# Phase 3 — UI + Evaluation + Observability

Healthcare AI Platform
Timeline: Phase 3
Scope: Issues #12–#17
Status: Completed

---

## 1. Phase Goal

Turn the Phase 2 backend (RAG, safety guard, persistence) into a system that can be **measured, observed, and demonstrated**:

* Deterministic evaluation of pipeline output
* Structured, field-level scoring of that output
* Per-run audit events and stage-level latency metrics
* A browser-based patient intake demo backed by the real `/api/ingest` endpoint
* A reproducible local runtime: clean dependency install, Docker Compose stack, and working PostgreSQL persistence

Phase 2 produced a capable backend that could only be exercised through tests. Phase 3 makes it something a reviewer can run, submit an intake to, and inspect.

---

## 2. Summary of Accomplishments

Phase 3 progressed in three stages: measure the pipeline, observe the pipeline, then put a working application in front of it.

### Evaluation and Scoring

* Added a deterministic benchmark CLI (`python -m evaluation.benchmark`) with RAG on/off modes
* Added per-run and aggregated metrics (success, safety violations, retrieval hits, latency)
* Added field-level proxy scoring for structured output (required-field presence, schema validity, coverage, symptom consistency)

### Observability

* Added a per-run audit event schema and `audit_logger.log_run()` with console and optional JSONL output
* Added `TraceContext` and API-level `AuditMiddleware`
* Added a strict per-run metrics contract with stage-level latency (intake, structuring, retrieval, output, safety, persistence)
* Added deterministic latency aggregation (mean, p50, p95) to benchmark output

### Demonstrable Application

* Built a Next.js patient intake UI that calls the real FastAPI `/api/ingest` endpoint
* Added a collapsed, read-only developer trace view (metrics, retrieval, safety, response JSON)
* Restored the deterministic no-key `/api/ingest` path (supporting work, Issue #20 / PR #21)
* Completed the runtime dependency manifest, Docker Compose integration, automatic schema migration, and PostgreSQL persistence

---

## 3. Completed Issues

Issues #12–#15 were delivered as direct commits to `main`. Issues #16 and #17 followed the `Issue → branch → tests → PR → review → merge` workflow introduced by the documentation realignment in PR #18.

### Issue 12 — Evaluation Harness v1 (Deterministic Benchmarks + Metrics Output)

**Status:** Completed

**Objective**
Run predefined test cases through `HealthcarePipeline` (RAG on/off), compute core metrics, and produce reproducible benchmark results suitable for CI.

**Key Deliverables**

* CLI entry point: `python -m evaluation.benchmark --mode mock --rag on|off`
* `evaluation/test_cases.json` executed sequentially as stateless runs
* Mock mode and disabled persistence by default
* Deterministic behavior: fixed seed, stable `run_id`, sorted JSON output
* Per-run metrics: `success`, `safety_violation_count`, `retrieval_hit_count`
* Aggregated metrics: `total_runs`, `success_rate`, `avg_latency_ms`, `total_safety_violations`, `total_retrieval_hits`
* Console summary plus optional JSON output under `evaluation/results/`
* `tests/test_benchmark.py`
* `docs/evaluation_benchmark.md`

**Design Notes**

* The benchmark is a regression instrument, not a clinical accuracy measure
* Mock-mode determinism keeps benchmark output comparable between runs

---

### Issue 13 — Structured Accuracy Scoring v1 (Field-Level Proxy Metrics)

**Status:** Completed

**Objective**
Approximate structured-output accuracy with field-level proxy metrics, without requiring real medical ground truth.

**Key Deliverables**

* Structured validation metrics in `evaluation/metrics.py`:
  * `required_field_presence_rate`
  * `is_schema_valid`
  * `compute_coverage` (non-empty field percentage)
  * `symptom_consistency` (basic symptom matching)
* `compute_run_metrics()` accepts expected data from the test cases
* Aggregates: `avg_coverage`, `required_field_pass_rate`, `schema_valid_rate`
* Symptom ground truth added to `evaluation/test_cases.json`
* Structured output schema aligned in `agents/structuring_agent.py`
* Schema tests in `tests/test_agents.py`
* `docs/evaluation_design.md`

**Design Notes**

* These are **proxy** metrics: they measure structure and consistency, not medical correctness
* RAG on/off runs can be compared using the same scoring

---

### Issue 14 — Observability Integration: Audit Logger (Per-Run Event Tracking)

**Status:** Completed

**Objective**
Record structured, traceable execution metadata for every pipeline run.

**Key Deliverables**

* Audit event schema: `run_id`, timestamp, status, flags, `latency_ms`, `safety_violation_count`, `retrieval_hit_count`, error
* `observability/audit_logger.py` with `log_run(event)`
* Pipeline emits audit events on both success and failure
* Console output plus optional JSONL file (`ENABLE_AUDIT_JSONL`, `AUDIT_LOG_PATH`)
* `observability/tracing.py` (`TraceContext`)
* `api/middleware/audit.py` registered in `api/main.py`

**Design Notes**

* Audit events carry execution metadata and counts rather than clinical content
* A later defect, where handled HTTP errors were recorded as `success`, was fixed in PR #21 (see Issue #20 below)

---

### Issue 15 — Observability Metrics: Latency + Stage-Level Instrumentation

**Status:** Completed

**Objective**
Introduce stage-level timing and a single metrics schema shared by the pipeline and the benchmark.

**Key Deliverables**

* `observability/metrics.py`:
  * `build_run_metrics()` — strict per-run contract (`intake_ms`, `structuring_ms`, `retrieval_ms`, `output_ms`, `safety_ms`, `persistence_ms`, `latency_ms`, plus safety and retrieval counts)
  * `compute_aggregate_latency()` — mean, p50, p95
* `TraceContext` extended with stage-level timing fields
* Stage timers in `agents/pipeline.py`
* Benchmark output standardized on the pipeline metrics schema, with latency aggregation

**Design Notes**

* Metrics only; Issue 15 added no new logging behavior
* Stages that do not run report `0.0`, so the contract is always complete
* Mock-mode determinism preserved

---

### Issue 16 — Patient Intake Demo UI (Next.js) with Developer Trace View

**Status:** Completed (primary implementation: PR #19)

**Objective**
Provide a browser workflow — patient intake → backend processing → structured result → safe report — that a reviewer can understand without knowing the internal pipeline.

**Key Deliverables (PR #19)**

* Next.js (pages router) application in `app/`
* `app/pages/index.tsx` — page states: idle, loading, success, validation error, failure; duplicate-submit guard
* `app/components/InputForm.tsx` — symptoms text, consent checkbox, client-side length checks matching backend intake rules
* `app/components/ReportView.tsx` — intake summary, report sections, safety note, emergency banner (only when the backend safety result requests it), non-diagnosis disclaimer
* `app/components/DeveloperTracePanel.tsx` — native `<details>`, collapsed by default, read-only: stage metrics, retrieval trace, safety trace, run ID, response JSON, Copy JSON
* `app/services/api.ts` — typed client for `POST /api/ingest`, user-safe error mapping, request timeout
* CORS allowlist (`CORS_ALLOWED_ORIGINS`) in `api/main.py` / `api/config.py`, with `tests/test_cors.py`
* `frontend` service in `docker-compose.yml` (multi-stage `app/Dockerfile`) and a root `.dockerignore`
* `/api/ingest` response contract unchanged

**User-Facing vs. Developer Output**

* The patient-facing view shows the intake summary, report, and safety/disclaimer text only
* Retrieval, safety, metrics, and raw JSON live in the developer panel
* Raw backend error detail is kept out of the main UI
* No browser controls for RAG, persistence, or LLM mode; these remain server configuration
* The browser receives only `NEXT_PUBLIC_API_BASE_URL`; no provider credentials

**Supporting Work — Issue #20 / PR #21 (Restore deterministic `/api/ingest` path)**

Issue #20 is **not** part of the Phase 3 issue range. It was opened when PR #19 integration testing showed that the merged UI could not get a successful response from the real backend:

* `OutputAgent` constructed an OpenAI client unconditionally, so every `/api/ingest` request without a key failed with a plain-text 500 that carried no CORS headers
* `OutputAgent.run()` returned the bare report, while the pipeline expected `{"report": ..., "_safety": ...}`, so the API returned `report: null` and a default safety result
* `AuditMiddleware` recorded handled HTTP errors as `success`

PR #21 fixed these with minimal changes:

* Deterministic mock mode for `OutputAgent`, selected by `LLM_MODE` (default `mock`), using the same safety guard and schema validation as real output
* One `{report, _safety}` contract between `OutputAgent` and `HealthcarePipeline`
* Safety guard applied to human-readable report fields only (a UUID identifier was being matched by the PHI phone pattern in about 10% of runs)
* `AuditMiddleware` records responses with status ≥ 400 as `failure`
* `tests/test_ingest_e2e.py` — unmocked FastAPI → real pipeline → real agents, with a stub that fails the test if the OpenAI client is called
* `tests/test_output_agent_mock.py`

**Validation**

* PR #19: 43 backend tests passed; frontend lint, typecheck, 23 vitest tests, and build clean
* PR #21: 56 backend tests passed; the new e2e tests fail against the previous code and pass with the fix
* Real browser E2E on `main` after PR #21: browser → Next.js → real `/api/ingest`, no OpenAI key; the intake summary and all five report sections rendered

**Design Notes**

* Docker Compose end-to-end, the dependency manifest, and PostgreSQL persistence were explicitly moved out of #16 into Issue #17
* Retrieval trace shows "not enabled" because RAG is not wired into the API pipeline

---

### Issue 17 — Local Runtime, Docker Compose & PostgreSQL Persistence

**Status:** Completed (PR #23, merge commit `6403878`)

**Objective**
Make the local application stack reproducible from a clean environment and make the existing PostgreSQL persistence path work.

> Issue #17 originally tracked Real LLM Provider Integration. That scope was moved unchanged to Issue #22 (Phase 4). #17 was re-scoped to the infrastructure and persistence findings from the #16 acceptance work.

**Confirmed Root Causes**

* `requirements.txt` was missing `jsonschema`, `sqlalchemy`, and `openai`; a clean Python 3.11 install failed on `import api.main`
* `HealthRecord.from_pipeline_trace` read a report structure that no longer exists, so every save failed before reaching the database
* Nothing created the `health_records` table
* The API container's default `DATABASE_URL` pointed at `localhost` (the container itself)
* `save_record` ran for failed runs and swallowed all exceptions

**Key Deliverables (PR #23)**

* `requirements.txt` completed; new `requirements-dev.txt` (pytest, httpx)
* `db/models.py` — `report_text` built from the five `report_sections`
* `db/migrate.py` — applies `db/migrations/*.sql` in order, tracked in `schema_migrations`
* `agents/pipeline.py` — persists successful runs only; `trace_id` = `run_id`; outcome reported in `trace["persistence"]` (`saved` / `duplicate` / `skipped` / `disabled` / `failed`); unexpected errors logged with a traceback
* `docker-compose.yml` — `api` builds `DATABASE_URL` from `POSTGRES_*` with host `db`; `db` healthcheck; `api` runs `python -m db.migrate` before uvicorn
* `api/config.py` / `.env.example` — consistent defaults; `LLM_MODE=mock` documented
* SQLite pipeline persistence regressions and `tests/test_persistence_postgres.py` (runs when `TEST_DATABASE_URL` is set)
* README startup instructions replaced with the verified procedure

**Validation**

* Fresh Python 3.11 venv: `pip install -r requirements.txt` then `import api.main` succeeded
* Backend: 64 passed, 3 skipped (PostgreSQL tests skip without `TEST_DATABASE_URL`); the PostgreSQL tests passed against the Compose database
* Frontend: 23 tests passed; image builds
* `docker compose build` / `up`: migration applied automatically; `api`, `frontend`, `db`, `redis` up
* Browser (Chrome) → Compose frontend → real `/api/ingest`, no OpenAI key: intake summary, all five report sections, and the developer trace (including the persistence outcome) rendered; a `health_records` row was saved
* Identical input submitted twice: second request returns 200 with a full report and `persistence.status = "duplicate"`
* JSON columns round-trip as `JSONB`; no credentials found in the frontend container
* The PR #23 record notes its Compose run used an existing local volume. The fresh-clone Compose startup (new volume, automatic migration) was run as part of the final close-out acceptance on `main`

**Design Notes**

* Persistence is best-effort: a database error never fails the patient's request, but the outcome is visible in the trace
* `build-essential` was left in the backend Dockerfile; it appears unnecessary, but removal was deferred rather than done blindly
* The duplicate key is a hash of the raw text only, so identical text from different patients is stored once (existing design, documented)

---

## 4. Architecture Progress After Phase 3

### Local Application Path

```
Browser (Next.js patient intake UI)
   → FastAPI POST /api/ingest
   → HealthcarePipeline (deterministic mock mode, no API key)
        IntakeAgent → StructuringAgent → OutputAgent → Safety Guard
   → Structured result + report  (patient-facing view)
   → Trace: metrics, safety, retrieval, run_id  (developer view)
   → PostgreSQL persistence (best-effort, outcome in trace)
   → Audit event (console / JSONL)
```

Retrieval exists in the pipeline but is not wired into the API, so the API path runs without RAG.

### Three Layers

**User-facing healthcare demo**

* Intake form with consent
* Structured intake summary and five-section report
* Safety note, emergency guidance banner, non-diagnosis disclaimer

**Developer / engineering diagnostics**

* Collapsible trace panel: stage latency, retrieval trace, safety trace, response JSON
* Per-run audit events
* Deterministic benchmark with structured scoring and latency aggregation

**Local infrastructure / runtime**

* Complete runtime dependency manifest
* Docker Compose: `api`, `frontend`, `db`, `redis`
* Automatic schema migration on API start
* PostgreSQL persistence with duplicate detection

### Running Locally

```
cp .env.example .env
docker compose up --build
# open http://localhost:3000
```

---

## 5. Phase 3 Acceptance Criteria

| Requirement                                                 | Status    |
| ----------------------------------------------------------- | --------- |
| Deterministic benchmark harness (RAG on/off)                | Completed |
| Field-level structured scoring                              | Completed |
| Per-run audit events (success and failure)                  | Completed |
| Stage-level latency metrics with mean / p50 / p95           | Completed |
| Browser intake → real `/api/ingest` → structured report     | Completed |
| Developer trace view, separated from patient-facing output  | Completed |
| `/api/ingest` works with no OpenAI key (mock mode)          | Completed |
| Clean Python 3.11 install from the declared manifest        | Completed |
| Docker Compose stack starts with automatic migration        | Completed |
| Successful ingest persisted to PostgreSQL                   | Completed |
| Duplicate input handled without failing the request         | Completed |
| No credentials exposed to the browser                       | Completed |

---

## 6. Known Limitations and Deferred Work

Phase 3 delivers a **local, deterministic demo**. It is not a production deployment, and it is not production healthcare software.

### Carried Forward

* **Real LLM provider integration** is not complete. It was moved from Issue #17 to Issue #22. All demo results come from deterministic mock agents.
* **Mock structuring output** returns placeholder values (e.g. empty symptom list, `"mock summary"`), and the UI shows them as-is.
* **RAG is not wired into the API**, and embeddings are deterministic placeholders without semantic meaning; retrieval quality is unmeasured.
* **Evaluation metrics are proxies**: they measure structure and consistency, not clinical correctness.
* **Raw intake text** is stored unmasked in `intake_json`, contrary to the model docstring. Not addressed in Phase 3.
* **Duplicate detection** keys on raw text only.
* **No CI pipeline** exists in the repository.
* Minor runtime items: `build-essential` in the backend image, obsolete Compose `version:` key.

### Not Part of Phase 3

* Authentication / staff RBAC
* Staff review queue
* Multi-clinic workflows
* Production patient data
* Full EHR integration
* Production deployment
* HIPAA compliance
* Voice / AI scribe workflows

---

## 7. Transition to Phase 4

| Phase   | Title                           | Issues     | Status    |
| ------- | ------------------------------- | ---------- | --------- |
| Phase 1 | Core Foundation                 | #1–#6      | Completed |
| Phase 2 | RAG + Safety + Persistence      | #7–#11     | Completed |
| Phase 3 | UI + Evaluation + Observability | #12–#17    | Completed |
| Phase 4 | To be defined                   | #22 onward | Next      |

Phase 4 begins with Issue #22 (Real LLM Provider Integration) and the remaining roadmap work following the documentation realignment in PR #18. Its full scope will be defined separately.

Phase 1 built the system spine. Phase 2 added grounding, safety, and memory. Phase 3 made the system measurable, observable, and runnable: a reviewer can start the local stack, submit an intake in a browser, read a safety-checked report, inspect the developer trace, and see the record in PostgreSQL — without an API key.
