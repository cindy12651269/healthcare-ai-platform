# Healthcare AI Platform

AI-assisted pre-visit symptom intake for an outpatient clinic: free-text patient input is validated, structured against a schema, summarised without diagnosis, checked by deterministic safety rules, and, when flagged, routed to the right clinic's staff for human review, with a signed notification to an external system.

> **Portfolio demo, not a medical device and not production software.** Synthetic data only. It gives no medical advice, makes **no HIPAA compliance claim**, and must not process real patient data ([`docs/security_data_handling.md`](docs/security_data_handling.md)).

**Status:** Phases 1–5 complete; Phase 6 (security notes #34, hosted deployment #35) complete, portfolio handover (#36) in review. Evidence per capability: [`docs/project_status.md`](docs/project_status.md).

## Hosted demo

| | URL |
| --- | --- |
| Patient intake UI | https://healthcare-ai-frontend-1s23.onrender.com |
| Staff review UI | https://healthcare-ai-frontend-1s23.onrender.com/staff (needs an operator-issued token) |
| API health | https://healthcare-ai-api-tovn.onrender.com/health |

Render free plans: services sleep after ~15 minutes idle (first request can take about a minute) and the free database expires 30 days after creation. Step-by-step walkthrough: [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md). Deployment procedure and verification evidence: [`docs/deployment.md`](docs/deployment.md).

## What is implemented

| Area | Implemented | Not implemented |
| --- | --- | --- |
| Intake pipeline | Validation and consent gate, schema-validated structuring, non-diagnostic report, deterministic safety guard (diagnosis/prescription blocking, report PHI masking, emergency guidance) | Validated de-identification |
| LLM | `LLM_MODE=mock` (default, deterministic, no key); `LLM_MODE=real` (OpenAI, opt-in, no fallback to mock) | Real mode is never run in CI |
| Retrieval (RAG) | Retrieval agent and in-memory vector store, exercised by tests and the benchmark (`--rag on`) | **Not wired into the API**; embeddings are hash-based mocks with no semantic meaning |
| Human review | Escalation rules → `needs_review` with reason codes; clinic-scoped review-queue API; staff UI at `/staff` | Per-clinic intake routing (all public intakes go to clinic `default`) |
| Access control | HMAC bearer tokens from an operator CLI; `clinic_staff` / `clinic_admin` roles re-checked per request; cross-clinic denial tested | Login/SSO, MFA, token revocation list |
| Integration | HMAC-SHA256-signed escalation webhook with idempotency key, bounded retries and a delivery log | Delivery guarantee, per-clinic receivers |
| Data | PostgreSQL with ordered SQL migrations; audit events without intake text (tested) | Encryption of stored intake text (stored unmasked) |
| Delivery | CI (backend + PostgreSQL, benchmark, frontend); one hosted demo on Render | Multiple environments, autoscaling, rate limiting |

Known exposure: `/api/ingest` returns the full pipeline trace, including the raw intake text, to the submitting browser (documented #32 finding).

## Architecture

```
Browser (Next.js) ──POST /api/ingest──► FastAPI ──► pipeline: intake → structuring → report + safety guard → escalation
      │                                                                                   │
      └── /staff ── bearer token ──► review-queue API ◄── PostgreSQL (health_records) ◄──┘──► signed webhook
```

Full diagram: [`docs/diagrams/architecture.md`](docs/diagrams/architecture.md). Design decisions: [`docs/decisions.md`](docs/decisions.md). API: [`docs/step4_repo_api.md`](docs/step4_repo_api.md), [`docs/review_queue_api.md`](docs/review_queue_api.md), [`docs/auth.md`](docs/auth.md). Data model: [`docs/data_model.md`](docs/data_model.md). Webhook: [`docs/escalation_webhook.md`](docs/escalation_webhook.md).

## Running locally

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build    # api :8000, frontend http://localhost:3000, db (PostgreSQL 15), redis (unused)
```

The `api` container waits for `db`, applies pending migrations (`python -m db.migrate`), then starts uvicorn. Each successful `/api/ingest` run is stored in `health_records`; the response's `persistence` field reports `saved`, `duplicate` (identical text is stored once), `skipped`, `disabled` or `failed`. Persistence is best-effort and never fails the request.

Staff access needs `AUTH_TOKEN_SECRET` (≥ 32 characters) in `.env`, a user and a token:

```bash
python -m api.auth create-user --email admin@clinic.test --clinic default --role clinic_admin
python -m api.auth issue-token --user-id <printed id>
```

The hosted demo seeds synthetic users instead (`python -m db.seed_demo`, [`docs/deployment.md`](docs/deployment.md) §2).

### Without Docker

```bash
uvicorn api.main:app --port 8000          # CORS_ALLOWED_ORIGINS defaults to http://localhost:3000
cd app && npm install && npm run dev      # http://localhost:3000; NEXT_PUBLIC_API_BASE_URL defaults to http://localhost:8000
```

For persistence, start Postgres with `docker compose up -d db` and run `python -m db.migrate` first.

### LLM mode

`LLM_MODE=mock` (default) is deterministic and offline. `LLM_MODE=real` calls OpenAI with `OPENAI_API_KEY` (server-side only); the API refuses to start without a key, and provider failures return controlled errors (502/503/422) with no fallback to mock. `GET /health` reports the mode. Secrets are never placed in `NEXT_PUBLIC_` variables.

## Testing

```bash
pip install -r requirements-dev.txt   # Python 3.11
pytest                                # PostgreSQL tests run when TEST_DATABASE_URL is set, otherwise skipped
python -m evaluation.benchmark --mode mock --rag off      # also: --rag on, --suite safety
cd app && npm run lint && npm run typecheck && npm test && npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs on every PR and push to `main` with `LLM_MODE=mock` and no secrets: backend tests against a `postgres:15` service (the job fails if the PostgreSQL tests are skipped), the deterministic benchmark and safety suite, and frontend lint/typecheck/tests/build. Mock-mode scores measure contract stability, not model quality ([`docs/evaluation_benchmark.md`](docs/evaluation_benchmark.md)).

## Limitations

* Not production software and no compliance claim; synthetic data only.
* Raw intake text is stored unmasked and returned in the `/api/ingest` response.
* Safety and PHI handling are rule-based heuristics, measured only on a small synthetic set.
* RAG is not active through the API, and mock embeddings carry no meaning.
* Free-tier hosting: cold starts, a 30-day database, ephemeral audit file (events remain in platform logs).
* No rate limiting, login flow, MFA or token revocation.

Full list: [`docs/project_status.md`](docs/project_status.md) and [`docs/security_data_handling.md`](docs/security_data_handling.md).

## Scope and contribution

Personal portfolio project. All commits in this repository are authored by Cindy Lin (first commit 2025-11-30), who defined the product scope, roadmap and phase acceptance criteria and reviewed and merged every PR. Implementation used AI coding assistance (Claude Code); 29 of the 80 commits at the start of Phase 6 handover carry a `Co-Authored-By: Claude` trailer. There is no client, employer or team behind this work, and no real users or patient data. Work was tracked as GitHub Issues and delivered as Issue → branch → tests → PR → review → merge → journal ([`docs/project_journal/`](docs/project_journal/)).

Roadmap and remaining scope: [`docs/step3_roadmap.md`](docs/step3_roadmap.md).
