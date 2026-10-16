# Hosted Demo Walkthrough

Step-by-step use of the hosted demo, matching the UI deployed after Phase 8 (#67–#72; frontend build `68db16a`, checked 2026-10-16). Synthetic data only: never enter real personal or health information. No medical advice, no HIPAA or other compliance claim.

| | URL |
| --- | --- |
| Frontend (product dashboard) | https://healthcare-ai-frontend-1s23.onrender.com |
| API | https://healthcare-ai-api-tovn.onrender.com |

Screenshots of each step: [`screenshots/`](screenshots/README.md).

## Before you start: cold starts and demo data

* **Cold start.** Render free services sleep after about 15 minutes idle. Opening any page starts the wake-up. The page shows *"Waking the demo server (can take up to a minute)"* with the attempt count, then *"Demo server is awake"*. If the API still has not answered after six attempts, the page shows *Try again*. An intake submitted while the server is waking is held and not sent until the API answers. To wake the demo from a terminal:

  ```bash
  curl -s https://healthcare-ai-api-tovn.onrender.com/health
  # {"status":"ok","app":"Healthcare AI Platform","environment":"demo","llm_mode":"mock"}
  ```

* **Mock mode.** The hosted API runs `LLM_MODE=mock`. Extraction is a deterministic rule-based baseline and no language model is called. The header shows *Demo · synthetic data · mock mode*, and `/intake` shows *LLM Mode: Mock*.
* **No webhook delivery.** The escalation webhook has no receiver on the hosted demo (#67), so nothing is sent to a third party.
* **Database lifecycle.** The free database expires on **2026-11-08** (Render dashboard, read 2026-10-16). It is then recreated and re-seeded ([`deployment.md`](deployment.md) §9.4), and records submitted by visitors are lost. Re-seeding never resets a status that staff changed, so the hosted queues may differ from the seed description in §3.

## 1. Product dashboard (anyone)

Open `/`. The page shows:

* the product statement and two entry points, *Try Patient Intake* and *Explore Staff Workflow*;
* the **Live system status** card: API reachability, `environment` and `llm_mode`, exactly as `GET /health` reports them;
* the seven-stage workflow, each stage labelled *Implemented*, *Mock mode* or *Demo limit*, with the signed webhook drawn as a conditional branch of the escalation step;
* *What is real vs. mock*, capability cards with evidence links, and the seeded demo staff identities (no credentials).

## 2. Patient intake: four synthetic scenarios (anyone)

1. Open `/intake` (*Patient intake* in the navigation).
2. Choose a scenario card. It fills the description only: it never ticks consent and never submits. Each card shows its expected outcome.
3. Tick consent yourself, then *Submit intake*. Progress shows *Demo server ready* → *Process your intake* → *Submission completed*. While a submission is active, the form and the Submit button are disabled.
4. Read the result. The heading *Your intake has been received* comes first, then emergency guidance when it applies, then the **Outcome** card (status, matched rules, what happens next). The intake summary, extracted information, safety findings and the pre-visit report follow, or a safe acknowledgement if the report was withheld.

| Scenario | Synthetic text | Expected outcome |
| --- | --- | --- |
| Routine symptoms | I have had a sore throat and a mild fever for two days. | Not flagged (`submitted`); symptoms *sore throat, fever*, duration *two days* |
| Emergency language | I have chest pain and shortness of breath since this morning. | Urgent-care guidance shown first; rule `emergency_signal` |
| Prescription request | Should I take 500 mg of amoxicillin for this cough? | Report withheld, *Safe acknowledgement (report withheld)*; rule `blocked_prescription` |
| Vague / low confidence | I just don't feel right and wanted to check in. | No lexicon symptom, confidence below 0.5; rule `low_confidence` |

These outcomes are pinned by `tests/test_demo_seed_intakes.py::test_scenario_presets_produce_the_documented_outcomes` and were verified on the hosted UI on 2026-10-15 ([Phase 8 journal](project_journal/phase8_Frontend_Experience_&_Portfolio_Presentation.md) §5d).

**Duplicate submissions.** Byte-identical text is stored only once. The four preset texts are already stored on the hosted database, so submitting one shows the matched rules and any safety guidance, but the badge reads *Already received · no new record*. The next step then says *"An identical description was received earlier, so no new record was created and nothing new was added to the clinic staff queue."* This is correct behaviour. A duplicate never triggers the webhook. Editing the text creates a new record. Please do so only with synthetic text, and only if you actually need a new queue item.

**Errors.** If the API is unreachable, returns an error or times out, the page says so. Your text and consent choice are kept, and nothing is retried automatically: *Try again* / *Send again* is always an explicit action.

**Reviewer trace.** Tick *Reviewer / developer: show the pipeline trace for this submission* to see escalation, review status, reasons and storage status. The full `/api/ingest` response includes the raw intake text (a documented #32 finding).

## 3. Staff review, evidence, FHIR export and clinic isolation (operator token required)

Staff access needs a short-lived token for one of the seeded synthetic users. Tokens are **issued on request by the demo operator** (the repository owner) and are never published: there is no public sign-up, guest login or shared password, and no password exists for these users. The operator procedure is in [`deployment.md`](deployment.md) §6 and §9.3.

| User id | Clinic | Role |
| --- | --- | --- |
| `demo-staff-a` | `default` | `clinic_staff` |
| `demo-admin-a` | `default` | `clinic_admin` |
| `demo-admin-b` | `demo-clinic-b` | `clinic_admin` |

The demo seed (`APP_ENV=demo` only) creates four synthetic intakes per clinic, one per review status. On the hosted demo, clinic `default` also contains the intakes submitted by visitors and by earlier verifications.

1. Open `/staff` (*Staff review*), paste the token and select *Sign in*. The token stays in the tab's memory: it is not written to browser storage or cookies, and it is gone after *Sign out*, a reload or closing the tab.
2. **Queue.** Status tabs (*Needs review*, *Reviewed*, *Escalated*, *Submitted*, *All*) with counts from the clinic's loaded list. Times are shown in UTC. At 1280 px and wider, the queue and the detail sit side by side; on narrower screens, opening an intake shows the detail with *← Back to queue*.
3. **Detail.** The header shows the reference, status, reasons, full id and times. The page then shows the structured summary, the report, the safety result and *Why flagged* with the recorded evidence. The original input appears beside the extracted fields, with the guard's matches highlighted. Provenance shows the mode, model, prompt and pipeline versions and the run id.
4. **Timeline.** Submitted → processed → safety evaluated → escalation decision, then any webhook delivery attempts and staff actions (actor, from → to). With no delivery recorded, it says *"No webhook delivery is recorded for this intake."*
5. **Decision.** Only `needs_review` intakes can be changed. *Mark reviewed* or *Mark escalated* opens a confirmation step; *Confirm* applies the change, *Cancel* sends nothing. The queue and timeline then refresh. Staff transitions never send a webhook.
6. **FHIR R4 export.** *Load FHIR export* shows the disclaimer (synthetic data, export only, not a conformance or certification claim, contains the original intake text), the resource summary and a collapsed JSON preview. *Download JSON* saves the Bundle.
7. **Clinic isolation.** A `demo-admin-b` token shows only `demo-clinic-b` intakes (`#demo-intake-b1` … `#demo-intake-b4`). Clinic `default` requests return 403, and none of its intakes appear.

Staff actions change the shared hosted data, so please use them sparingly.

## 4. System card (anyone)

`/system-card` lists the known limitations first, then the pipeline stages (the webhook stage is marked *Conditional*), the safety and escalation rules (low-confidence threshold 0.5), the review rule, and the evaluation results with their sample sizes and caveats. The results come from the committed `evaluation/system_card_results.json`: 16 safety and escalation cases, and 6 in-sample extraction cases.

## 5. Signed webhook (operator, not on the public demo)

When `WEBHOOK_URL` and `WEBHOOK_SECRET` are both configured, each **newly stored** `needs_review` intake sends one HMAC-SHA256-signed POST carrying only `event`, `schema_version`, `idempotency_key`, `intake_id` and `clinic_id`. Duplicates and staff transitions send nothing. The operator verifies a delivery with `scripts/verify_webhook.py` ([`deployment.md`](deployment.md) §6 step 4; last verified 2026-10-09). The public demo keeps `WEBHOOK_URL` unset ([`deployment.md`](deployment.md) §9.1).

## 6. Scripted check (operator)

`python -m scripts.hosted_check --api https://healthcare-ai-api-tovn.onrender.com`, with `STAFF_A_TOKEN` and `STAFF_B_TOKEN` set in the environment, runs the original acceptance flow: emergency intake → clinic `default` queue → cross-clinic denial. It prints `[PASS]`/`[FAIL]` per check. Latest result: 8/8 PASS on 2026-10-14, webhook disabled ([Phase 8 journal](project_journal/phase8_Frontend_Experience_&_Portfolio_Presentation.md) §2a). The script submits a new flagged synthetic intake, so the operator confirms webhook isolation before running it.

## What this demo does not show

* real LLM output (mock mode only; extraction is a rule-based baseline);
* retrieval (not connected to the API);
* clinical validation or accuracy;
* real patient data;
* any production, HIPAA or other compliance property.

See [`project_status.md`](project_status.md).
