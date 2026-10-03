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
pip install -r requirements.txt   # note: manifest is incomplete; fixed in Phase 3
pytest
```

## Running the patient intake demo UI

The Next.js intake UI (`app/`) submits to the FastAPI `POST /api/ingest` endpoint. Pipeline settings (RAG, persistence, LLM mode) are backend configuration and are not exposed in the browser.

```bash
# 1. Backend (port 8000). Allowed browser origins: CORS_ALLOWED_ORIGINS (default http://localhost:3000,http://127.0.0.1:3000)
uvicorn api.main:app --port 8000

# 2. Frontend (port 3000). NEXT_PUBLIC_API_BASE_URL defaults to http://localhost:8000
cd app
npm install
npm run dev        # open http://localhost:3000
```

Or with Docker Compose: `docker compose up --build` starts `api`, `frontend` (http://localhost:3000), `db` and `redis`. Compose reads a root `.env` (copy `.env.example`).

Frontend checks: `cd app && npm run lint && npm run typecheck && npm test && npm run build`.

**Known limitation:** `/api/ingest` does not yet complete without an OpenAI key. Report generation always calls OpenAI, so without a key every request returns HTTP 500, and the UI shows its service-failure state. A deterministic no-key path is separate Phase 3 work (see [`docs/step3_roadmap.md`](docs/step3_roadmap.md)).

A full README (setup, demo walkthrough, architecture diagram) is part of Phase 4.
