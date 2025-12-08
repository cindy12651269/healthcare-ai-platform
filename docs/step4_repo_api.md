# Step 4 — Repository & API Documentation

Healthcare AI Platform — Repository Structure and API Specification

This document describes how the repository is organized and how the backend API (FastAPI) is structured, implemented, and used. It provides a complete reference for developers, reviewers, and potential clients evaluating the system.

---

## 1. Repository Overview

The project follows a modular architecture designed for clarity, scalability, and portfolio readability.

```
healthcare-ai-platform/
├── agents/                # Core LLM-driven agents and pipeline
├── api/                   # FastAPI service (endpoints, dependencies, config)
├── app/                   # Frontend demo UI
├── llm/                   # Prompts, schemas, safety guard
├── rag/                   # Retrieval and vector storage (Week 2+)
├── db/                    # Database models and migrations
├── interoperability/      # FHIR, HL7, EHR routing modules
├── observability/         # Audit logs, metrics, tracing
├── infra/                 # AWS, IaC, Docker service config
├── docs/                  # Architecture, product, roadmap, demo docs
├── tests/                 # Automated tests (agents, pipeline, API)
├── Makefile               # Developer automation
├── docker-compose.yml     # Local runtime stack (API + Postgres + Redis)
└── requirements.txt
```

Each folder represents a functional boundary within the system. Backend execution centers on the **agents**, **pipeline**, and **api** layers.

---

## 2. FastAPI Service Architecture (`api/`)

The API layer exposes the healthcare pipeline to external clients.

### 2.1 Key Files

| File                    | Purpose                                                             |
| ----------------------- | ------------------------------------------------------------------- |
| `api/main.py`           | FastAPI initialization, router registration, lifecycle events       |
| `api/routers/ingest.py` | Defines `/api/ingest` endpoint and request/response models          |
| `api/deps.py`           | Dependency injection (pipeline, DB session, future auth middleware) |
| `api/config.py`         | Centralized environment configuration (Pydantic-based)              |
| `api/middleware/`       | Reserved for audit, authentication, rate-limiting                   |

---

## 3. API Initialization (`api/main.py`)

The main API entry point configures logging, registers routers, and provides basic system introspection.

### Responsibilities

* Initialize the FastAPI application
* Load environment config (`get_settings()`)
* Register routers (`ingest`)
* Provide `/health` and `/` endpoints
* Log startup and shutdown events

### Simplified Structure

```python
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
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

## 4. Ingest Endpoint (`/api/ingest`)

This is the core API entrypoint for the healthcare AI pipeline.

### 4.1 Request Schema

Defined using Pydantic:

```python
class IngestRequest(BaseModel):
    text: str
    source: Optional[str] = "web"
    input_type: Optional[str] = "chat"
    consent_granted: Optional[bool] = False
    user_id: Optional[str] = None
```

### 4.2 Response Schema

```python
class IngestResponse(BaseModel):
    success: bool
    intake: Optional[Dict[str, Any]]
    structured: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    errors: List[Dict[str, Any]]
```

### 4.3 Endpoint Logic

Core logic inside `ingest.py`:

```python
@router.post("/ingest")
def ingest(payload: IngestRequest, pipeline: HealthcarePipeline = Depends(get_pipeline)):
    trace = pipeline.run(
        raw_text=payload.text,
        meta={
            "source": payload.source,
            "input_type": payload.input_type,
            "consent_granted": payload.consent_granted,
            "user_id": payload.user_id,
        },
    )
    return trace
```

### 4.4 Error Handling

Mapped to consistent HTTP responses:

| Error                 | HTTP Code |
| --------------------- | --------- |
| Missing field / type  | 422       |
| IntakeValidationError | 400       |
| StructuringError      | 422       |
| Unexpected error      | 500       |

This aligns with the **unified error model** documented in step5.

---

## 5. Pipeline Integration (`agents/pipeline.py`)

The API never talks directly to LLMs or validators.
Instead, requests are forwarded to `HealthcarePipeline`.

### Pipeline Responsibilities

* Run Intake → Structuring → Output agents in order
* Capture intermediate data for debugging
* Catch and re-throw domain-specific exceptions
* Produce final structured trace for API output

### Output Structure

Example trace:

```json
{
  "success": true,
  "intake": {...},
  "structured": {...},
  "report": {...},
  "errors": []
}
```

This design keeps the API thin, secure, and maintainable.

---

## 6. Environment & Configuration (`api/config.py`)

Environment variables (DB, Redis, API keys) are stored in:

```
.env
.env.example
```

`get_settings()` loads configuration via Pydantic for reliability:

```python
class Settings(BaseSettings):
    app_name: str = "Healthcare AI Platform"
    app_env: str = "local"
    openai_api_key: str | None = None
```

This ensures:

* central config management
* multiple environments (local, dev, prod)
* reproducibility

---

## 7. Local Development Stack

Local environment is fully containerized.

### 7.1 Makefile

Key commands:

| Command      | Description                  |
| ------------ | ---------------------------- |
| `make up`    | Start API + Postgres + Redis |
| `make down`  | Stop stack                   |
| `make logs`  | Tail API logs                |
| `make build` | Build services               |

### 7.2 docker-compose.yml

Starts three services:

```
api → FastAPI backend
postgres → structured data persistence
redis → caching / async tasks (future)
```

Ports:

* API: `8000:8000`
* Postgres: `5432:5432`
* Redis: `6379:6379`

This environment ensures the project runs identically on any machine.

---

## 8. Deployment Considerations

Although Week 1 only covers local execution, the repo is structured for production:

* `infra/aws/` contains Terraform examples
* Observability hooks exist for metrics + audit logs
* API supports adding auth middleware easily
* Modular architecture supports scaling agents independently

This section becomes important for Upwork clients looking for **HIPAA-aligned**, **AWS-ready**, or **scalable SaaS** backend designs.

---

## 9. Summary

`docs/step4_repo_api.md` provides a comprehensive overview of:

* how the repo is structured
* how API requests are handled
* how the ingest endpoint integrates with the agent pipeline
* how configuration, Docker, and Makefile make the system reproducible

This document completes **Step 4** of the project blueprint and ensures technical reviewers can understand the backend at a glance.
