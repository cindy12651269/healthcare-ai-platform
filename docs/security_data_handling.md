# Security & Data-Handling Notes

> Issue #34 (Phase 6). Describes the implementation as of the end of Phase 5 (#27–#33). This is the canonical security and data-handling document; it replaces the empty `compliance/*.md` stubs (BAA map, data flow, HIPAA overview, RBAC, threat model), which were removed in #26.
>
> **No compliance claim.** This system is not HIPAA compliant, has not been assessed against HIPAA or any other framework, and must not process real patient data. It runs on synthetic data only (roadmap §8).

---

## 1. Data flow

```
Browser (patient intake form, app/pages/index.tsx)
   │  POST /api/ingest  {text, consent_granted, source, input_type, user_id?}   — unauthenticated
   ▼
FastAPI (api/main.py) ── AuditMiddleware ──► audit event per request (path, status, latency)
   │
   ▼
HealthcarePipeline (agents/pipeline.py)
   intake → structuring → [retrieval] → output + safety guard → escalation decision
   │                                                         │
   │                                                         └─► pipeline audit event (run id, counts, reason codes)
   ▼
PostgreSQL  health_records  (clinic_id = "default", review_status)
   │
   ├─► Escalation webhook (api/webhook.py), only if review_status = needs_review
   │      signed payload: event, schema_version, idempotency_key, intake_id, clinic_id
   │      delivery log: webhook_deliveries
   │
   └─► Staff API (api/routers/records.py) ── bearer token + clinic membership ──► Staff Review UI (app/pages/staff.tsx)
          every successful call ──► staff audit event (actor_id, action, resource_id)
```

