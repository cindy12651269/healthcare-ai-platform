# Step 4 — Repository & API Documentation (Updated After Phase 2)

Healthcare AI Platform — Repository Structure and API Specification

This document reflects the **current repository structure and API behavior after Phase 2 (RAG, Safety, Persistence)**.

It serves as a technical reference for:

* Developers contributing to the codebase
* Reviewers evaluating backend quality
* Clients assessing healthcare AI readiness

---

# 1. Repository Overview

The project follows a modular, layered architecture designed for clarity, testability, and healthcare SaaS extensibility.

```
healthcare-ai-platform/
├── agents/                # Core agents and HealthcarePipeline
├── api/                   # FastAPI service (routes, config, deps)
├── app/                   # Frontend demo UI
├── llm/                   # Prompts, schemas, safety guard
├── rag/                   # Deterministic RAG + vector store abstraction
├── db/                    # ORM models, migrations, session management
├── interoperability/      # FHIR, HL7, consent, EHR routing (Phase 4)
├── observability/         # Audit, tracing, metrics hooks (Phase 3+)
├── infra/                 # Docker, AWS/IaC examples
├── docs/                  # Architecture, roadmap, API, journals
├── tests/                 # Unit & integration tests
├── Makefile               # Developer automation
├── docker-compose.yml     # Local runtime stack (API + Postgres + Redis)
└── requirements.txt
```

Backend execution centers on:

* `agents/`
* `api/`
* `rag/`
* `llm/`
* `db/`

---

# 2. FastAPI Service Architecture (`api/`)

The API layer exposes the HealthcarePipeline to external clients while remaining thin and secure.

## 2.1 Key Files

| File                    | Purpose                                                       |
| ----------------------- | ------------------------------------------------------------- |
| `api/main.py`           | FastAPI initialization, router registration, lifecycle events |
| `api/routers/ingest.py` | Defines `/api/ingest` endpoint and request/response models    |
| `api/deps.py`           | Dependency injection (pipeline, DB session, runtime flags)    |
| `api/config.py`         | Centralized environment configuration (Pydantic-based)        |
| `api/middleware/`       | Reserved for auth, audit, rate-limiting                       |

---

# 3. API Initialization (`api/main.py`)

## Responsibilities

* Initialize FastAPI application
* Load environment config via `get_settings()`
* Register routers
* Provide `/health` endpoint
* Log startup and shutdown events

### Simplified Initialization

```python
app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
```

### Health Endpoint

```python
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
```

---

# 4. Ingest Endpoint (`POST /api/ingest`)

This is the primary API entrypoint for healthcare AI processing.

## 4.1 Request Schema

```python
class IngestRequest(BaseModel):
    text: str
    source: Optional[str] = "web"
    input_type: Optional[str] = "chat"
    consent_granted: Optional[bool] = False
    user_id: Optional[str] = None
```

## 4.2 Response Schema (Phase 2 Updated)

```python
class IngestResponse(BaseModel):
    success: bool
    intake: Optional[Dict[str, Any]]
    structured: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    retrieval_trace: Optional[List[Dict[str, Any]]] = None
    safety_trace: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, Any]]
```

### Field Notes

* `retrieval_trace` is present when RAG is enabled.
* `safety_trace` contains deterministic safety enforcement results.
* `errors` contains structured domain errors.

---

## 4.3 Endpoint Logic

```python
@router.post("/ingest")
def ingest(
    payload: IngestRequest,
    pipeline: HealthcarePipeline = Depends(get_pipeline),
):
    result = pipeline.run(
        raw_text=payload.text,
        meta={
            "source": payload.source,
            "input_type": payload.input_type,
            "consent_granted": payload.consent_granted,
            "user_id": payload.user_id,
        },
    )
    return result
```

The API layer:

* Does not call LLMs directly
* Does not apply business logic
* Delegates all execution to `HealthcarePipeline`

---

# 5. Pipeline Integration (`agents/pipeline.py`)

The API interacts exclusively with `HealthcarePipeline`.

## 5.1 Current Phase 2 Execution Flow

```text
Raw Input
   → IntakeAgent
   → StructuringAgent
   → RetrievalAgent (optional)
   → OutputAgent
   → Safety Guard
   → Persistence (optional)
```

## 5.2 Responsibilities

The pipeline:

* Coordinates agent execution order
* Applies feature flags (RAG, persistence)
* Attaches retrieval trace
* Attaches safety trace
* Handles domain-level exceptions
* Returns structured response object

---

# 6. Runtime Feature Flags

Pipeline execution supports configuration toggles:

* `enable_rag`
* `enable_persistence`

These are injected via dependency layer or environment configuration.

This enables:

* Deterministic CI mode
* A/B evaluation
* Controlled rollout of features

---

# 7. Deterministic Safety Enforcement

All outputs pass through a deterministic safety guard before returning to clients.

Safety includes:

* PHI masking
* No-diagnosis enforcement
* No-prescription enforcement
* Crisis detection

No unsafe content is returned directly to API consumers.

---

# 8. Persistence Behavior

When persistence is enabled:

* Structured output and report are stored via `HealthRecord`
* Idempotency enforced using `input_hash`
* Transactions handled via `save_record()` helper

Encryption at rest is assumed at infrastructure level (managed Postgres).

---

# 9. Error Handling

| Error Type            | HTTP Code |
| --------------------- | --------- |
| Validation error      | 422       |
| IntakeValidationError | 400       |
| StructuringError      | 422       |
| SafetyViolation       | 422       |
| Unexpected error      | 500       |

Errors are returned in structured format under `errors` field.

---

# 10. Local Development Stack

## 10.1 Makefile

| Command      | Description                  |
| ------------ | ---------------------------- |
| `make up`    | Start API + Postgres + Redis |
| `make down`  | Stop stack                   |
| `make logs`  | Tail API logs                |
| `make build` | Build services               |

## 10.2 docker-compose.yml

Services:

* API (FastAPI)
* PostgreSQL
* Redis (reserved for async/caching)

Ports:

* API → `8000`
* Postgres → `5432`
* Redis → `6379`

---

# 11. Deployment Readiness

Repository is structured for future production use:

* Terraform examples in `infra/`
* Pluggable LLM provider interface
* Deterministic CI-safe mode
* Modular agents
* Extensible API design

---

# 12. Architectural Status After Phase 2

The API now exposes a healthcare AI backend that is:

* RAG-capable (deterministic mode)
* Safety-enforced
* Persistence-enabled
* Feature-toggle controlled
* Schema-validated end-to-end

The API contract reflects retrieval and safety traces and is ready for Phase 3 evaluation expansion.

---

**Document Status:** Updated after Phase 2 completion
Future revisions will incorporate Phase 3 evaluation endpoints and Phase 4 interoperability expansion.
