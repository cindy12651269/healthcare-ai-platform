# Escalation Notification Webhook (Issue #33)

When an intake is persisted with `review_status = needs_review` by the escalation rules (#29), the API sends **one logical notification** to a single configured receiver. The notification is an HMAC-SHA256-signed JSON payload with a stable idempotency key. Failed sends are retried a bounded number of times, and every outcome is written to a delivery log.

Code: `api/webhook.py` (payload, signing, delivery), the hook in `agents/pipeline.py` that runs after persistence, the `WebhookDelivery` model in `db/models.py`, and `db/migrations/003_webhook_deliveries.sql`. Tests: `tests/test_webhook.py`.

## Configuration (server-side only)

| Variable | Default | Meaning |
| --- | --- | --- |
| `WEBHOOK_URL` | unset | Receiver URL (`http` or `https`; use `https` outside local testing). |
| `WEBHOOK_SECRET` | unset | HMAC signing key, at least 32 characters, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit it or put it in a `NEXT_PUBLIC_` variable. |
| `WEBHOOK_TIMEOUT_SECONDS` | `3` | Timeout per attempt (maximum 10). |
| `WEBHOOK_MAX_ATTEMPTS` | `3` | Total attempts, including the first (1–5). |
| `WEBHOOK_RETRY_BACKOFF_SECONDS` | `0.5` | Base delay. The wait after attempt *n* is `base × 2^(n-1)`, so 0.5 s and then 1 s. |

**Disabled or unconfigured.** If either `WEBHOOK_URL` or `WEBHOOK_SECRET` is missing, the secret is shorter than 32 characters, or the URL is not http(s), no notification is sent and no delivery row is written. A partial or invalid configuration logs a warning. Nothing is ever sent unsigned. `/api/ingest`, persistence and escalation behave exactly as before. This is the default for local, mock-mode and CI runs.

## Trigger

- The hook runs only when persistence returns `saved`, meaning a new `health_records` row was committed.
- The notifier then re-reads that row and sends only if the **stored** `review_status` is `needs_review`. The trigger is therefore the persisted escalation decision, never client input.
- All escalation reasons qualify: `emergency_signal`, `blocked_diagnosis`, `blocked_prescription` and `low_confidence`.
- An intake with several reasons gets one notification.
- No notification is sent in these cases:
  - a normal (`submitted`) intake;
  - a duplicate submission, where existing `input_hash` deduplication stores no new record;
  - when persistence is disabled.

## Payload

The payload is built field by field from the stored record (`EscalationPayload`, with `extra="forbid"`):

```json
{"clinic_id":"default","event":"intake.escalated","idempotency_key":"intake.escalated:<intake_id>","intake_id":"<intake_id>","schema_version":1}
```

| Field | Value |
| --- | --- |
| `event` | Always `intake.escalated`. |
| `schema_version` | Always `1`. |
| `idempotency_key` | `intake.escalated:<intake_id>`. |
| `intake_id` | The opaque `health_records.id`. |
| `clinic_id` | The owning clinic, for routing. |

**PHI exclusions.** The payload never contains the intake text, structured output (`chief_complaint`, summary, symptoms), the report, safety results or guard evidence (including the raw `match` values found in #32), escalation reason codes, timestamps, patient identifiers or any other trace field. The pipeline trace is never serialized into the payload. To see details, the receiver uses the intake reference with the authenticated, clinic-scoped review-queue API (#30).

## Signature

- **Algorithm:** HMAC-SHA256, keyed with `WEBHOOK_SECRET` (UTF-8).
- **Signed bytes:** exactly the HTTP request body. That body is `json.dumps(payload, separators=(",", ":"), sort_keys=True)` encoded as UTF-8.
- **Header:** `X-Webhook-Signature: sha256=<lowercase hex digest>`.
- **Other headers:** `Content-Type: application/json`, `Idempotency-Key: <idempotency_key>`, `X-Webhook-Event: intake.escalated`.

Receiver verification:

1. Read the **raw** request body bytes. Do not parse and re-serialize them.
2. Compute `"sha256=" + hex(HMAC_SHA256(secret, raw_body))`.
3. Compare it with `X-Webhook-Signature` using a constant-time comparison (`hmac.compare_digest`). Reject the request if they differ.
4. Deduplicate on `Idempotency-Key`. The same key can arrive more than once.

`api.webhook.verify_signature(body, header, secret)` is a reference implementation.

## Idempotency and retries

- The key is derived only from the intake ID, so every attempt and any later handling of the same intake use the same key. It contains no PHI.
- Before the first send, a `webhook_deliveries` row is committed with that key under a unique constraint. Handling the same intake a second time hits the constraint and sends nothing (`already_notified`).
- Each attempt sends identical body bytes, signature and key.
- **Retried:** timeouts, connection errors, HTTP 408, 429 and 5xx, up to `WEBHOOK_MAX_ATTEMPTS`, with the deterministic backoff above.
- **Not retried:** other 3xx and 4xx responses, which are recorded as `failed`. Redirects are not followed.
- **Stopping:** retries stop at the first 2xx.

This is **one logical notification with bounded delivery attempts, not a delivery guarantee**. The receiver may get it once, more than once, or not at all. It can arrive more than once if a request succeeds but the response is lost, so the receiver must deduplicate on `Idempotency-Key`. It may not arrive if every attempt fails or the process stops mid-delivery. The resulting local state is recorded in `webhook_deliveries`.

## Delivery log (`webhook_deliveries`)

There is one row per logical notification:

| Column | Contents |
| --- | --- |
| `idempotency_key` | Unique. |
| `intake_id` | References `health_records`, with cascade delete. |
| `event_type` | The event name. |
| `target` | Only `scheme://host[:port]`, never the path, query or credentials. |
| `status` | `pending`, `delivered` or `failed`. |
| `attempts` | Number of attempts made. |
| `last_http_status` | Status code of the last response, if any. |
| `last_error` | A failure class: `timeout`, `connection_error`, `http_3xx` (redirect, not followed), `http_4xx`, `http_408`, `http_429` or `http_5xx`. |
| `attempt_log` | One entry per attempt: `{attempt, outcome, http_status, at}`. |
| `created_at`, `updated_at`, `delivered_at` | Timestamps. |

The log never stores the payload's source data, the secret, the signature or response bodies, which are never read. Server logs record only the key, status, attempt count and target host.

## Failure isolation

- Delivery runs after the intake is committed, in its own database session, so a webhook problem cannot roll back or alter the escalated intake.
- `notify_escalation` never raises, and the pipeline also guards the call. Timeouts, connection failures, 5xx responses, exhausted retries, delivery-log database errors and unexpected exceptions all leave `/api/ingest` returning its normal successful response.
- Webhook status, errors and configuration are not added to the trace, so none of it appears in the patient response.

## Local testing

`tests/test_webhook.py` uses two kinds of receiver, so no external service is called and CI needs no network or credentials:

- a recording fake transport;
- a loopback `http.server` receiver that verifies the signature over the bytes it received.

To try it by hand, run any local receiver, set `WEBHOOK_URL=http://127.0.0.1:<port>/hook` and a 32+ character `WEBHOOK_SECRET`, then submit an escalating intake, for example: "I have chest pain and shortness of breath."

## Limitations

- **Synchronous delivery:** it happens inside the ingest request, after persistence. With the default retry and backoff settings and a responsive network, a failed delivery can add about 10.5 s to an escalated intake's response (3 attempts × 3 s, plus 1.5 s of backoff). The HTTP timeout applies per socket operation, not as a strict total deadline, and DNS resolution may fall outside it. The added time is only ever latency, never an error.
- **No re-drive:** there is no queue or worker (Redis, Celery and similar are out of scope). A `failed` notification, or one left `pending` because the process stopped mid-delivery, is not retried later. It is visible in `webhook_deliveries` for manual follow-up.
- **One receiver:** there is a single target and no per-clinic routing.
- **No replay window:** the signature carries no timestamp, so receivers should deduplicate on `Idempotency-Key`.
- **PHI elsewhere is unchanged:** the raw-PHI-in-trace finding from #32 is not addressed here. The webhook payload just never reads from those locations.
