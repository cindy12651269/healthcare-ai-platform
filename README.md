# Healthcare AI Platform

AI-assisted pre-visit symptom intake for an outpatient clinic: free-text patient input is validated, structured against a schema, summarised without diagnosis, checked by deterministic safety rules, and (planned) routed to clinic staff for human review.

**Status:** in development — Phases 1–2 complete, Phase 3 in progress. Synthetic data only; no medical advice; no HIPAA compliance claim.

* What works today, with evidence: [`docs/project_status.md`](docs/project_status.md)
* Product and architecture overview: [`docs/overview.md`](docs/overview.md)
* Roadmap and remaining scope: [`docs/step3_roadmap.md`](docs/step3_roadmap.md)
* Completed phase records: [`docs/project_journal/`](docs/project_journal/)

Work is tracked in GitHub Issues and Projects and delivered as Issue → branch → tests → PR → review → merge → journal.

## Running tests

```bash
pip install -r requirements-dev.txt   # runtime (requirements.txt) + pytest/httpx; Python 3.11
pytest
```

`tests/test_persistence_postgres.py` runs only when `TEST_DATABASE_URL` points at a PostgreSQL database (for example the Compose `db` service: `postgresql+psycopg2://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:5432/<POSTGRES_DB>`); otherwise it is skipped.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request to `main` and every push to `main`:

- **Backend:** Python 3.11, `pytest` (full suite) against a `postgres:15` service container with `TEST_DATABASE_URL` set, so the PostgreSQL integration tests execute; the job fails if they are skipped.
- **Benchmark:** `python -m evaluation.benchmark --mode mock` with `--rag off` and `--rag on` (deterministic).
- **Frontend (`app/`):** `npm ci`, then `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` (Node 22).

CI sets `LLM_MODE=mock` and needs no secrets: no OpenAI or other provider credentials are used, and no real LLM call is made. Real-provider runs (`--mode real`) are intentionally excluded from default CI.

## Running the patient intake demo UI

The Next.js intake UI (`app/`) submits to the FastAPI `POST /api/ingest` endpoint. Pipeline settings (RAG, persistence, LLM mode) are backend configuration and are not exposed in the browser.

The default `LLM_MODE=mock` runs the deterministic pipeline and needs no OpenAI API key. `LLM_MODE=real` calls OpenAI with `OPENAI_API_KEY` (real-provider hardening is tracked separately). The key is only read by the backend; the browser only receives `NEXT_PUBLIC_API_BASE_URL`.

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build    # api :8000, frontend http://localhost:3000, db (PostgreSQL 15), redis
```

On start, the `api` container waits for `db` to be healthy, applies pending SQL migrations from `db/migrations/` (`python -m db.migrate`, recorded in `schema_migrations`; works on a new or an existing volume), then starts uvicorn. Inside Compose the API connects to Postgres through the `db` service (`DATABASE_URL` is set in `docker-compose.yml` from the `POSTGRES_*` values).

Each successful `/api/ingest` run is stored as one row in `health_records`, and the response's `persistence` field reports the outcome (`saved`, `duplicate`, `skipped`, `disabled`, `failed`). Persistence is best-effort: a database error does not fail the request, but it is logged and reported as `failed`. Rows are unique per input text (`input_hash`), so submitting identical text again returns `duplicate` and is not stored twice.

### Without Docker

```bash
# 1. Backend (port 8000). Allowed browser origins: CORS_ALLOWED_ORIGINS (default http://localhost:3000,http://127.0.0.1:3000)
uvicorn api.main:app --port 8000

# 2. Frontend (port 3000). NEXT_PUBLIC_API_BASE_URL defaults to http://localhost:8000
cd app
npm install
npm run dev        # open http://localhost:3000
```

For persistence in this mode, start Postgres with `docker compose up -d db`, then run `python -m db.migrate` before uvicorn; `.env.example`'s `DATABASE_URL` targets the published `localhost:5432` port.

### LLM mode (mock / real)

`LLM_MODE` in `.env` selects the execution mode for `StructuringAgent` and `OutputAgent` (shared provider interface in `llm/provider.py`, OpenAI wrapper in `llm/providers/openai_client.py`):

- `mock` (default): deterministic, offline, no API key. Used by all tests and CI.
- `real`: OpenAI with `OPENAI_API_KEY` (server-side only). The API refuses to start without a key; provider timeouts, failures and malformed output return a controlled error (HTTP 502). There is no fallback to mock.
- Any other value fails at startup.

Both modes go through the same `structured_output.json` / `report_output.json` validation. `GET /health` reports `llm_mode`, and the UI shows it read-only (`LLM Mode: Mock` / `LLM Mode: Real`).

Benchmark: `python evaluation/benchmark.py --mode mock` (deterministic) or `python evaluation/benchmark.py --mode real --limit 1` (opt-in, needs `OPENAI_API_KEY`, never run in CI; output in `evaluation/results/benchmark_results_real.json`, not committed).

Frontend checks: `cd app && npm run lint && npm run typecheck && npm test && npm run build`.

A full README (setup, demo walkthrough, architecture diagram) is part of Phase 4.
