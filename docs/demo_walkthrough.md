# Hosted Demo Walkthrough

Reproducible walkthrough of the hosted demo (#35), including the Phase 7 guided demo (#43). Synthetic data only: never enter real personal or health information. No medical advice; no HIPAA compliance claim.

| | URL |
| --- | --- |
| Frontend | https://healthcare-ai-frontend-1s23.onrender.com |
| API | https://healthcare-ai-api-tovn.onrender.com |

The services run on Render's free plan and sleep after ~15 minutes idle. Wake them first; the first request can take about a minute:

```bash
curl -s https://healthcare-ai-api-tovn.onrender.com/health
# {"status":"ok","app":"Healthcare AI Platform","environment":"demo","llm_mode":"mock"}
curl -s -o /dev/null -w "%{http_code}\n" https://healthcare-ai-frontend-1s23.onrender.com/
```

> **Phase 7 (#43) status.** Steps 0–2 below describe the guided demo added in #43. They are verified by automated tests (frontend and in-process backend) but **have not yet been re-run against the hosted demo**; the hosted services must be redeployed from `main` first (frontend rebuild with `NEXT_PUBLIC_DEMO_MODE=true`, API restart to seed the demo intakes). Record the hosted result here once performed.

## 0. Guided demo landing (anyone)

Open the frontend root (`/`). It explains the workflow (patient intake → AI processing → safety & escalation → staff review → evidence timeline → FHIR export) and links to **Patient intake** (`/intake`), **Staff review** (`/staff`) and the **System card** (`/system-card`). With `NEXT_PUBLIC_DEMO_MODE=true` it also lists the seeded demo staff identities (user id, clinic, role) — identities only, never tokens.

The **System card** shows the pipeline stages, the current execution mode (`mock`), the safety and escalation rules with the 0.5 low-confidence threshold, the committed #32 and #40 evaluation results with their limitations, known limitations and a "Not a medical device" statement.

## 1. Patient intake: four scenarios (anyone)

1. Open `/intake`. The header shows `LLM Mode: Mock`.
2. Click a scenario button. It fills the text only; tick consent yourself, then submit. Identical text is stored only once, so add something unique (e.g. "Synthetic test 4821") if you want a new record each time.

| Scenario | Preset text | Expected |
| --- | --- | --- |
| Routine symptoms | I have had a sore throat and a mild fever for two days. | Summary shown; symptoms *sore throat, fever*, duration *two days*; not flagged (`submitted`) |
| Emergency language | I have chest pain and shortness of breath since this morning. | Emergency guidance banner; flagged `emergency_signal` |
| Prescription request | Should I take 500 mg of amoxicillin for this cough? | Report blocked, safe acknowledgement shown; flagged `blocked_prescription` |
| Vague / low confidence | I just don't feel right and wanted to check in. | No lexicon symptom, confidence below 0.5; flagged `low_confidence` |

These outcomes are pinned by `tests/test_demo_seed_intakes.py::test_scenario_presets_produce_the_documented_outcomes`. The **developer trace** is hidden by default; tick "Reviewer / developer: show the pipeline trace" to see the raw `/api/ingest` response (`escalation`, `persistence.record_id`).

## 2. Staff review, evidence, FHIR export and clinic isolation (operator token required)

Staff tokens are issued by the operator, not by the browser ([`deployment.md`](deployment.md) §6 step 2); the site never publishes a token. Seeded synthetic users: `demo-staff-a` / `demo-admin-a` (clinic `default`) and `demo-admin-b` (`demo-clinic-b`). The demo seed (`APP_ENV=demo` only) adds four synthetic intakes per clinic, one in each review status (`submitted`, `needs_review`, `reviewed`, `escalated`); resolved ones carry one seeded staff transition.

1. Open `/staff` and paste a `demo-staff-a` token (kept in browser memory only). The `default` queue shows the flagged scenario intakes from step 1 and the seeded `demo-intake-a2`. Filter **All** to see every status.
2. Open a flagged intake. **Why flagged** shows the triggered rule and its recorded evidence; the original input sits next to the extracted fields (derived), with recorded safety matches highlighted where they occur in the input; provenance shows mode `mock`, model/prompt/pipeline versions and the run id. The **Timeline** lists submitted → processed → safety evaluated → escalation decision → webhook delivery → staff actions.
3. Mark it **Reviewed** or **Escalated**: the timeline reloads with the staff action (actor, from → to).
4. **FHIR R4 — Synthetic Demo Data**: click "Load FHIR export" for the JSON Bundle preview, then "Download JSON". The `Task` shows the current status and escalation reason; a `Provenance` names the reviewer after step 3.
5. Clinic isolation: with a `demo-admin-b` token, the `demo-clinic-b` queue shows only `demo-intake-b1`–`b4`; the `default` clinic's queue returns 403 and none of its intakes appear.

## 3. Signed webhook (operator)

Each newly stored `needs_review` intake sends one HMAC-signed POST to the configured receiver, with only `event`, `schema_version`, `idempotency_key`, `intake_id` and `clinic_id`. The operator verifies it with `scripts/verify_webhook.py` ([`deployment.md`](deployment.md) §6 step 4).

## 4. Scripted version

`python -m scripts.hosted_check --api https://healthcare-ai-api-tovn.onrender.com` (with `STAFF_A_TOKEN` and `STAFF_B_TOKEN` set) runs the original Phase 5 acceptance flow (emergency intake → `default` queue → cross-clinic denial) non-interactively and prints `[PASS]`/`[FAIL]` per check. Result on 2026-10-09: 8/8 PASS, exactly one webhook, `VALID signature` ([`deployment.md`](deployment.md) §7).

## What this demo does not show

Real LLM output (the hosted demo runs in mock mode; extraction is a rule-based baseline), retrieval (not wired into the API), clinical validation, real patient data, or any production or compliance property. See [`project_status.md`](project_status.md).
