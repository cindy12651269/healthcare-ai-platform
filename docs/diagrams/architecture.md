# Architecture Diagram

Implemented system at the end of Phase 6 (#34, #35). Solid arrows are active request paths; dashed arrows are code that exists but is not on the API's runtime path, or is optional configuration. Sources are named on each node.

```mermaid
flowchart LR
    subgraph Browser["Browser — Next.js (app/)"]
        P["Patient intake<br/>pages/index.tsx"]
        S["Staff review<br/>pages/staff.tsx<br/>token kept in memory"]
    end

    subgraph API["FastAPI (api/main.py) — CORS allowlist, AuditMiddleware"]
        ING["POST /api/ingest<br/>unauthenticated<br/>returns full pipeline trace"]
        AUTH["Bearer token + clinic role<br/>api/auth.py"]
        REC["Review queue<br/>GET intakes · GET intake · POST transition<br/>api/routers/records.py"]
        H["GET /health<br/>reports llm_mode"]
    end

    subgraph Pipeline["HealthcarePipeline (agents/pipeline.py)"]
        I["Intake + consent gate<br/>intake_agent.py"]
        ST["Structuring<br/>structuring_agent.py"]
        R["Retrieval / RAG<br/>retrieval_agent.py, rag/<br/>hash-based mock embeddings"]
        O["Report + safety guard<br/>output_agent.py, llm/safety_guard.py"]
        E["Escalation rules<br/>agents/escalation.py"]
    end

    LLM{{"LLM provider (llm/provider.py)<br/>mock (default, deterministic)<br/>real = OpenAI, opt-in"}}
    DB[("PostgreSQL<br/>health_records · clinics · users<br/>clinic_memberships · webhook_deliveries<br/>migrations: db/migrate.py")]
    WH["Signed webhook (api/webhook.py)<br/>HMAC-SHA256, idempotency key,<br/>bounded retries"]
    RCV["External receiver"]
    AUD["Audit events<br/>stdout + audit.jsonl<br/>no intake text"]

    P -->|intake text| ING --> I --> ST --> O --> E
    ST -.-> LLM
    O -.-> LLM
    ST -. "not wired into the API pipeline;<br/>benchmark --rag on only" .-> R -.-> O
    E -->|"record, clinic 'default',<br/>review_status + reason codes"| DB
    E -->|"only if newly saved<br/>and needs_review"| WH -->|"ids only"| RCV
    WH -->|delivery log| DB
    S -->|Authorization: Bearer| AUTH --> REC <-->|clinic-filtered queries| DB
    API -.-> AUD
    Pipeline -.-> AUD
```

Notes (each checked against the code):

* `api/deps.py` builds `HealthcarePipeline()` without a `RetrievalAgent`, so `/api/ingest` traces show `rag.enabled: false`.
* Persistence and the webhook are best-effort: a database or delivery problem never fails `/api/ingest` (`agents/pipeline.py`, `api/webhook.py`).
* The webhook payload is `event`, `schema_version`, `idempotency_key`, `intake_id`, `clinic_id` (`EscalationPayload`, `extra="forbid"`).
* Clinic access is decided from database memberships on every request; another clinic's intake reads as 403 (other clinic's path) or 404 (own path).
* Redis in `docker-compose.yml` is unused and not deployed.
* Hosted deployment (`render.yaml`): API and frontend as Docker web services, PostgreSQL managed by Render ([`../deployment.md`](../deployment.md)).
