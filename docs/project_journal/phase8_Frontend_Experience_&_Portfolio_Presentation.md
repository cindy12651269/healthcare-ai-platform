# Phase 8 — Frontend Experience & Portfolio Presentation

Healthcare AI Platform
Timeline: Phase 8 (from 2026-10-14)
Scope: Issue #67 (item 1 of 7) so far
Status: In progress — #67 implemented and validated on the hosted demo on 2026-10-14 (§2); PR open, not merged.

---

## 1. Phase Goal

Make the public demo safe, predictable and presentable before later Phase 8 UI work is verified on it. #67 comes first because later issues verify on the hosted demo.

---

## 2. Issue 67 — Safe Public Demo: Webhook Isolation, Cold Start & Demo Data Lifecycle

**Delivered (configuration, frontend and docs; no backend code, API, auth, RBAC or clinic-isolation change):**

* **Webhook isolation.** `WEBHOOK_URL` was deleted from the hosted API's environment by the account owner on 2026-10-14 and the API redeployed (*Save and deploy*); `WEBHOOK_SECRET` kept. Escalation delivery is therefore `disabled` (`api/webhook.py` `_config()`): no network call, no `webhook_deliveries` row. Chosen over a controlled receiver because it has no side effects by construction and needs no extra service or secret. Runbook and verification: [`deployment.md`](../deployment.md) §9.1. No receiver URL or secret is recorded anywhere in the repository.
* **Cold start.** `waitForApi` (`app/services/api.ts`) polls the existing `GET /health` (6 attempts, 15 s timeout, at most one attempt per 15 s, so ~75–105 s even when attempts fail instantly); `ApiStatus` (`app/components/ApiStatus.tsx`) on `/`, `/intake`, `/staff` and `/system-card` shows *"Waking the demo server (can take up to a minute)"* with the attempt count, then *"Demo server is awake"*, or an actionable failure with *Try again*. The landing page starts the wake-up while the visitor reads.
* **Staff-access policy.** The `/staff` sign-in page and the landing page's Staff entry state that tokens are issued on request by the demo operator and never published; no public token endpoint, guest login or shared password. Visitors are pointed to the patient intake and system card.
* **Demo-data lifecycle.** [`deployment.md`](../deployment.md) §9.4: database created on or before 2026-10-09, expires **no later than 2026-11-08**; how to check expiry, recreate (Blueprint sync + manual deploy → migrate + seed), re-seed, and a live-link check before sharing.

### 2a. Hosted validation (2026-10-14)

API https://healthcare-ai-api-tovn.onrender.com, `main` build of Phase 7 (the #67 frontend is not deployed yet, §3). All times UTC (Taiwan time = UTC+8).

**Isolation established before any flagged submission.** `/health` → `{"status":"ok","environment":"demo","llm_mode":"mock"}`. A non-flagged synthetic probe (unique text, locally confirmed `submitted` in mock mode) was submitted at 08:08:31 and stored as `submitted` (record `ce204004c1d846b9a40d5e5c317a78f6`). The owner confirmed the API log at 08:08:32: `Escalation webhook disabled: WEBHOOK_URL and WEBHOOK_SECRET (>= 32 chars) are both required`. Only then were flagged presets submitted.

**The four presets** (exact texts from `app/services/demo.ts`, same request body as the UI: `consent_granted`, `source: web`, `input_type: intake`; submitted via the API, not the browser):

| Preset | Submitted | HTTP | `review_status` | Reasons | Safety actions | Persistence | Timeline events | `webhook_delivery` events | Clinic B timeline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| routine | 08:21:26 | 200 | `submitted` | — | — | `duplicate` (text stored in Phase 7, 2026-10-13) | — | — | — |
| routine probe | 08:08:31 | 200 | `submitted` | — | — | saved `ce204004…` | submitted, processed, safety_evaluated, escalation_decision | 0 | 403 |
| emergency | 08:21:26 | 200 | `needs_review` | `emergency_signal` | `add_emergency_guidance` | saved `0edbaf66641b48bdb73046023b7559b0` | same four | **0** | 403 |
| prescription | 08:21:27 | 200 | `needs_review` | `blocked_prescription` | `block_prescription` | saved `f0508a5123be4fea93fa649a28e940d8` | same four | **0** | 403 |
| vague | 08:21:27 | 200 | `needs_review` | `low_confidence` (confidence 0.1) | — | saved `d0d89533841744278aa03f20592b04f3` | same four | **0** | 403 |

