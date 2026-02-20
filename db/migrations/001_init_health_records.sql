-- Migration: 001_init_health_records.sql
-- Purpose: Create health_records table for Healthcare AI Platform
-- Author: Healthcare AI Platform

-- Enable required extension (optional but good practice)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: health_records
CREATE TABLE IF NOT EXISTS health_records (

    -- Primary Key
    id TEXT PRIMARY KEY,

    -- Trace & versioning
    trace_id TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,

    -- Core payloads (JSONB for structured + flexible storage)
    intake_json JSONB NOT NULL,
    structured_output_json JSONB NOT NULL,

    -- Final report
    report_json JSONB NOT NULL,
    report_text TEXT NOT NULL,

    -- Safety / compliance audit
    safety_audit_json JSONB NOT NULL,

    -- Idempotency support
    input_hash TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
-- Fast lookup by trace_id
CREATE INDEX IF NOT EXISTS ix_health_records_trace_id
    ON health_records (trace_id);

-- Idempotency protection (nullable unique)
CREATE UNIQUE INDEX IF NOT EXISTS uq_health_records_input_hash
    ON health_records (input_hash)
    WHERE input_hash IS NOT NULL;

-- Optional: JSONB GIN index for structured search (future-proof)
-- Useful if you later query inside structured_output_json
CREATE INDEX IF NOT EXISTS ix_health_records_structured_gin
    ON health_records
    USING GIN (structured_output_json);

-- Optional: JSONB GIN index for report_json
CREATE INDEX IF NOT EXISTS ix_health_records_report_gin
    ON health_records
    USING GIN (report_json);

-- End of Migration