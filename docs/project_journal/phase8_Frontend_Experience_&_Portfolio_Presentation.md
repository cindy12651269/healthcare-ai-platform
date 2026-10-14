# Phase 8 — Frontend Experience & Portfolio Presentation

Healthcare AI Platform
Timeline: Phase 8 (from 2026-10-14)
Scope: Issue #67 (item 1 of 7) so far
Status: In progress — #67 closed (2026-10-14): PR #74 merged (`f84a1da`, `main` CI run 38537057498 — success); hosted API validated (§2a) and hosted frontend deployed and verified (§2c).

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

* ~~The #67 frontend is not on the hosted demo yet.~~ Resolved: deployed from `f84a1da` and verified on 2026-10-14 (§2c).
* **Log evidence for flagged submissions.** The `disabled` warning was confirmed in the API logs for the routine probe (08:08:32). Equivalent lines for the three flagged presets (08:21:26–27) and the `hosted_check` intake (08:30:17) are expected; the timelines (no delivery row) are the recorded evidence for them.
* Presets were submitted through the API with the UI's exact request body, not by clicking in the browser.
* The routine preset text was a `duplicate` on the hosted database (de-duplicated by `input_hash`), so its own timeline could not be checked; the unique routine probe covers that path.
* Four new synthetic intakes (three presets + `hosted_check`) and the probe now sit in clinic `default`'s queue; they are disposable and disappear when the database is recreated.
* The database's exact creation and expiry dates were not read from the dashboard in this session; the runbook states the upper bound (2026-11-08).
* Out of scope, recorded as options only: paid database (no expiry), paid instances (no cold start), rate limiting the public intake endpoint.

### 2c. Hosted frontend verification (2026-10-14)

**Deploy.** PR #74 merged with a merge commit (`f84a1da`, reviewed head `9c77172`; PR CI and `main` CI run 38537057498 — success). Frontend *Manual Deploy* by the account owner: source commit `f84a1da`, *Live* at 16:46 Taiwan time (08:46 UTC). The API was not redeployed (no backend change) and was not restarted for this check.

**Served pages and bundle** (`curl`, 08:48 UTC): `/`, `/intake`, `/staff`, `/system-card` → 200. The prerendered HTML of `/` contains the Staff entry text *"Needs an access token issued on request by the demo operator."*; `/staff` contains the *"Visiting the public demo?"* card (*"issued on request by the demo operator and are never published: there is no public sign-up, guest login or shared password"*) above *Staff sign-in*. The 16 deployed JS chunks reference only `https://healthcare-ai-api-tovn.onrender.com` (no `localhost:8000` fallback), contain the reviewed cold-start strings (*"Waking the demo server"*, *"Demo server is awake"*, *"We kept checking for over a minute"*), and no secret names, receiver/database URLs, keys or bearer tokens.

**Live cold start (observed in Chrome, not forced).** The API had been idle since 08:30 UTC (the `hosted_check` run). Opening `/` at about 08:49 UTC:

| Time (UTC) | Banner |
| --- | --- |
| 08:49:08–17 | *"Waking the demo server (can take up to a minute)." … "(attempt 1 of 6)"* (screenshot 01) |
| 08:49:32 | same, *"attempt 2 of 6"* (attempt 1 had ended without success) |
| 08:49:47 | *"Demo server is awake."* (screenshot 02) |

Network log of that session: `GET https://healthcare-ai-api-tovn.onrender.com/health` → **503**, then → **200** (exactly two cold-session requests captured). Verified: the deployed component recovered from a 503 during the cold start, retried within its bounds and reached *"Demo server is awake"*. Not determinable: tracking started while attempt 1 was in flight, so it is unknown whether attempt 1 is the captured 503 (then attempt 2 was held until the instance was up and returned 200) or timed out uncaptured (then attempt 2 was the 503 and attempt 3 the 200). Per-request timestamps were not captured, so the timeout path and the spacing after the 503 were not measured on the hosted demo.

**Warm behaviour.** Reloading `/` and opening `/staff` with the API awake: one `GET …/health` → 200 per page, no banner (screenshot 03 for `/staff`). Without a token `/staff` makes no other API call.

**Evidence:** [`evidence/phase8_issue67_hosted_frontend_2026-10-14/`](evidence/phase8_issue67_hosted_frontend_2026-10-14/) — `01-cold-start-waking-attempt-1-of-6.jpg`, `02-cold-start-demo-server-awake.jpg`, `03-staff-access-policy.jpg`. No token, secret or personal data visible.

**Not verified on the hosted demo:**

* The **failure state** (*"The demo server did not respond"* + *Try again*): it needs the API to stay down for the whole ~75–105 s window, which was not induced (no forced restart or outage). Covered by `app/tests/ApiStatus.test.tsx` only.
* The waking notice on `/intake` and `/system-card` (same component; observed on `/` only).
* A cold start longer than the observed ~40 s, and behaviour on mobile browsers.
* `/intake` makes a second `/health` call for the LLM-mode badge (pre-existing); not a functional issue.

**Verdict for #67 on the hosted demo:** webhook isolation, the four presets, `hosted_check`, staff-access messaging, the correct API host and the waking → awake path are verified; the failure state is test-only.