* Stored records (detail as `demo-staff-a`): clinic `default`, `review_status` and `escalation_reason` as in the table. The timeline checks read event **kinds** only: the `escalation_decision` event's `details` (`required`, `reasons`) were not read (the check script looked for them at the wrong level and got no value), so the reasons above are evidenced by the ingest response and the stored record's `escalation_reason`, not by the timeline event.
* **Webhook state: `disabled` for every new intake.** No `webhook_delivery` event in any new timeline. Control: the Phase 6 acceptance intake (`77c8cd97…`, 2026-10-09) still shows its one historical `webhook_delivery` event, so the timeline does list deliveries when a row exists.
* **Matches CI and the system card.** Identical to `tests/test_demo_seed_intakes.py::test_scenario_presets_produce_the_documented_outcomes` (routine `submitted` / emergency `emergency_signal` / prescription `blocked_prescription` / vague `low_confidence`, all `needs_review`) and consistent with the preset expectations on the landing page and the escalation rules the system card serves (low-confidence threshold 0.5), compared against the committed code; the hosted `/api/system-card` was not fetched in this run.

**`scripts/hosted_check.py`** at 08:30:17 with 1-hour operator-issued tokens for `demo-staff-a` and `demo-admin-b`: all 8 checks `[PASS]` (health, mock mode, intake accepted, flagged `emergency_signal`, persisted, in clinic `default` queue, **403** for clinic B, absent from clinic B queue). Intake `2f005d14d0fc4de1acc4879d586481a3`: `needs_review`, `emergency_signal`, no `webhook_delivery` event, clinic B timeline 403. The script's closing line ("Expect one webhook at the receiver …") does not apply while delivery is disabled.

**Token handling.** Tokens were generated by the owner locally (secrets entered at hidden prompts, written to an owner-only `0600` file outside the repository, nothing printed), read by the checks from the environment without being printed, and the file was deleted after the run. No token, secret or connection string appears in the repository, the logs quoted here or the chat.

**Frontend checks** (branch `feat/issue-67-safe-public-demo`): `vitest` 76 passed (new `ApiStatus.test.tsx`: slow → OK, slow → fail with retry, fast-failure pacing, hanging attempt timeout, cancel; staff-access policy tests), `eslint` clean, `tsc --noEmit` clean, `next build` succeeded. Bundle scan of `.next/static` and `.next/server/pages` (84 files, built with the hosted `NEXT_PUBLIC_API_BASE_URL`): no `AUTH_TOKEN_SECRET`, `WEBHOOK_SECRET`, `WEBHOOK_URL`, `OPENAI_API_KEY`, `DATABASE_URL` or `POSTGRES_PASSWORD`, no receiver/database URL, API key or bearer token; the only host is the public API URL. Backend `pytest`: 237 passed, 11 skipped (PostgreSQL-only tests; no local PostgreSQL).

### 2b. Limitations and follow-ups

* **The #67 frontend is not on the hosted demo yet.** Cold-start and staff-policy UI are verified by tests and a production build only. After merge, the frontend needs *Manual Deploy* (Render `autoDeployTrigger` is off); then confirm the waking notice on a cold `/`.
* **Log evidence for flagged submissions.** The `disabled` warning was confirmed in the API logs for the routine probe (08:08:32). Equivalent lines for the three flagged presets (08:21:26–27) and the `hosted_check` intake (08:30:17) are expected; the timelines (no delivery row) are the recorded evidence for them.
* Presets were submitted through the API with the UI's exact request body, not by clicking in the browser.
* The routine preset text was a `duplicate` on the hosted database (de-duplicated by `input_hash`), so its own timeline could not be checked; the unique routine probe covers that path.
* Four new synthetic intakes (three presets + `hosted_check`) and the probe now sit in clinic `default`'s queue; they are disposable and disappear when the database is recreated.
* The database's exact creation and expiry dates were not read from the dashboard in this session; the runbook states the upper bound (2026-11-08).
* Out of scope, recorded as options only: paid database (no expiry), paid instances (no cold start), rate limiting the public intake endpoint.