* Transport: the demo runs over plain HTTP locally. TLS termination is a deployment concern (#35) and is not provided by the application.
* CORS: explicit origin allowlist (`CORS_ALLOWED_ORIGINS`), no credentials, `GET`/`POST` only.
* LLM provider: in the default mock mode no data leaves the process. In real mode (`LLM_MODE=real`) the intake text is sent to the configured OpenAI API for structuring and report generation.

## 2. What is masked and what is stored

| Location | Contains raw intake text? | Notes |
| --- | --- | --- |
| `health_records.intake_json` | **Yes, unmasked** | The full `HealthInput` (`raw_text`, `user_id`, `contains_phi`, `consent_granted`, …) is persisted as-is. Not encrypted at the application level. Verified by `tests/test_audit_no_raw_text.py`. |
| `health_records.structured_output_json` | **Yes (partial)** | In mock mode `clinical_structuring.chief_complaint` is the first 200 characters of the raw text. |
| `health_records.safety_audit_json` | **Can** | Guard evidence (`reasons[].match`) holds the matched input fragment; `masked_text` is the masked report text. |
| `health_records.report_json` / `report_text` | Report text only | Rendered report text passes through the regex PHI masker (`llm/safety_guard.py`: SSN, email, phone, date, ID patterns). |
| `health_records.input_hash` | No | SHA-256 of the raw text, used for idempotency. An unsalted hash of short text is guessable; treat it as sensitive. |
| `/api/ingest` response (to the browser) | **Yes** | Returns the full pipeline trace, including `intake.raw_text`, `chief_complaint` and guard evidence. Known finding from #32, not fixed here. |
| Staff detail API (`GET …/intakes/{id}`) | Indirectly | Returns `structured`, `report` and `safety` (which can hold fragments, above); does **not** return `intake_json`. |
| Audit events (`audit.jsonl` + stdout) | **No** | Pipeline, API middleware and staff-action events carry ids, status, latency, counts, paths and reason codes only. Verified by `tests/test_audit_no_raw_text.py` (see §4). |
| Webhook payload | No | Allowlisted model (`EscalationPayload`, `extra="forbid"`): event, schema version, idempotency key, intake id, clinic id. |
| `webhook_deliveries` | No | Outcome metadata only: target as `scheme://host[:port]`, attempts, HTTP status, error class. Never the secret, signature or response body. |
| Application logs (`logging`) | **Can** | Not covered by the audit test. Some handlers log exception text (e.g. `Structuring failed: {e}`); the uvicorn access log records paths. |

Masking is applied to **generated report text**, not to stored input. The intake PHI check (`agents/intake_agent.py`) is a keyword heuristic used only as a consent gate; it does not redact anything. None of these heuristics is a validated de-identification method.

## 3. Access control

* Patient intake (`POST /api/ingest`) is unauthenticated and assigned to the seeded `default` clinic.
* Staff endpoints require an HMAC-SHA256 bearer token (`AUTH_TOKEN_SECRET`, ≥ 32 chars, default TTL 8 h) issued by an operator CLI (`python -m api.auth`). Clinic access is decided from database memberships on every request, never from client input; cross-clinic reads return 403/404 (see [`auth.md`](auth.md), [`review_queue_api.md`](review_queue_api.md)).
* The Staff Review UI keeps the token in memory only (no cookies or web storage).
* There is no token revocation list, no MFA, no rate limiting and no account lockout.

## 4. Audit logs

`observability/audit_logger.py` writes one JSON line per event to stdout and, when `ENABLE_AUDIT_JSONL=true` (default), to `AUDIT_LOG_PATH` (default `./audit.jsonl`, untracked). Producers:

| Producer | Fields beyond the common schema |
| --- | --- |
| Pipeline (`agents/pipeline.py`) | `run_id`, `flags.rag_enabled`, `flags.escalation_required`, `flags.escalation_reasons` (reason codes), `error` (exception message) |
| API middleware (`api/middleware/audit.py`) | `run_id="api_request"`, `flags.path`, `error` (`HTTP <status>` or exception message) |
| Staff actions (`api/routers/records.py`) | `actor_id`, `action` (`intake.list`/`read`/`transition`), `resource_id`, `flags.clinic_id`, filter / status fields |

`tests/test_audit_no_raw_text.py` runs each producer end to end (real pipeline in mock mode, real FastAPI app, real `log_run` writing the JSONL file) with a synthetic sentinel token in the intake text, including an escalated intake and a rejected (no-consent) intake, and asserts the token appears in no audit line while it **is** present in the stored `intake_json`. It runs in the existing `Backend tests` CI job.

Limits of that guarantee: the `error` fields carry exception messages. Current intake, structuring and HTTP errors do not echo input, but a future exception that interpolates input (or a real-provider error message) could. The audit file is append-only by convention only: no integrity protection, rotation or retention policy.

## 5. Threat model summary

| Threat | Current mitigation | Gap |
| --- | --- | --- |
| Cross-clinic data access | Server-side membership checks; queries filter on authorized clinic; tested | Single shared intake clinic for unauthenticated submissions |
| Stolen staff token | Signed, expiring tokens; memberships re-read per request | No revocation, no MFA, bearer token usable until expiry |
| Database compromise / backup leak | None at application level | Raw intake text stored unmasked; no field-level encryption |
| PHI in logs | Audit events exclude intake text (tested) | Application/exception logs not covered; no log redaction filter |
| PHI returned to browser | Patient sees only their own submission | `/api/ingest` returns raw text and guard evidence (#32 finding) |
| PHI to third parties | Webhook payload allowlisted and signed; mock mode sends nothing out | Real LLM mode sends intake text to the provider |
| Webhook spoofing / replay | HMAC-SHA256 signature, idempotency key | Receiver must verify; no timestamp in signed payload |
| Abuse of public intake | Length limits, consent gate | No rate limiting or bot protection (roadmap §7) |
| Prompt injection / unsafe output | Deterministic output guard, escalation to human review | Rule-based; measured only on a small synthetic set (#32) |
| Secrets exposure | Environment-managed, server-only (`AUTH_TOKEN_SECRET`, `WEBHOOK_SECRET`, `OPENAI_API_KEY`) | No secret manager or rotation procedure |

## 6. What HIPAA compliance would require (not done)

This list is indicative, not legal advice, and is not a gap assessment. Work that a real deployment handling PHI would need, at minimum:

* **Administrative:** a designated security/privacy owner, documented risk analysis, policies, workforce training, incident response and breach notification procedures.
* **Business Associate Agreements** with every vendor that handles PHI (hosting, database, LLM provider, webhook receivers, log storage).
* **Encryption** in transit (TLS everywhere) and at rest (database, backups, logs), with key management; consider application-level encryption of `raw_text` (roadmap §7).
* **Data minimization:** stop returning raw text and guard evidence from `/api/ingest`; decide whether `raw_text` must be stored at all; salt or drop `input_hash`.
* **Access control:** unique user identities with MFA, token revocation, least-privilege roles, automatic logoff, emergency access procedure.
* **Audit controls:** tamper-evident, centrally retained audit logs (including read access, which staff events already record), log redaction for application logs, regular review.
* **Integrity and availability:** backups, tested restore, retention and disposal policy, rate limiting and monitoring.
* **De-identification:** if de-identified data is claimed, a validated method (Safe Harbor or Expert Determination) instead of the current regex/keyword heuristics.
* **Independent assessment** before any compliance statement is made.

None of the above is implemented beyond what §§3–4 describe, and no "HIPAA compliant" label is used anywhere in this project.
