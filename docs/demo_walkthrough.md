# Hosted Demo Walkthrough

Reproducible walkthrough of the Phase 4–5 workflow on the hosted demo (#35). Synthetic data only: never enter real personal or health information. No medical advice; no HIPAA compliance claim.

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

## 1. Patient intake (anyone)

1. Open the frontend. The header shows `LLM Mode: Mock`.
2. Enter a short synthetic description that mentions an emergency symptom, plus something unique (identical text is stored only once), for example: *"Synthetic test 4821: sudden chest pain and trouble breathing since this morning."*
3. Tick consent and submit.
4. Expected: a non-diagnostic summary report. Expand **Developer trace**: its raw JSON (the full `/api/ingest` response) shows `escalation.required: true`, `escalation.reasons: ["emergency_signal"]` and `persistence.status: "saved"` with a `record_id`.

A routine description (e.g. a mild sore throat) shows `escalation.required: false` and is stored as `submitted`, so it does not appear in the review queue filter for `needs_review`.

## 2. Staff review (operator token required)

Staff tokens are issued by the operator, not by the browser ([`deployment.md`](deployment.md) §6 step 2). The seeded synthetic users are `demo-staff-a` / `demo-admin-a` (clinic `default`) and `demo-admin-b` (`demo-clinic-b`).

1. Open `/staff` and paste a `demo-staff-a` token. The token stays in browser memory only.
2. Expected: the `default` clinic's queue lists the intake from step 1 as **Needs review** with reason `emergency_signal`.
3. Open it: the structured output, report and safety result are shown. The staff API does not return the stored raw intake record (`intake_json`), but structured fields can still contain parts of the original text (in mock mode `chief_complaint` is its first 200 characters).
4. Mark it **Reviewed** (or **Escalated**). Expected: the status changes and the transition buttons are replaced by "Only intakes that need review can be marked reviewed or escalated." The API itself rejects any further transition of that intake with HTTP 409 (only `needs_review` can be resolved).
5. With a `demo-admin-b` token, the `default` clinic's queue is not accessible (403) and `demo-clinic-b`'s queue does not contain the intake.

## 3. Signed webhook (operator)

Each newly stored `needs_review` intake sends one HMAC-signed POST to the configured receiver, with only `event`, `schema_version`, `idempotency_key`, `intake_id` and `clinic_id`. The operator verifies it with `scripts/verify_webhook.py` ([`deployment.md`](deployment.md) §6 step 4).

## 4. Scripted version

`python -m scripts.hosted_check --api https://healthcare-ai-api-tovn.onrender.com` (with `STAFF_A_TOKEN` and `STAFF_B_TOKEN` set) runs steps 1–2 non-interactively and prints `[PASS]`/`[FAIL]` per check. Result on 2026-10-09: 8/8 PASS, exactly one webhook, `VALID signature` ([`deployment.md`](deployment.md) §7).

## What this demo does not show

Real LLM output (the hosted demo runs in mock mode), retrieval (not wired into the API), real patient data, or any production or compliance property. See [`project_status.md`](project_status.md).
