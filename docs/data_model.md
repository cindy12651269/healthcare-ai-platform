# Data Model v2 & Migrations (Issue #27)

Schema: `db/migrations/001_init_health_records.sql` + `002_clinics_users_review_status.sql`.
ORM: `db/models.py`.

Issue #27 added the tables and columns only. Later issues built on them: authentication, role enforcement and clinic isolation (#28, [`auth.md`](auth.md)); escalation rules (#29, below); review-queue endpoints (#30, [`review_queue_api.md`](review_queue_api.md)); the webhook delivery log, migration `003_webhook_deliveries.sql` (#33, [`escalation_webhook.md`](escalation_webhook.md)).

---

## Tables

| Table | Columns | Constraints |
| --- | --- | --- |
| `clinics` | `id`, `name`, `created_at` | PK `id`. Migration 002 seeds `('default', 'Default Clinic')`. |
| `users` | `id`, `email`, `display_name`, `created_at` | PK `id`; `email` unique. No stored credentials; staff authenticate with signed tokens ([`auth.md`](auth.md)). |
| `clinic_memberships` | `user_id`, `clinic_id`, `role`, `created_at` | PK (`user_id`, `clinic_id`); FKs to `users` / `clinics` (cascade on delete); `role` ∈ `clinic_staff`, `clinic_admin`. A user can belong to several clinics with one role each. |
| `health_records` (v1 + new columns) | `clinic_id`, `review_status`, `escalation_reason` | `clinic_id` NOT NULL, FK to `clinics`, no default; `review_status` NOT NULL, default `submitted`, ∈ `submitted`, `needs_review`, `reviewed`, `escalated`; `escalation_reason` nullable text. Index (`clinic_id`, `review_status`) for the review queue. |

### Review status

* `submitted` — stored and not flagged. This is the initial status of every intake and of upgraded v1 records.
* `needs_review` — flagged for staff review, with `escalation_reason` set (set by the escalation rules, #29).
* `reviewed` / `escalated` — staff outcomes, set only by the `needs_review → reviewed | escalated` transition (#30).

`submitted` is added alongside the three required statuses so that an intake that has not been flagged is distinguishable from one waiting in the review queue.

### Escalation rules (#29)

`agents/escalation.py` evaluates every successful `/api/ingest` run. A non-triggering intake is stored as `submitted` with a NULL `escalation_reason`. Any trigger stores it as `needs_review` with `escalation_reason` set to the comma-separated reason codes, in this order:

| Reason code | Trigger |
| --- | --- |
| `emergency_signal` | The safety guard's existing emergency detection matches the intake text or the generated report. The patient-facing emergency guidance is unchanged. |
| `blocked_diagnosis` | The safety guard blocked the generated report for diagnostic certainty. |
| `blocked_prescription` | The safety guard blocked the generated report for prescription or dosing content. |
| `low_confidence` | `clinical_structuring.confidence_level` is below `LOW_CONFIDENCE_THRESHOLD = 0.5` (strict; 0.5 itself does not escalate). |

A blocked report is not returned to the patient and does not produce a 500. The response carries a fixed acknowledgement report (`report_metadata.model_version = "safety_acknowledgement"`, plus the unchanged emergency guidance when an emergency signal is present), and `safety` keeps only the guard's actions and reason types. The decision is in the trace (`escalation`: `required`, `review_status`, `reasons`, `confidence_level`, `low_confidence_threshold`) and in the pipeline audit event flags (`escalation_required`, `escalation_reasons`). Neither contains intake text.

---

## `/api/ingest` clinic assignment

**Decision:** every intake persisted by `/api/ingest` is assigned to the seeded clinic `default` (`db.models.DEFAULT_CLINIC_ID`, passed explicitly by `HealthcarePipeline.save_record`). The request body is unchanged.

**Why:** the endpoint is unauthenticated, so a client-supplied clinic id could not be trusted and would let any caller file intakes into any clinic. A single fixed clinic is deterministic, needs no new request field or configuration, and keeps existing clients and tests working. Per-clinic intake routing (for example a clinic-specific intake link or key) is decided with authentication and clinic isolation in #28.

---

## Migrations

**Decision:** keep the existing ordered SQL runner (`db/migrate.py`) and add `002_clinics_users_review_status.sql`. No migration framework (e.g. Alembic) is introduced.

**Why:** the runner already applies files in filename order, one transaction per file, records each in `schema_migrations`, and runs on every Compose start (`python -m db.migrate`). That covers the fresh-volume and existing-volume cases this project needs. A framework would add a dependency and a second source of schema truth without solving a current problem. `001` is not modified.

**Upgrade of a v1 database:** `002` adds `clinic_id` with a temporary default of `'default'` (which backfills existing rows) and then drops the default, so new rows must name their clinic. Existing rows get `review_status = 'submitted'` and a NULL `escalation_reason`. No rows are rewritten or deleted.

**Re-running:** applied files are skipped via `schema_migrations`; `002` also uses `IF NOT EXISTS` / `ON CONFLICT DO NOTHING` like `001`. Migration locking for multiple replicas is out of scope.

**Tests:** `tests/test_data_model_v2.py` (SQLite, ORM constraints) and `tests/test_persistence_postgres.py` (PostgreSQL in CI: fresh migration, v1 → v2 upgrade preserving a record, constraints, and `/api/ingest` persistence with clinic and review status).
