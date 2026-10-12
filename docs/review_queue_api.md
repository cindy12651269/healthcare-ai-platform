# Records & Review-Queue API (Issue #30)

Code: `api/routers/records.py`. Tests: `tests/test_review_queue.py`.

These endpoints let clinic staff read their clinic's stored intakes and resolve the review queue that the escalation rules (#29, [`data_model.md`](data_model.md#escalation-rules-29)) fill. Patient intake (`POST /api/ingest`) is unchanged.

## Authentication, role and clinic scoping

Every route uses the #28 dependency `require_clinic_role("clinic_staff", "clinic_admin")` ([`auth.md`](auth.md)):

* No bearer token, or an invalid or expired one → **401**. Server without `AUTH_TOKEN_SECRET` → **503**.
* The caller must hold a `clinic_staff` or `clinic_admin` membership of the `{clinic_id}` in the path, read from `clinic_memberships`. Otherwise → **403**.
* Every query also filters on that authorized `clinic_id`. Another clinic's intake is never listed, and requesting it by id under your own clinic returns **404**, the same as a missing intake. A `clinic_id` in the query string or body is never used.

## Endpoints

| Method and route | Purpose | Response |
| --- | --- | --- |
| `GET /api/clinics/{clinic_id}/intakes[?review_status=<status>]` | Review queue / record list for the clinic, newest first. `review_status` ∈ `submitted`, `needs_review`, `reviewed`, `escalated` (any other value → 422). | List of `{id, trace_id, review_status, escalation_reason, created_at, updated_at}` |
| `GET /api/clinics/{clinic_id}/intakes/{intake_id}` | One intake for review. | Summary fields plus `clinic_id`, `structured` (structured result), `report`, `safety` (safety guard result). Unknown or other-clinic id → 404. |
| `POST /api/clinics/{clinic_id}/intakes/{intake_id}/transition` body `{"review_status": "reviewed" \| "escalated"}` | Resolve a flagged intake. | The updated intake (same shape as GET). |

| `GET /api/clinics/{clinic_id}/intakes/{intake_id}/timeline` (#41) | Read-only evidence and review timeline. | See [Intake evidence & timeline](#intake-evidence--timeline-41). Unknown or other-clinic id → 404. |

The detail response does not include the stored raw intake payload (`intake_json`). Clinical content is read-only; there is no edit endpoint.

## Intake evidence & timeline (#41)

Same authorization as every route here: 401 without a valid token, 403 without a staff/admin membership of `{clinic_id}`, 404 for an intake of another clinic (indistinguishable from a missing id). Unlike the detail response, it returns the original intake text (`intake_json.raw_text`), because the reviewer needs it to judge the evidence; only authorized staff of the owning clinic can read it.

Response:

* `evidence.original_input`: stored intake text, or `null` if the record has none.
* `evidence.extracted`: `symptoms`, `duration`, `onset`, `severity`, `red_flags`, `clinical_summary`, `confidence_level` from the stored structured output. These are **derived** fields (in mock mode, the #40 rule-based baseline), not recorded matches.
* `evidence.recorded_matches[]`: `{type, detail, match, found_in_input}` for every safety-guard reason that recorded a `match`. The guard runs on the generated report, so a match may not occur in the input; `found_in_input` is a case-insensitive substring check against the stored input, and the UI highlights only those. Blocked reports keep reason types only (no matches), by the #29 design.
* `evidence.escalation_rules[]`: one entry per stored `escalation_reason` code with the #29 rule text and its recorded evidence: guard action recorded + guard reasons of the matching type (emergency, blocked diagnosis/prescription), or `confidence_level` and the threshold (low confidence). The threshold is the current constant; it is not stored per record. For `emergency_signal`, the rule also checks the intake text; that check's match is not persisted, so the evidence can show no guard reason.
* `evidence.provenance`: `execution_mode`, `model_version`, `prompt_version` (from `structured.output_metadata`), `pipeline_version`, `run_id` (`trace_id`). `execution_mode` is derived: `mock` when `model_version == "mock"`, `real` for any other recorded model, `null` when nothing was recorded.
* `events[]`: `{kind, at, at_source, details}` sorted by `at`, ties in lifecycle order: `submitted` (`intake.timestamp`), `processed`, `safety_evaluated`, `escalation_decision` (all three at `record.created_at`, because their own times are not persisted), `webhook_delivery` (per `webhook_deliveries` row: event type, status, attempts, last HTTP status/error class, delivered time, attempt log; no target path, payload or secret) and `staff_transition` (per `review_events` row: actor id, from → to status).
* `notes[]`: plain statements of missing data for legacy records (status changed without a recorded transition, no input text, no model/prompt version). Missing values are `null`, never filled in.

No model reasoning is stored, so none is returned. Each successful read emits an `intake.timeline.read` audit event with actor, clinic and intake id only (covered by `tests/test_audit_no_raw_text.py`).

## Allowed transitions

| From | To |
| --- | --- |
| `needs_review` | `reviewed`, `escalated` |

Every other transition is rejected and the record is left unchanged:

* Target other than `reviewed` / `escalated`, or unknown body fields (e.g. `clinic_id`) → **422**.
* Current status is not `needs_review` (`submitted`, `reviewed`, `escalated`) → **409**. This also covers a second transition of an already resolved intake.
* The status is changed with a conditional update on the current status, so of two concurrent transitions only one succeeds; the other gets **409**.

`escalation_reason` is kept unchanged after a transition, as the record of why the intake was flagged.

## Audit

Each successful call emits one event through the existing audit logger (`observability/audit_logger.py`, `log_run`). The event has `status: "success"` and these fields:

| Field | Value |
| --- | --- |
| `actor_id` | Authenticated staff user id |
| `action` | `intake.list`, `intake.read` or `intake.transition` |
| `resource_id` | Intake id (`null` for list) |
| `flags` | `clinic_id`; list: `review_status`, `result_count`; transition: `from_status`, `to_status` |

Audit events never contain intake text, structured content or report content. Denied requests (401/403/404/409/422) emit no staff-action event; they are still recorded as failures by the request-level `AuditMiddleware`. `actor_id`, `action` and `resource_id` are optional fields on every audit event and are `null` on pipeline and request events.
