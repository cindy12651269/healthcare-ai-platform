-- Migration: 002_clinics_users_review_status.sql
-- Purpose: Data model v2 (Issue #27) — clinics, users and clinic membership roles,
--          clinic ownership and review status for health_records.
-- Existing v1 rows are kept: they are assigned to the seeded 'default' clinic
-- with review_status 'submitted' (not yet evaluated by escalation rules).

-- Table: clinics
CREATE TABLE IF NOT EXISTS clinics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The clinic /api/ingest assigns intakes to (db.models.DEFAULT_CLINIC_ID)
INSERT INTO clinics (id, name) VALUES ('default', 'Default Clinic')
    ON CONFLICT (id) DO NOTHING;

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- Table: clinic_memberships (a user's role within one clinic)
CREATE TABLE IF NOT EXISTS clinic_memberships (
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    clinic_id TEXT NOT NULL REFERENCES clinics (id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, clinic_id),
    CONSTRAINT ck_clinic_memberships_role CHECK (role IN ('clinic_staff', 'clinic_admin'))
);

CREATE INDEX IF NOT EXISTS ix_clinic_memberships_clinic_id
    ON clinic_memberships (clinic_id);

-- health_records: clinic ownership, review status, escalation reason.
-- The DEFAULT backfills existing rows; it is then dropped so new rows must name their clinic.
ALTER TABLE health_records
    ADD COLUMN IF NOT EXISTS clinic_id TEXT NOT NULL DEFAULT 'default'
        CONSTRAINT fk_health_records_clinic_id REFERENCES clinics (id),
    ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'submitted'
        CONSTRAINT ck_health_records_review_status
        CHECK (review_status IN ('submitted', 'needs_review', 'reviewed', 'escalated')),
    ADD COLUMN IF NOT EXISTS escalation_reason TEXT;

ALTER TABLE health_records ALTER COLUMN clinic_id DROP DEFAULT;

-- Review queue lookup: a clinic's intakes by status
CREATE INDEX IF NOT EXISTS ix_health_records_clinic_review_status
    ON health_records (clinic_id, review_status);

-- End of Migration
