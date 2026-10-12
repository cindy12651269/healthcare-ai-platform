# Phase 7 — Demo Experience, AI Evidence & FHIR Interoperability

Healthcare AI Platform
Timeline: Phase 7 (2026-10-12)
Scope: Issues #40, #41, #42, #43
Status: Implemented and merged — #40–#43 closed (2026-10-12). Hosted deployment **not verified** for Phase 7 (§4).

---

## 1. Phase Goal

Turn the hosted demo into a self-explanatory walkthrough and back it with visible evidence ([`step3_roadmap.md`](../step3_roadmap.md) §2, §7):

* An honest, measured extraction baseline in mock mode (#40)
* Per-intake evidence and an auditable review timeline for staff (#41)
* An export-only, validated FHIR R4 representation of an intake (#42)
* A guided demo, a system card and the Phase 7 close-out (#43)

Out of scope throughout: real LLM mode on the hosted demo, real patient data, compliance claims, a FHIR server or EHR connectivity, clinical coding, analytics dashboards.

---

## 2. Pull Requests

| PR | Issue | Head commits | Merge commit | Main CI run |
| --- | --- | --- | --- | --- |
| #60 Deterministic extraction baseline & extraction evaluation | #40 | `cfac44b` | `ba2aa3f` | 38234168161 — success |
| #61 Intake evidence & review timeline | #41 | `63001bd`, `efd4a17` | `428fbf9` | 38235577805 — success |
| #62 FHIR R4 export of reviewed intakes | #42 | `8c962a4`, `47d4023` | `b91d6ea` | 38237316553 — success |
| #63 Guided demo, system card & Phase 7 close-out | #43 | `8946ec4`, `5fd759b` | `2afdb4b` | 38238842122 — success |

Merged with merge commits after a final review gate. Two gates were blocked and fixed on the branch before merge: #61 (naive intake timestamps displayed in the browser's local time → normalised to UTC, sorted on parsed datetimes) and #62 (Questionnaire consent wording did not match the intake form → exact wording plus a regression test).

---

## 3. Completed Issues

### Issue 40 — Deterministic Extraction Baseline & Extraction Evaluation

**Delivered:** `agents/extraction_baseline.py` (documented synthetic lexicon, negation window, duration/onset/severity/red flags), coverage-based confidence `0.1 + 0.4·[≥1 symptom] + 0.15·[≥2] + 0.2·[duration|onset] + 0.15·[severity]` (no symptom ⇒ ≤ 0.45 < 0.5 ⇒ `low_confidence`), template summary labelled "not LLM-generated", `--suite extraction` with per-run and aggregate precision/recall (mock in CI, real opt-in).
**Evidence:** extraction 6 cases, micro/macro P = R = 1.00 (**in-sample**: the lexicon was written with these cases in view). #32 re-run: 16/16 guard and escalation matches; four cases gained `low_confidence`; `em_paraphrased_breathing` caught in mock mode (known gaps 4 → 3).
**Limitations:** fixed English lexicon, crude negation, one duration/onset per intake.

### Issue 41 — Intake Evidence & Review Timeline

**Delivered:** `GET /api/clinics/{clinic_id}/intakes/{id}/timeline` (`api/routers/timeline.py`), migration `004_review_events.sql` (transition history written in the same transaction as the status change), "Why flagged" evidence panel and timeline in the staff detail view (`app/components/IntakeEvidence.tsx`).
**Evidence:** 9 backend timeline tests (three triggers, ordering, persisted webhook/transition accuracy, legacy nulls, UTC normalisation, cross-clinic denial, ids-only audit); #34 audit test extended.
**Limitations:** stage times are not persisted (processing/safety/escalation carry the record time); emergency matches from the intake-text check were never stored; the shown threshold is the current constant; pre-#41 transitions are not backfilled.

### Issue 42 — FHIR R4 Export of Reviewed Intakes

**Delivered:** `GET /api/clinics/{clinic_id}/intakes/{id}/fhir` (`api/routers/fhir.py`, `interoperability/fhir_export.py`), deterministic Bundle (`QuestionnaireResponse`, `Questionnaire`, `Task`, `Organization`, `Device`, `Provenance`), JSON preview/download labelled "FHIR R4 — Synthetic Demo Data".
**Evidence:** official HL7 FHIR R4 4.0.1 JSON Schema vendored and SHA-256 pinned, plus required-primitive and reference checks; committed synthetic example must equal exporter output; isolation and ids-only audit tests.
**Limitations:** not the full HL7 validator (no profiles/invariants/terminology); reviewer is a staff user id only; `reviewed`/`escalated` both map to `Task.status = completed` (kept in `businessStatus`); downloaded files leave platform control.

### Issue 43 — Guided Demo, System Card & Phase 7 Close-out

**Delivered:** landing page with Patient / Staff / System card entry points and the workflow (`app/pages/index.tsx`, intake moved to `/intake`); four scenario presets that fill text only (`app/services/demo.ts`); developer trace behind a reviewer toggle; seeded synthetic intakes in two clinics covering every status, refused unless `APP_ENV=demo` (`db/seed_demo.py`); read-only `GET /api/system-card` and `/system-card` page serving the committed snapshot `evaluation/system_card_results.json`; demo staff identities (never tokens) shown only when `NEXT_PUBLIC_DEMO_MODE=true`.
**Evidence:** the snapshot is re-computed and compared in CI (`tests/test_system_card.py`); preset outcomes pinned through the real pipeline; seed idempotency, status coverage and clinic isolation tests; frontend tests for presets, toggle, system card and demo-flag visibility.
**Limitations:** hosted demo not yet redeployed or re-verified for #43; tokens still require the operator (no self-service sign-in, by design); seeded transitions are synthetic demo history.

---

## 4. Validation Summary

* Every Phase 7 PR passed the three CI jobs (backend + PostgreSQL, deterministic benchmark incl. extraction and safety suites, frontend lint/typecheck/test/build) on its final head and on `main` after merge (runs in §2).
* Hosted-demo verification for Phase 7 has **not** been performed; [`demo_walkthrough.md`](../demo_walkthrough.md) marks the Phase 7 steps accordingly.
* Hosted state observed on 2026-10-12 after the #63 merge (read-only requests): the frontend had redeployed (landing page, `/intake` presets, `/system-card` page and the demo staff panel are served), but the API was still the Phase 6 build — `/openapi.json` lists no `…/timeline`, `…/fhir` or `/api/system-card` route, and `/api/system-card` returns 404 (the API service has `autoDeployTrigger: off`). Until the API is redeployed from `main` (which also applies migration 004 and seeds the demo intakes), the hosted System Card shows its error state and the staff detail view cannot load the evidence timeline or FHIR export. No scenario was submitted to the hosted demo, because flagged submissions send a real webhook.

---

## 5. Carried-forward Limitations

* Rule-based safety, escalation and extraction: paraphrases and out-of-lexicon text are missed; evaluation sets are tiny, synthetic and partly in-sample.
* Raw intake text is stored unmasked and returned to authorized staff (timeline, FHIR export).
* No real-mode measurements; the hosted demo stays in mock mode.
