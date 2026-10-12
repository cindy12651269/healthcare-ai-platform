# FHIR R4 Export of an Intake (Issue #42)

Export-only mapping of one stored intake to a FHIR R4 `Bundle` (type `collection`). Nothing is sent to an EHR, FHIR server or sandbox; there is no inbound FHIR, search or FHIR server. **Synthetic demo data only**: the Bundle carries the tag `urn:healthcare-ai-platform:data|synthetic-demo` ("FHIR R4 — Synthetic Demo Data"). No US Core or other profile conformance is claimed.

Code: `interoperability/fhir_export.py` (mapping), `interoperability/fhir_validation.py` (validation), `interoperability/fhir/intake_questionnaire.json` (static form definition), `api/routers/fhir.py` (endpoint). Example: `interoperability/fhir/examples/synthetic_reviewed_intake_bundle.json`.

## Endpoint

`GET /api/clinics/{clinic_id}/intakes/{intake_id}/fhir` → `200 application/fhir+json`.

Same authorization as the #30 records API ([`../review_queue_api.md`](../review_queue_api.md)): 401 without a valid staff token, 403 without a `clinic_staff`/`clinic_admin` membership of `{clinic_id}`, 404 for an intake owned by another clinic (same as a missing id). Read-only; any review status can be exported, and the `Task` shows the current one. Each successful export emits an `intake.fhir_export` audit event with actor id, clinic id and intake id only — never intake text or Bundle content (`tests/test_audit_no_raw_text.py`, `tests/test_fhir_export.py`).

The export is deterministic: entries use `urn:uuid` fullUrls derived (UUIDv5) from the intake id, and the Bundle has no export timestamp. All internal references resolve to entries in the same Bundle.

## R4 vs R4B and the validator

The target is **FHIR R4 (4.0.1)**. Every resource used here (`Bundle`, `QuestionnaireResponse`, `Questionnaire`, `Task`, `Provenance`, `Organization`, `Device`) and every element mapped below has the same name, cardinality, type and required value set in R4B (4.3.0); R4B's changes are to other resources (e.g. medication definition, `SubscriptionTopic`, `Citation`/`Evidence`), so the output is also R4B-shaped. R4 was chosen because it is the version EHRs commonly accept.

**Validator:** the official HL7 FHIR R4 JSON Schema (`https://hl7.org/fhir/R4/fhir.schema.json.zip`, generated 2019-11-01 for 4.0.1), vendored as `interoperability/fhir/fhir.schema.json.zip` and pinned by SHA-256 (`75e5560d…cb5ac6`; the loader refuses a mismatching file). It is run offline with `jsonschema` (Draft 6, pinned in `requirements-dev.txt`) against each resource's definition and the Bundle. The JSON Schema checks structure, datatypes, primitive formats (e.g. `instant`, `uri`) and required code enumerations. It does **not** enforce 1..1 primitives, FHIRPath invariants or terminology bindings, so two supplementary checks run: the R4 1..1 primitives of the exported resources (`Bundle.type`, `Task.status`/`intent`, `QuestionnaireResponse.status`, `item.linkId`, `Provenance.recorded`, `Questionnaire.status`, `item.linkId`/`type`) and reference resolution within the Bundle. This is not the full HL7 Java validator (no profile or invariant evaluation); that would need a JVM and package downloads in CI.

CI: `tests/test_fhir_export.py` (backend job) validates the static Questionnaire, the committed synthetic example (which must also equal the exporter's output), and the Bundles exported through the API before and after a staff review.

## Mapping

| FHIR element | Source | Notes |
| --- | --- | --- |
| **QuestionnaireResponse** | | The patient's submission |
| `.identifier` | `health_records.id` | system `urn:healthcare-ai-platform:intake` |
| `.questionnaire` | static Questionnaire `url` | `urn:healthcare-ai-platform:fhir:Questionnaire:pre-visit-intake`; the Questionnaire is included in the Bundle |
| `.status` | constant `completed` | A stored intake is a submitted form |
| `.authored` | `intake_json.timestamp` | Naive value interpreted as UTC (written by `datetime.utcnow()`); omitted if absent |
| `.item[symptoms].answer.valueString` | `intake_json.raw_text` | **Raw intake text, unmasked (PHI-bearing)**; omitted if absent |
| `.item[consent].answer.valueBoolean` | `intake_json.consent_granted` | Omitted if absent |
| **Questionnaire** | `interoperability/fhir/intake_questionnaire.json` | Two items (`symptoms` text, `consent` boolean), matching the intake form |
| **Task** | | The review workflow |
| `.identifier` | `health_records.id` | system `…:intake-review` |
| `.status` | `review_status` | `submitted` → `received`, `needs_review` → `ready`, `reviewed` → `completed`, `escalated` → `completed` |
| `.businessStatus` | `review_status` | Exact platform value (coding `…:review-status` + text); keeps `reviewed` vs `escalated`, which `status` cannot |
| `.intent` | constant `order` | Required by R4; review is requested by the #29 rules |
| `.reasonCode.text` | `escalation_reason` | Comma-separated #29 reason codes, uncoded; omitted when not escalated |
| `.focus` | QuestionnaireResponse | |
| `.owner` | Organization | |
| `.authoredOn` / `.lastModified` | `created_at` / `updated_at` | UTC |
| **Organization** | `clinics` | `.identifier` = clinic id; `.name` = clinic name (omitted if the clinic row is missing) |
| **Device** | AI pipeline | `.deviceName` constant; `.version[]` = `model` (`output_metadata.model_version`), `prompt` (`output_metadata.prompt_version`), `pipeline` (`pipeline_version`); each omitted if not recorded |
| **Provenance** (AI) | | `.target` = QuestionnaireResponse + Task; `.recorded` = `created_at`; `.activity.text` includes the run id; `.agent` type `assembler`, `who` → Device |
| **Provenance** (review) | `review_events` (#41) | One per recorded staff transition: `.target` = Task; `.recorded` = transition time; `.agent` type `verifier`, `who.identifier` = staff user id (system `…:user`), `onBehalfOf` → Organization; `.activity.text` = `from -> to` |

## Deliberately not mapped

| Not exported | Reason |
| --- | --- |
| `Patient`, `QuestionnaireResponse.subject` | No demographics are collected; `user_id` is an anonymous intake id, not a patient identity |
| `Encounter` | No visit or encounter data exists |
| `Condition`, `Observation`, any clinical coding (ICD-10, SNOMED, LOINC) | Extracted symptoms are uncoded, unverified strings (in mock mode, a rule-based baseline, #40); coding them would invent clinical facts |
| Medication resources | Out of scope; the platform blocks prescription content |
| Structured output (symptoms, summary, confidence), report, safety guard evidence | AI-derived content and guard matches are not a clinical record; only provenance (versions) is exported |
| `contains_phi`, `source`, `input_type`, `user_id` | Internal processing flags and identifiers with no FHIR meaning here |
| `Practitioner` / reviewer email or name | Only the staff user id is persisted with the transition; no professional identity exists |
| Reviewer for transitions made before migration 004 | Not persisted (#41); no reviewer agent is invented |
| Times of processing, safety and escalation steps | Not persisted; `Provenance.recorded` uses the record creation time |
| Webhook deliveries, timeline | Operational data, not part of the clinical record |
| `Bundle.timestamp`, `Bundle.identifier` | Omitted to keep the export deterministic |

**Information loss:** `Task.status` merges `reviewed` and `escalated` into `completed` (the distinction is kept in `businessStatus`); escalation reasons are free text, not coded.
