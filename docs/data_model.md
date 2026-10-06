# Data Model v2 & Migrations (Issue #27)

Schema: `db/migrations/001_init_health_records.sql` + `002_clinics_users_review_status.sql`.
ORM: `db/models.py`.

This issue adds the tables and columns only. Authentication, role enforcement, clinic isolation (#28), escalation rules (#29) and review-queue endpoints (#30) are not implemented.

---

## Tables

| Table | Columns | Constraints |
| --- | --- | --- |
| `clinics` | `id`, `name`, `created_at` | PK `id`. Migration 002 seeds `('default', 'Default Clinic')`. |
| `users` | `id`, `email`, `display_name`, `created_at` | PK `id`; `email` unique. No credentials yet (#28). |
| `clinic_memberships` | `user_id`, `clinic_id`, `role`, `created_at` | PK (`user_id`, `clinic_id`); FKs to `users` / `clinics` (cascade on delete); `role` ∈ `clinic_staff`, `clinic_admin`. A user can belong to several clinics with one role each. |
| `health_records` (v1 + new columns) | `clinic_id`, `review_status`, `escalation_reason` | `clinic_id` NOT NULL, FK to `clinics`, no default; `review_status` NOT NULL, default `submitted`, ∈ `submitted`, `needs_review`, `reviewed`, `escalated`; `escalation_reason` nullable text. Index (`clinic_id`, `review_status`) for the review queue. |

### Review status

* `submitted` — stored and not flagged. This is the initial status of every intake and of upgraded v1 records.
* `needs_review` — flagged for staff review, with `escalation_reason` set (set by the escalation rules, #29).
* `reviewed` / `escalated` — staff outcomes (transitions belong to #30).

`submitted` is added alongside the three required statuses so that an intake that has not been flagged is distinguishable from one waiting in the review queue.

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
