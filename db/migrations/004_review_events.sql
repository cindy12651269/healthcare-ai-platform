-- Migration: 004_review_events.sql
-- Purpose: Queryable staff review transition history (Issue #41).
-- One row per successful staff transition: actor, from -> to status, time.
-- Status values and ids only; never intake text, structured content or report content.
-- Transitions made before this migration exist only in the audit log and are not backfilled.

CREATE TABLE IF NOT EXISTS review_events (
    id TEXT PRIMARY KEY,
    intake_id TEXT NOT NULL
        CONSTRAINT fk_review_events_intake_id REFERENCES health_records (id) ON DELETE CASCADE,
    clinic_id TEXT NOT NULL
        CONSTRAINT fk_review_events_clinic_id REFERENCES clinics (id),
    actor_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_review_events_intake_id
    ON review_events (intake_id);

-- End of Migration
