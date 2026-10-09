# Architecture Decision Records

Concise records of the main design decisions that are implemented in the code. Each lists the decision, why it was made, and its accepted consequences. Issue numbers point to the delivering work.

## ADR-1 — Narrow product scope: pre-visit intake with human review

* **Decision:** Build one workflow (patient intake → AI structuring and summary → safety rules → clinic review queue → signed notification) instead of a general healthcare AI platform ([`step3_roadmap.md`](step3_roadmap.md) §1, §8).
* **Why:** A complete, tested, deployed workflow is stronger evidence than many partial AI components.
* **Consequences:** FHIR export, HL7, EHR routing, voice and extra agents are out of scope or deferred (#42).

## ADR-2 — Deterministic mock LLM mode by default; real mode opt-in (#20/PR #21, #22)

* **Decision:** `LLM_MODE=mock` is the default and the only mode in CI; `LLM_MODE=real` (OpenAI) must be set explicitly, fails at startup without a key, and never falls back to mock.
* **Why:** Reproducible tests and benchmarks without secrets or cost; no silent change of behaviour when a provider fails.
* **Consequences:** CI scores measure contract stability, not model quality. Both modes share the same JSON-schema validation.

## ADR-3 — Deterministic, rule-based safety guard and escalation (#29, #32)

* **Decision:** Diagnosis/prescription blocking, report PHI masking and emergency detection are regex/keyword rules; escalation to `needs_review` uses reason codes (emergency signal, blocked output, confidence < 0.5).
* **Why:** Patient-facing AI needs predictable, testable boundaries and a human in the loop; behaviour is measured on a labelled synthetic suite in CI.
* **Consequences:** Rules have known gaps (recorded in [`evaluation_benchmark.md`](evaluation_benchmark.md)); a 1.0 match rate means agreement with the labelled baseline, not safety accuracy.

## ADR-4 — PostgreSQL with plain ordered SQL migrations (#27)

* **Decision:** `db/migrations/NNN_*.sql` applied in order by `db/migrate.py`, recorded in `schema_migrations`, run on every start.
* **Why:** Small schema, no extra migration dependency, safe to rerun on new or existing databases; tested on PostgreSQL in CI, including a v1 → v2 upgrade.
* **Consequences:** No automatic down-migrations.

## ADR-5 — Operator-issued HMAC bearer tokens and per-request membership checks (#28, #30)

* **Decision:** Staff authenticate with HMAC-signed, expiring tokens issued by a CLI; clinic roles are re-read from the database on every request and every query filters on the authorized clinic.
* **Why:** Server-side tenant isolation with minimal moving parts; role changes apply immediately.
* **Consequences:** No login UI, SSO, MFA or revocation list; patient intake stays unauthenticated and goes to one seeded clinic.

## ADR-6 — Best-effort persistence and notification (PR #23, #33)

* **Decision:** Database and webhook problems never fail the patient's request; outcomes are reported (`persistence` in the trace, `webhook_deliveries` rows) and logged.
* **Why:** The patient-facing response should not depend on downstream systems.
* **Consequences:** The webhook is one logical notification with bounded attempts, not a delivery guarantee; receivers deduplicate on `Idempotency-Key`.

## ADR-7 — Minimal, allowlisted webhook payload (#33)

* **Decision:** The signed payload carries only event, schema version, idempotency key, intake id and clinic id; receivers fetch details through the authenticated review API.
* **Why:** No PHI leaves the system through the integration.
* **Consequences:** Receivers need API access for any detail.

## ADR-8 — Audit events without intake text (#30, #34)

* **Decision:** Pipeline, request and staff-action audit events contain ids, status, counts, paths and reason codes only; a regression test checks the written audit file.
* **Why:** Audit logs are widely read and retained; they should not become a second copy of patient text.
* **Consequences:** Application/exception logs are not covered by that test ([`security_data_handling.md`](security_data_handling.md)).

## ADR-9 — Single hosted demo on a Render Blueprint (#35)

* **Decision:** One `render.yaml` with the existing Dockerfiles and managed PostgreSQL on free plans; migrations and an idempotent synthetic seed run in the start command; secrets generated or entered in the platform.
* **Why:** Lowest-effort hosting for the existing stack without Terraform or multi-service cloud infrastructure (roadmap §8).
* **Consequences:** Cold starts, a 30-day free database, one environment and one instance ([`deployment.md`](deployment.md)).
