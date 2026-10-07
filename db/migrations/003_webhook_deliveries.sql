-- Migration: 003_webhook_deliveries.sql
-- Purpose: Escalation notification webhook delivery log (Issue #33).
-- One row per logical notification; outcome metadata only (no payload source data,
-- secret, signature or response bodies).

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    intake_id TEXT NOT NULL
        CONSTRAINT fk_webhook_deliveries_intake_id REFERENCES health_records (id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CONSTRAINT ck_webhook_deliveries_status CHECK (status IN ('pending', 'delivered', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_http_status INTEGER,
    last_error TEXT,
    attempt_log JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    CONSTRAINT uq_webhook_deliveries_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_intake_id
    ON webhook_deliveries (intake_id);

-- End of Migration
