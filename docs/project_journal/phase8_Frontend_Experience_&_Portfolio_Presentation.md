# Phase 8 — Frontend Experience & Portfolio Presentation

Healthcare AI Platform
Timeline: Phase 8 (from 2026-10-14)
Scope: Issues #67–#71 (items 1–5 of 7) so far
Status: In progress — #67 closed (2026-10-14): PR #74 merged (`f84a1da`, `main` CI run 38537057498 — success); hosted API validated (§2a) and hosted frontend deployed and verified (§2c). #68 closed (2026-10-14): PR #76 merged (`ba028df`); hosted frontend verified on the public pages (§3c), signed-in staff workspace pending a token. #69 closed (2026-10-14): PR #78 merged (`24d2a6b`); hosted dashboard and system card verified (§4c). #70 closed (2026-10-15): PR #80 merged (`8f6e963`); hosted intake verified with webhook isolation confirmed first (§5d). #71 closed (2026-10-15): PR #82 merged (`7585f84`); hosted staff workspace verified with short-lived tokens (§6d); the seeded-reference defect was fixed in #84 (PR #85, `1ed0b4a`) and verified on the hosted demo (§6f).

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

---

## 3. Issue 68 — Design System, App Shell & Responsive Layout

**Status:** closed (2026-10-14): PR #76 merged (`ba028df`, reviewed head `8231d9e`; `main` CI run 38543008087 — success); frontend deployed and verified on the hosted demo (§3c), signed-in staff workspace pending. No API, backend, auth, RBAC, clinic-isolation or workflow change; no new dependency (`app/package.json` unchanged).

**Delivered:**

* **Tokens** (`app/styles/tokens.css`): colour palette with semantic status colours (submitted, needs review, reviewed, escalated, blocked, emergency, neutral), type scale, spacing, radius, elevation, reading (832 px) and workspace (1248 px) widths; light and dark themes. Decision: plain CSS, [ADR-10](../decisions.md).
* **AppShell** (`app/components/AppShell.tsx`): brand, primary navigation (`aria-current`), skip link, persistent *"Demo · synthetic data · mock mode"* indicator, footer, document title and viewport. All four pages render through it; the per-page header/footer markup and `SiteNav.tsx` are removed. The intake page's live *LLM Mode* badge is passed into the shell's indicator bar.
* **Responsive navigation:** horizontal from 768 px; below that a *Menu* button (`aria-expanded`, `aria-controls`) collapses it; Escape closes it and returns focus to the button; following a link closes it.
* **Components** (`app/components/ui/`): `Button` (primary/secondary/danger/ghost, sm/md), `Card`, `Alert`, `StatusBadge`, `ReasonLabel`/`ReasonList` (label + visible code; splits the stored comma-separated `escalation_reason`), `PageHeader`, `DataTable` (scrolls inside a labelled, focusable region, or stacks rows as labelled blocks below 768 px), `EmptyState`, `Spinner`/`Skeleton`/`LoadingMessage`.
* **Where statuses and reasons now use the shared components:** staff queue (status + reason columns), intake detail (status, escalation reason), *Why flagged* rules, timeline *escalation decision* reasons, system-card escalation rules.
* **Widths:** `/intake` and `/system-card` reading width; `/` and `/staff` workspace width, with two-column grids at ≥ 1280 px (landing workflow + scenarios; staff access policy + sign-in). The staff queue/detail side-by-side layout is left to #71.
* **Accessibility basics:** visible `:focus-visible` ring (focus colour ≥ 3:1 in both themes), 44 px minimum height for buttons, nav links, inputs and selects, `prefers-reduced-motion` disables spinner/skeleton animation and transitions.

**Statuses and reasons, everywhere they appear:** the staff queue, intake detail, *Why flagged*, timeline *escalation decision* reasons and *staff action* statuses (from → to), and the system-card escalation rules all use `StatusBadge` / `ReasonLabel`. Not in scope for these components: safety *guard action* codes (`add_emergency_guidance`, …), which are not review statuses or escalation reasons, and the prose preset expectations on the landing page (copy owned by #70).

**Tests:** `app/tests/ui.test.tsx` (30 new: variants, roles, accessible names, reason/status mapping, DataTable, AppShell nav/indicator/widths, keyboard menu toggle + Escape). 106 total. All 76 existing tests pass; one assertion was updated deliberately: the timeline staff-action line in `StaffReview.test.tsx` now expects the readable labels (*"admin-a: Needs review → Escalated"*) and checks both recorded codes via `data-status`, instead of the raw `needs_review → escalated` text. `npm run lint`, `typecheck`, `test`, `build` pass locally.

**Contrast** (token pairs, WCAG 2.x formula, computed from `tokens.css`; 47 pairs × 2 themes, 0 failures; text ≥ 4.5:1, focus ring / control borders / primary ≥ 3:1):

| Pair | Min | Light | Dark |
| --- | --- | --- | --- |
| `--color-text` on `--color-bg` | 4.5:1 | 14.72 | 15.56 |
| `--color-text` on `--color-surface` | 4.5:1 | 15.93 | 13.82 |
| `--color-text` on `--color-surface-sunken` | 4.5:1 | 14.16 | 14.91 |
| `--color-text-muted` on `--color-bg` | 4.5:1 | 6.24 | 8.77 |
| `--color-text-muted` on `--color-surface` | 4.5:1 | 6.76 | 7.79 |
| `--color-text-muted` on `--color-surface-sunken` | 4.5:1 | 6.01 | 8.40 |
| `--color-link` on `--color-surface` | 4.5:1 | 7.06 | 9.17 |
| `--color-link` on `--color-bg` | 4.5:1 | 6.52 | 10.32 |
| `--color-on-primary` on `--color-primary` | 4.5:1 | 5.96 | 7.54 |
| `--color-on-primary` on `--color-primary-hover` | 4.5:1 | 7.92 | 9.36 |
| `--color-on-danger` on `--color-danger` | 4.5:1 | 6.57 | 8.03 |
| `--color-on-danger` on `--color-danger-hover` | 4.5:1 | 8.83 | 10.14 |
| `--color-danger` on `--color-surface` | 4.5:1 | 6.57 | 7.21 |
| `--color-text` on `--color-highlight` | 4.5:1 | 14.16 | 9.28 |
| `--color-focus` on `--color-surface` | 3:1 | 5.84 | 8.13 |
| `--color-focus` on `--color-bg` | 3:1 | 5.39 | 9.16 |
| `--color-border-strong` on `--color-surface` | 3:1 | 3.49 | 4.00 |
| `--color-border-strong` on `--color-bg` | 3:1 | 3.22 | 4.51 |
| `--color-primary` on `--color-surface` | 3:1 | 5.96 | 6.96 |
| `--status-neutral-fg` on `--status-neutral-bg` | 4.5:1 | 7.95 | 9.05 |
| `--status-neutral-fg` on `--color-surface` | 4.5:1 | 8.94 | 10.21 |
| `--color-text` on `--status-neutral-bg` | 4.5:1 | 14.16 | 12.25 |
| `--color-text-muted` on `--status-neutral-bg` | 4.5:1 | 6.01 | 6.90 |
| `--status-info-fg` on `--status-info-bg` | 4.5:1 | 7.14 | 8.45 |
| `--status-info-fg` on `--color-surface` | 4.5:1 | 8.20 | 9.23 |
| `--color-text` on `--status-info-bg` | 4.5:1 | 13.88 | 12.66 |
| `--color-text-muted` on `--status-info-bg` | 4.5:1 | 5.89 | 7.13 |
| `--status-warning-fg` on `--status-warning-bg` | 4.5:1 | 6.99 | 9.39 |
| `--status-warning-fg` on `--color-surface` | 4.5:1 | 7.63 | 10.19 |
| `--color-text` on `--status-warning-bg` | 4.5:1 | 14.60 | 12.74 |
| `--color-text-muted` on `--status-warning-bg` | 4.5:1 | 6.20 | 7.18 |
| `--status-success-fg` on `--status-success-bg` | 4.5:1 | 6.58 | 8.96 |
| `--status-success-fg` on `--color-surface` | 4.5:1 | 7.42 | 9.84 |
| `--color-text` on `--status-success-bg` | 4.5:1 | 14.13 | 12.60 |
| `--color-text-muted` on `--status-success-bg` | 4.5:1 | 6.00 | 7.10 |
| `--status-escalated-fg` on `--status-escalated-bg` | 4.5:1 | 8.09 | 9.01 |
| `--status-escalated-fg` on `--color-surface` | 4.5:1 | 9.48 | 9.21 |
| `--color-text` on `--status-escalated-bg` | 4.5:1 | 13.61 | 13.53 |
| `--color-text-muted` on `--status-escalated-bg` | 4.5:1 | 5.77 | 7.62 |
| `--status-blocked-fg` on `--status-blocked-bg` | 4.5:1 | 7.23 | 8.74 |
| `--status-blocked-fg` on `--color-surface` | 4.5:1 | 8.29 | 8.76 |
| `--color-text` on `--status-blocked-bg` | 4.5:1 | 13.89 | 13.79 |
| `--color-text-muted` on `--status-blocked-bg` | 4.5:1 | 5.89 | 7.77 |
| `--status-emergency-fg` on `--status-emergency-bg` | 4.5:1 | 6.88 | 8.44 |
| `--status-emergency-fg` on `--color-surface` | 4.5:1 | 7.87 | 8.59 |
| `--color-text` on `--status-emergency-bg` | 4.5:1 | 13.93 | 13.59 |
| `--color-text-muted` on `--status-emergency-bg` | 4.5:1 | 5.91 | 7.65 |

47 pairs × 2 themes; failures: 0

### 3a. Local responsive and accessibility validation (2026-10-14)

**Setup.** Production build (`next build` + `next start`) of the branch against a local **synthetic fixture API** (`fixtures-server.mjs`: fixed JSON for `/health`, `/api/system-card` — generated from the committed `system_card()` handler — and the staff endpoints, with synthetic intakes for clinic `default`). The fixture server accepts any bearer string; sign-in used the placeholder `synthetic-fixture-not-a-token`. **No real token was generated or used** and no hosted service was called. Headless Chrome driven over the DevTools Protocol (`capture-cdp.mjs`, no dependency): viewport width × `prefers-color-scheme` emulated, locale `en-US`, timezone UTC, device scale 1.

**Matrix:** 5 views (`/`, `/intake`, `/system-card`, `/staff` signed out, `/staff` signed in with an intake open) × 390 / 768 / 1280 / 1440 px × light / dark = **40 full-page screenshots** plus 3 interaction shots. Results per run in `measurements.json`.

| Check | Method | Result |
| --- | --- | --- |
| Horizontal page overflow | `scrollWidth − clientWidth` and any element past the viewport (outside table scroll regions) | **0 px in all 40 runs** |
| Tables | DataTable regions | Queue, demo-staff and safety tables stack below 768 px; none scrolls at ≥ 768 px |
| Touch targets | every visible link/button/input/select/textarea/summary except inline text links; checkbox measured by its label | **No target under 44 × 44 px in all 40 runs** (after fixes below) |
| Mobile nav (390 px) | real key events | Collapsed by default (`display: none`); Tab order skip link → brand → *Menu*; Enter opens (`aria-expanded="true"`); next Tab focuses *Guided demo*; links 358 × 44 px; Escape closes and returns focus to *Menu* |
| Desktop nav (1280 px) | computed style | Horizontal nav visible, *Menu* hidden |
| Focus visibility | computed style of the focused element | 3 px solid focus ring on every element tabbed (`#1f5fcf` light, `#8ab8ff` dark) |
| Reduced motion | `prefers-reduced-motion: reduce` | Spinner animation duration 0.01 ms |
| Contrast | token pairs (table above) | 0 failures; screenshots show no low-contrast text on review |

**Defects found and fixed in this pass:**

* `btn-sm` (scenario presets, queue *Open* buttons) was 36 px tall at ≥ 768 px → now 44 px at all widths (smaller text only). Skip link 41 → 44 px.
* Card `h3` headings in the intake detail sat flush against the preceding list (`margin-top: 0`) → spacing restored.
* System-card evaluation table hid two columns behind horizontal scroll at 390 px → stacked layout.
* Stacked-table label column (9 rem) squeezed reason pills at 390 px, breaking `blocked_prescription` mid-word → 6.5 rem.
* Timeline staff-action statuses now use `StatusBadge` (acceptance criterion: shared components everywhere).

**Evidence:** [`evidence/phase8_issue68_responsive_2026-10-14/`](evidence/phase8_issue68_responsive_2026-10-14/) — `{landing,intake,system-card,staff-signin,staff-workspace}-{390,768,1280,1440}-{light,dark}.jpg`, `nav-mobile-open-390-light.jpg`, `focus-visible-nav-link-390-light.jpg`, `focus-visible-signin-button-1280-dark.jpg`, `measurements.json`, and the two scripts. All data shown is synthetic; no token is visible.

### 3b. Limitations

* ~~Hosted visual validation: pending.~~ Resolved for the public pages on 2026-10-14 (§3c); the signed-in staff workspace remains validated on synthetic fixtures only.
* Chrome only (headless, emulated viewports, not physical devices); Safari/Firefox and 200 % zoom are #72.
* Contrast verified on token pairs plus visual review, not per-element with a scanner.
* The *"mock mode"* text in the indicator is static (hosted demo and CI run mock only); a locally run real-mode API still shows the live *LLM Mode: Real* badge on `/intake`.
* Dates use the browser locale (`toLocaleString`, pre-existing); explicit locale/timezone formatting is #71. Screenshots pin `en-US`/UTC.
* Theme follows the OS setting; there is no in-app toggle.

### 3c. Hosted frontend verification (2026-10-14)

**Deploy.** PR #76 merged with a merge commit (`ba028df`, reviewed head `8231d9e`; PR CI and `main` CI run 38543008087 — success). Frontend *Manual Deploy* by the account owner: source commit `ba028df`, *Live* at about 17:38 Taiwan time (09:38 UTC). The API was not redeployed (no backend change) and was not restarted for this check. No Render setting was changed.

**Served build** (`curl`, 09:41 UTC): `/`, `/intake`, `/staff`, `/system-card` → 200. Every page's HTML contains the *"Demo · synthetic data · mock mode"* indicator, the skip link and the menu toggle (`aria-controls="site-nav"`); the pre-#68 *"Demo · synthetic data only"* badge is gone. `/` and `/staff` contain the #67 wording *"issued on request by the demo operator"*; `/` contains the demo staff table (`NEXT_PUBLIC_DEMO_MODE` on). API `GET /health` → 200 in 0.2 s (`environment: demo`, `llm_mode: mock`).

**Responsive matrix (hosted, 09:42:14–09:42:38 UTC).** Same headless-Chrome DevTools-Protocol method as §3a (`capture-cdp-hosted.mjs`), pointed at `https://healthcare-ai-frontend-1s23.onrender.com`: 4 public views (`/`, `/intake`, `/system-card`, `/staff` signed out) × 390 / 768 / 1280 / 1440 px × light / dark = **32 runs**, locale `en-US`, timezone UTC. Each page waited for live API data before measuring (`/intake`: the *LLM Mode* badge from `/health`; `/system-card`: the evaluation table from `/api/system-card`). The harness sends **no bearer token** and performs no sign-in.

| Check | Result (hosted) |
| --- | --- |
| Horizontal page overflow | **0 px in all 32 runs** |
| Touch targets ≥ 44 × 44 | **No smaller target in any run** |
| Demo indicator | Present with the exact text on **32/32** runs |
| Tables | Demo-staff and system-card evaluation tables stack at 390 px; none scrolls at any width |
| Mobile nav (390 px) | Collapsed by default; Tab order skip link → brand → *Menu*; Enter opens; next Tab focuses *Guided demo*; links 358 × 44 px; Escape closes and returns focus to *Menu* |
| Desktop nav (1280 px) | Horizontal, *Menu* hidden |
| Focus visibility | 3 px solid ring (`#1f5fcf` light on *Guided demo*, `#8ab8ff` dark on *Sign in*) |
| Reduced motion | Spinner animation 0.01 ms |
| #67 staff-access card | Above *Staff sign-in* on **8/8** `/staff` runs |

**#67 cold-start integration.** Observed warm only: the API answered `/health` at once, so no notice was rendered on any of the 32 runs (expected: `ApiStatus` renders nothing when the first check is fast). The owner reported seeing the waking notice *"(attempt 1 of 6)"* in the new shell on the hosted homepage just after the deploy; that observation is the owner's, with no screenshot in this folder. No restart was forced to reproduce it.

**Evidence:** [`evidence/phase8_issue68_hosted_frontend_2026-10-14/`](evidence/phase8_issue68_hosted_frontend_2026-10-14/) — `{landing,intake,system-card,staff-signin}-{390,768,1280,1440}-{light,dark}.jpg`, `nav-mobile-open-390-light.jpg`, `focus-visible-nav-link-390-light.jpg`, `focus-visible-signin-button-1280-dark.jpg`, `measurements.json`, `capture-cdp-hosted.mjs`. No token, secret or personal data visible.

**Not verified on the hosted demo:**

* **Signed-in staff workspace** (queue, status badges, reason labels, detail, timeline, FHIR panel): **pending**. No securely issued short-lived token was available for this check, and none was generated. Covered on a local production build with synthetic fixtures (§3a) and by unit tests.
* The cold-start waking → awake sequence in the new shell, beyond the owner's report above; the failure state remains test-only (§2c).
* Physical devices, Safari/Firefox and 200 % zoom (#72).

**Verdict for #68 on the hosted demo:** the deployed build is `ba028df`; all four public pages pass the overflow, touch-target, indicator, navigation, focus and reduced-motion checks at all four widths in both themes, and the #67 staff-access messaging is intact. Only the signed-in staff workspace is still pending hosted validation.

---

## 4. Issue 69 — Product Dashboard & AI Transparency

**Status:** closed (2026-10-14): PR #78 merged (`24d2a6b`, reviewed head `758fb37`; `main` CI run 38547619614 — success); frontend deployed and verified on the hosted demo (§4c). No backend change, no new endpoint, no API-contract, auth, RBAC, clinic-isolation or workflow change; no new dependency (`app/package.json` unchanged).

**Delivered:**

* **Dashboard** (`app/pages/index.tsx`, replaces the guided-demo landing; nav label *Dashboard*): product statement and value proposition; CTAs *Try Patient Intake* (`/intake`) and *Explore Staff Workflow* (`/staff`) with the #67 token note; the seven-stage workflow (Patient intake → Structuring → Report + safety guard → Escalation rules → Clinic review queue → Evidence timeline → FHIR R4 export) as a CSS stepper, each stage labelled *Implemented* / *Mock mode* / *Demo limit*; the **signed webhook as a dashed conditional branch of the escalation step**, not a step (*"only when a receiver is configured"*, *"Disabled on the hosted demo"*).
* **Live system status** (`app/components/SystemStatus.tsx`): API reachable/unreachable, `environment` and `llm_mode` exactly as `GET /health` reports them (*Not reported* if absent, *Unknown* unless `/health` answered `ok`); checking → waking (attempt *n* of *m*) → ready / unavailable with *Try again*. It reuses the #67 state machine, now the `useApiReadiness` hook in `ApiStatus.tsx` (behaviour unchanged; all #67 tests pass), and `waitForApi` gained an optional `onHealth` callback (backward compatible). It is the dashboard's **only** `/health` poller; the separate #67 banner is not rendered there.
* **What is real vs. mock** panel: hosted demo and CI run mock mode; mock structuring is rule-based, report text from a deterministic builder; real mode is opt-in OpenAI, not run in CI or on the hosted demo; RAG not connected to the API; embeddings are SHA-256 mock vectors; safety rules and staff review are implemented within the system card's limits; and a *not claimed* statement (not a medical device, not clinically validated, no clinical-accuracy, HIPAA or other compliance claim, not production-ready).
* **Capability cards** (content in `app/services/evidence.ts`): clinic-scoped RBAC, rule-based safety guard, escalation and human review, evidence timeline, FHIR R4 export, signed webhook, CI-gated evaluation. Each has a status taken from `docs/project_status.md` §3, its limits, and evidence links to system-card sections or committed docs/tests.
* **System card** (`app/pages/system-card.tsx`): section navigation; a prominent *Known limitations* section first; pipeline and safety rules as responsive card grids; escalation rules with `ReasonLabel` plus the review rule (only `needs_review` → `reviewed`/`escalated`) linked to `review_queue_api.md`; evaluation as stat tiles plus a stacked per-category table showing *matches/cases · rate*, each suite's caveat in a warning note, and the snapshot source. Values missing from the response read *Not reported*.
* **Demo access:** the #67 wording is kept on the dashboard; the demo staff identities table stays behind `NEXT_PUBLIC_DEMO_MODE`.

**Evaluation metric provenance.** The dashboard shows **no metrics**. Every number on the system card is read at runtime from `GET /api/system-card` → `evaluation`, which the API serves unchanged from the committed `evaluation/system_card_results.json` (`evaluation/system_card.py::load_results`). That file is generated by `python -m evaluation.system_card` and `tests/test_system_card.py` fails CI if it drifts from the suites. Values shown (from the snapshot, not typed into the UI): safety & escalation (#32, mock) 16 synthetic cases, guard 16/16 (1.00), escalation 16/16 (1.00), 3 known gaps, four categories of 4 cases each; extraction (#40, mock, `deterministic_rule_based_baseline`) 6 cases, micro/macro precision and recall 1.00, 9 true positives, 0 false positives, 0 missed — each with the snapshot's own caveat (agreement with a labelled baseline / in-sample). `tests/SystemCard.test.tsx` compares every rendered value with the committed file and checks that missing values are not filled in.

**Wording review against `docs/project_status.md` §3:**

| Item | Finding | Action |
| --- | --- | --- |
| Hero headline | First draft said intake "reaches clinic staff *safely*", implying a safety guarantee | Reworded to "rule-checked and routed to clinic staff for human review" |
| Numbers on the dashboard | First draft had hard-coded case counts, gap count and the 0.5 threshold | Removed; numbers appear only on the system card, from the snapshot. A test fails if the dashboard shows a decimal metric or percentage |
| Clinic-scoped RBAC status | Labelled *Complete*, but the card covers RBAC (**COMPLETE**) and tenant isolation (**PARTIAL**) | Status *RBAC complete · isolation partial*; limits note one seeded clinic and no SSO |
| Safety guard, escalation | Matrix: **COMPLETE (rule-based scope)** | Same status; limits say keyword/regex rules and recorded gaps |
| Evidence timeline, FHIR, webhook, evaluation | Matrix: **PARTIAL** (explainability; export only; integration; AI/LLM evaluation) | Shown as *Partial* with the matrix's limits (no stage timings/citations; no FHIR server; single receiver, no resend, disabled on hosted; mock-only tiny sets, in-sample) |
| Webhook wording | Must not read as unconditional or as a delivery guarantee | Dashboard: drawn as a conditional branch; the capability card opens *"When a receiver is configured, …"*; the timeline lists *"any webhook delivery attempts"*. System card: the API's stage text (*"escalated intakes trigger a signed, PHI-free webhook"*) is qualified **inside that stage card** with a *Conditional* tag (*"Sent only when a receiver is configured on the server; disabled on the hosted demo. Not a delivery guarantee."*). **Not fixed at the source**: changing `api/routers/system_card.py` is a backend change, out of scope |
| Real mode, RAG, embeddings | Matrix: OpenAI opt-in, never in CI; RAG not wired; mock embeddings | Stated as such in the real-vs-mock panel |
| Forbidden claims | No clinical validation, accuracy, HIPAA/compliance or production-readiness claim | Stated as *not claimed*; a test rejects positive compliance/accuracy phrases on the dashboard |

**Tests.** `app/tests/Dashboard.test.tsx` (new, 34 including one per evidence path):
* `waitForApi` health info.
* `SystemStatus`: healthy mock, healthy real, missing fields, unreachable → *Try again* → ready, a 502 cold start showing *attempt 2 of 3* then ready, and the slow first check.
* Dashboard: a single `/health` poller and the CTAs; seven stages in order with the webhook as a branch of escalation; the real-vs-mock statements and forbidden-claim guard; the webhook card is conditional; seven capability cards with links.
* Every repository evidence path exists and every `#anchor` matches a heading (GitHub slug rules); system-card anchors exist.
* Demo-mode gating and the #67 wording.

`app/tests/SystemCard.test.tsx` was updated: exact committed values per category and total, stats, caveats, source, *Not reported* for missing data, section navigation, the review rule, and the webhook qualifier inside the stage that states it. The two landing tests that lived there moved to `Dashboard.test.tsx`. Total **140 passed**. `npm run lint`, `typecheck`, `test` and `build` pass locally.

### 4a. Local browser validation (2026-10-14)

Production build against the synthetic fixture API (§3a method; the system-card payload is generated from the committed handler; any bearer string accepted, placeholder only, no real token). Headless Chrome over DevTools Protocol, `en-US`/UTC: `/`, `/intake`, `/system-card`, `/staff` signed out and signed in × **390 / 768 / 1280 px × light / dark = 30 runs**.

| Check | Result |
| --- | --- |
| Horizontal page overflow | **0 px in all 30 runs** |
| Touch targets ≥ 44 × 44 (incl. evidence links and section nav) | **No smaller target** |
| Clipped content in workflow steps, capability cards, stat tiles, rule/stage cards, real-vs-mock rows | **None** (`scrollWidth ≤ clientWidth`) |
| One `h1` per page | 30/30 |
| Live status (dashboard) | *Reachable*, `local-fixture`, `mock` as reported by the fixture `/health` |
| Mobile nav, focus, Escape, reduced motion | Pass (Enter opens; first link *Dashboard*; Escape closes and returns focus) |

Fixed during the pass: the `phi` category was shown as *Phi* (now *PHI*); nav label *Guided demo* → *Dashboard*; capture height cap raised so the 390 px dashboard is captured in full.

**Evidence:** [`evidence/phase8_issue69_dashboard_local_2026-10-14/`](evidence/phase8_issue69_dashboard_local_2026-10-14/) — `{dashboard,system-card}-{390,768,1280}-{light,dark}.jpg`, `nav-mobile-open-390-light.jpg`, `measurements.json` (all 30 runs), `capture-cdp.mjs`. Synthetic data only.

### 4b. Limitations

* ~~Hosted validation: pending.~~ Resolved on 2026-10-14 (§4c).
* The unavailable and waking dashboard states are covered by unit tests, not by browser screenshots (the real wake window is ~75–105 s).
* The API's pipeline text still states the webhook unconditionally (see wording review); the UI qualifies it in place, the source text is unchanged.

**Review Gate (2026-10-14).** The first candidate (`8dff155`) qualified the webhook only in a small note below the pipeline grid, after the unconditional stage text, and the dashboard's webhook card opened with *"one … notification per escalation"*. Fixed with frontend wording only (above); tests, lint, typecheck, build and the 30-run browser matrix re-run (0 overflow, no target < 44 × 44, no clipped content); screenshots refreshed.
* Chrome only; Safari/Firefox, physical devices and 200 % zoom are #72.

### 4c. Hosted frontend verification (2026-10-14)

**Deploy.** PR #78 merged with a merge commit (`24d2a6b`, reviewed head `758fb37`; PR CI and `main` CI run 38547619614 — success). Frontend *Manual Deploy* by the account owner: source commit `24d2a6b`, *Live* at 18:12 Taiwan time (10:12 UTC). The API was not redeployed (no backend change) and **was not restarted** for this check. No Render setting was changed.

**Natural cold start (observed, not forced).** The API had been idle since the #68 check (09:42 UTC). The first request of this run was the hosted dashboard in headless Chrome at 1280 px, with no prior API call. Its *Live system status* card moved through:

| Time (UTC) | `data-state` | Card |
| --- | --- | --- |
| 10:15:44.5 | `checking` | *Checking the demo API…* |
| 10:15:46.7 | `waking` | *Waking the demo server (can take up to a minute)… (attempt 1 of 6)*; API *Checking…*, environment and LLM mode *Unknown* (screenshot `cold-start-waking-dashboard-1280-light.jpg`) |
| 10:16:27.4 | `ready` | *Reachable*; environment `demo`, LLM mode `mock` (screenshot `cold-start-final-dashboard-1280-light.jpg`) |

About 43 s from the first check to *ready*. No environment or mode was shown before `/health` answered. Request-level network timings were not captured, so the attempt that succeeded is not recorded; the unavailable/failure state is still covered by unit tests only.

**Live `/health`** (`curl`, after the run): `{"status":"ok","app":"Healthcare AI Platform","environment":"demo","llm_mode":"mock"}`. The dashboard showed `demo` / `mock` on **6/6** dashboard runs.

**Evaluation metrics, hosted vs. committed.** The hosted `GET /api/system-card` → `evaluation` is **deep-equal** to the committed `evaluation/system_card_results.json` (saved as `hosted-api-system-card.json`; `execution_mode: mock`, threshold 0.5, 6 pipeline stages, 6 limitations). On all **6** system-card runs, the rendered table rows, the extraction line and both caveats equal the values computed from the committed file:

* Safety & escalation (#32): Diagnosis seeking, Emergency language, PHI, Prescription request — 4 cases each, 4/4 · 1.00 guard and escalation, known gaps 1/0/1/1; **Total 16 cases, 16/16 · 1.00, 16/16 · 1.00, 3 known gaps**; caveat *"Match rates measure agreement with the labelled current rule baseline on 16 synthetic cases, not safety accuracy or recall. Known gaps are recorded, not fixed."*
* Extraction (#40): *"6 cases · micro precision 1.00 · micro recall 1.00 · macro precision 1.00 · macro recall 1.00"*; caveat *"In-sample: the rule-based lexicon was written with these 6 synthetic cases in view, so 1.00 is agreement with a tiny set, not a measure of real-world extraction quality."*

**Responsive matrix (hosted, 10:16:28–10:16:47 UTC).** `capture-cdp-hosted.mjs` (no sign-in, no bearer token): `/`, `/system-card`, `/intake`, `/staff` (signed out) × **390 / 768 / 1280 px × light / dark = 24 runs**.

| Check | Result (hosted) |
| --- | --- |
| Horizontal page overflow | **0 px in all 24 runs** |
| Touch targets ≥ 44 × 44 | **No smaller target** |
| Clipped content (workflow steps, capability cards, stats, rule/stage cards, real-vs-mock rows) | **None** |
| One `h1` per page; demo indicator | 24/24; 24/24 |
| Workflow | Seven stages in order (`intake`, `structuring`, `report`, `escalation`, `queue`, `timeline`, `fhir`) on 6/6 dashboard runs; the webhook branch is inside the `escalation` step: *"Conditional branch · Signed webhook … only when a receiver is configured. Disabled on the hosted demo (no receiver configured)."* |
| System-card webhook wording | Inside the *Persistence + notification* stage: *"Conditional · Sent only when a receiver is configured on the server; disabled on the hosted demo. Not a delivery guarantee."* |
| Demo access | #67 wording present (*"Tokens are issued on request by the demo operator and are never published: there is no public sign-up, guest login or shared password."*); demo staff table shown (`NEXT_PUBLIC_DEMO_MODE` on) on 6/6 dashboard runs |
| Mobile nav, focus, Escape, reduced motion | Pass (first link *Dashboard*; links 358 × 44 px; Escape returns focus to *Menu*) |

**Capability evidence links.** All **22** links on the hosted dashboard return HTTP 200 (`evidence-links-status.txt`): 19 GitHub files on `main` and 3 in-app `/system-card#…` links. The GitHub `#anchors` are checked against the files' headings by `app/tests/Dashboard.test.tsx`. The in-app section ids are checked by the same tests on this commit, not by a separate probe of the hosted page.

**Evidence:** [`evidence/phase8_issue69_hosted_frontend_2026-10-14/`](evidence/phase8_issue69_hosted_frontend_2026-10-14/) — `{dashboard,system-card}-{390,768,1280}-{light,dark}.jpg`, `cold-start-waking-dashboard-1280-light.jpg`, `cold-start-final-dashboard-1280-light.jpg`, `nav-mobile-open-390-light.jpg`, `measurements.json` (cold-start samples + 24 runs; its captured page text includes the public policy sentence about bearer tokens, no token), `hosted-api-system-card.json`, `evidence-links-status.txt`, `capture-cdp-hosted.mjs`.

**Not verified on the hosted demo:** the *unavailable* state and *Try again* (unit tests only); per-request `/health` timings during the wake; Safari/Firefox, physical devices and 200 % zoom (#72). The signed-in staff workspace is unchanged by #69 and remains pending hosted validation (§3c).

**Verdict for #69 on the hosted demo:** the deployed build is `24d2a6b`; the dashboard and system card pass the responsive and accessibility checks at 390, 768 and 1280 px in both themes; live status reports the real `/health` values through a natural cold start; the system card's numbers, sample sizes and caveats match the committed snapshot exactly; the webhook is presented as conditional; the access policy and demo gating are intact; all evidence links resolve.

---

## 5. Issue 70 — Patient Intake Experience

**Status:** closed (2026-10-15): PR #80 merged (`8f6e963`, reviewed head `6dd697a`; `main` CI run 38725970985 — success); deployed and verified on the hosted demo (§5d). Frontend only: no backend, `/api/ingest`, validation-rule, consent-semantics, safety-guard or escalation-rule change; no new dependency (`app/package.json` unchanged); no environment variable or Render change.

**Delivered:**

* **Scenario cards** (`app/components/InputForm.tsx`): the four `SCENARIO_PRESETS` as a fieldset of `aria-pressed` buttons, each showing the name, the synthetic text and *Expected outcome:* from `SCENARIO_PRESETS.expect`, with a *Selected* tag and a 2 px primary border. Choosing a card fills the text only. It never ticks consent, never submits, and a consent the patient already ticked is kept. Editing the text away from the scenario clears the selection. Cards are disabled while a submission is active.
* **Form** (the page now owns the values, so a failure keeps them and a reset can clear them): explicit label *Your symptoms (required)*, instructions (*At least 10 characters…*) and a request not to enter name, contact details, date of birth or other identifiers. The field is described by the hint, the counter and, when present, the error (`aria-describedby`, `aria-invalid`). Live counter *n / 5000 characters* against `MAX_TEXT_LENGTH`; a separate polite live region announces only the last 500 characters and the limit, not every keystroke. Validation rules unchanged (`validateIntake`, `maxLength`). A client error moves focus to the field and is announced (`role="alert"`). A server consent error marks and focuses the consent checkbox. Consent stays exactly as before: not required on the client, enforced by the backend when it detects personal details.
* **Staged submission** (`app/components/SubmissionProgress.tsx`): *Wake the demo server* (or *Demo server ready*) → *Process your intake* → *Submission completed*, as a step list with `aria-current="step"` and one `role="status"` line. No percentages. The page runs the #67 readiness check once (`useApiReadiness`, now shared with the notice through the new `ApiStatusView`). A submission made before `/health` answered waits in stage 1 and **sends nothing** until it does (*"Your intake has not been sent yet"*, attempt *n* of 6). *Processing* is shown only when the POST starts. After 15 s of processing a note says it is taking longer than usual and asks not to resubmit. If the wake check gives up, the POST is never sent (class *unavailable*), and one explicit re-check runs per submission, never in the background. The *LLM Mode* badge now comes from the same `/health` answer, which removes the page's second `/health` request. Submit, text, consent and cards stay disabled for the whole submission (button *Submitting…*, plus the existing `inFlight` guard).
* **Outcome first** (`app/components/ReportView.tsx`, `app/services/intakeOutcome.ts`): *Your intake has been received* (focused when it appears), then emergency guidance (urgent `role="alert"`, first element, *"Do not wait for the clinic to review this intake"*) whenever the safety trace requests it or `emergency_signal` is a reason. Then an **Outcome** card: `StatusBadge` from `escalation.review_status` (`submitted` → *Submitted*, `needs_review` → *Flagged for staff review*, via a new optional `label` prop; staff views unchanged), the reasons as `ReasonList`/`ReasonLabel`, a blocked-report notice when the guard blocked the report, and what happens next. All values are read from the response; nothing is re-evaluated in the browser.
* **What happens next depends on `persistence.status`** (`agents/pipeline.py::save_record`): `saved` + flagged → *"Authorized clinic staff can review this record in their queue"*; `saved` + not flagged → stored as submitted, no review flag; `duplicate` → *"An identical description was received earlier, so no new record was created and nothing new was added to the clinic staff queue"*; `disabled`/`skipped`/`failed` → not stored, will not appear in the queue; missing → says it is unknown. The queue is never claimed for a record that was not saved. For a record that was not newly saved, the badge also reports the storage result (*Already received · no new record* or *Not stored*), not *Flagged for staff review*, and the reasons are headed *Escalation rules this description matched*.
* **Sections:** Intake summary (what you told us, summary) · Extracted information (symptoms, duration, onset, severity, warning signs, and the unchanged *"deterministic rule-based baseline, not LLM-generated"* note in mock mode) · Safety findings · Pre-visit report, or **Safe acknowledgement (report withheld)** for a blocked report, with *"No automated report was generated for you"* in the outcome card · Next steps (disclaimer, reference id, *Start a new intake*).
* **Errors and recovery** (`app/services/api.ts`): each failed outcome now carries an `errorClass`. HTTP 502 and 503 have their own messages (previously the generic processing message). Backend detail stays in the developer trace.

| Class | Trigger | Message (patient) | Recovery | Stored? |
| --- | --- | --- | --- | --- |
| `validation` | 400 (not consent), 422 with a list | *We couldn't accept this description…* | *Review your description* (focus field) | No |
| `consent` | 400 consent detail | *…appears to include personal details. Please confirm consent…* | *Review consent* (focus checkbox) | No |
| `provider` | 502 (`LLMError`) | *…did not respond properly, so nothing was saved…* | *Try again* | No (raised before persistence) |
| `configuration` | 503 (`LLMConfigurationError`) | *…not available at the moment, so nothing was saved…* | *Try again* | No |
| `server` | 500, 422 string, 200 without `success` | *We couldn't process your intake right now…* | *Try again* | No |
| `network` | no readable response | *We couldn't reach the intake service…* + *may or may not have been received* | *Send again* | **Unknown** |
| `timeout` | client abort at 60 s | *…took too long to respond…* + *may still have been received* | *Send again* | **Unknown** |
| `unavailable` | #67 wake check gave up | *…did not respond, so your intake was not sent…* | *Try again* (re-checks `/health` first) | No (no POST) |

  Text and consent are kept on every failure (*"Your description and your consent choice have been kept"*). **No automatic retry**, because a network failure or timeout is ambiguous. *Send again* is an explicit action, and the same in-flight guard and disabled controls apply, so a retry cannot overlap another submission. The patient note does **not** promise idempotency: *"…this demo normally recognises the identical text and does not store it twice, but that cannot be guaranteed."* The backend behaviour behind "normally": when persistence is enabled, byte-identical text hits the `input_hash` unique constraint (an unsalted SHA-256 of the text), returns `persistence: duplicate`, creates no second record and does not fire the webhook, which runs only for `saved`. The page then shows the *identical description* next step. Edited text, or persistence turned off, gives no such protection.
* **Start a new intake:** clears text, scenario, consent (unchecked), field errors, result, error, progress and the trace toggle, then moves focus to the form heading. Nothing is sent and no record is deleted.
* **Developer trace:** still behind the reviewer toggle (#43), collapsed. It is now a `Card` with a *Reviewer only* `Tag`, and its Run section adds escalation required, review status, reasons (`ReasonList`) and storage status.

**Raw-text limitation (unchanged).** `/api/ingest` still returns the full trace, including `intake.raw_text`, `chief_complaint` and guard evidence (#32 finding, `docs/security_data_handling.md`). The result shows *What you told us* from `chief_complaint` as before. Fixing it is an API change, out of scope.

**Tests.** `app/tests/IntakePage.test.tsx` rewritten (19 → 51), covering:
* the four scenario cards (text, expected outcome, fills text only, consent untouched, no submit) and each preset's expected outcome (status and reasons on screen without the trace);
* consent as a deliberate action and no identifier fields;
* validation linked by `aria-describedby`, focus and announcement; the counter and its near-limit announcements;
* already awake → processing → done; a slow `/health` (attempt 2 of 6) with no POST until ready and a single `/health` check; wake failure (no POST, kept input, retry); the slow-processing note;
* submitted, flagged (queue wording), emergency first, blocked acknowledgement, and duplicate/disabled/failed storage wording;
* every error class end to end through the real `submitIntake` against a mocked `fetch` (400, 400 consent, 422, 502, 503, network, timeout): message, kept text and consent, focus, a single announcement, and the recovery path (no automatic retry; explicit retry sends the same body). Also network/timeout followed by a `duplicate` answer, and a retry that cannot overlap;
* double-submit prevention; *Start a new intake* after a result and after an error; developer-trace visibility and contents.

`app/tests/api.test.ts` adds 7: `errorClass` for 502/503/500/422-string and the three validation cases, and the network/timeout classes. Fixtures gained `escalation`/`persistence` and four synthetic scenario outcomes shaped like the mock pipeline's. Total **179 passed** (140 before). `npm run lint`, `typecheck`, `test` and `build` pass locally.

### 5a. Local browser validation (2026-10-15)

**Setup.** Production build (`next build` + `next start`, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8787`, `NEXT_PUBLIC_DEMO_MODE=true`) against a local synthetic fixture API (`fixtures-server.mjs`). Its `/api/ingest` answers with **real mock-pipeline responses** for the four preset texts: `gen-ingest-fixtures.py` runs `HealthcarePipeline` with `LLM_MODE=mock`, persistence and webhook off, with no database and no network (`ingest-fixtures.json`). The server sets `persistence` to `saved` because no local database ran. Error classes are produced by a synthetic marker in the text (`[fixture:502]` etc.; `network` drops the socket), and `/__control` delays `/health` or the ingest for the cold-start and slow shots. Headless Chrome over the DevTools Protocol (`capture-cdp.mjs`), `en-US`/UTC. No hosted service was called.

**Matrix:** the form (a scenario selected) and the four outcomes × **390 / 768 / 1280 px × light / dark = 30 runs**.

| Check | Result |
| --- | --- |
| Horizontal page overflow | **0 px in all 30 runs** |
| Touch targets ≥ 44 × 44 (scenario cards, buttons, consent label, reviewer toggle) | **No smaller target** |
| Clipped content (scenario cards, progress steps, badges, reasons, cards, alerts, tags) | **None** |
| One `h1`; demo indicator; *LLM Mode: Mock* from the single `/health` | 30/30 |
| Outcomes (all 6 viewports each) | routine *Submitted*, no reasons; emergency *Flagged for staff review* + `emergency_signal`, guidance first; prescription *Flagged…* + `blocked_prescription`, *Safe acknowledgement (report withheld)*; vague *Flagged…* + `low_confidence`; queue wording for every `saved` result; baseline note present |
| Focus after a result | *Your intake has been received* heading, 24/24 |
| Keyboard | Tab from the form heading reaches the first scenario card (3 px ring); Space selects it; text filled, consent still unchecked |
| Client validation | focus on the field, `aria-invalid`, `aria-describedby` `symptoms-hint symptoms-counter symptoms-error`, `role="alert"` |
| Server errors, submitted from the keyboard | 400 consent → consent checkbox focused; 422 → field focused; 502/503/network → the alert focused; 3 px focus ring in each; text and consent kept; recovery button enabled |
| Cold start (`/health` delayed 6 s, submit at once) | *waking, attempt 1 of 6, "has not been sent yet"* (10:51:09.9) → *processing* (10:51:15.9, when `/health` answered) → *done* (10:51:17.5); submit disabled until done |
| Slow processing (17 s) | note after 15 s, no `%`, submit disabled, then the result |
| Reset | text empty, consent unchecked, no selection, result and trace gone, focus on the form heading |
| Developer trace | hidden by default; shows escalation, review status `needs_review`, reasons and storage when opened |
| Reduced motion | spinner animation 0.01 ms |

**Defect found and fixed in this pass:** after a server error, focus fell back to `<body>`. The focus call ran on a timer that could fire before React committed, while the form was still disabled and the alert not mounted. jsdom did not show this. Focus now moves in a post-commit effect, once the target is mounted and enabled, and the browser re-run confirms it. Focus moved to a heading (result or reset) shows no ring when the action came from a pointer; that is the browser's `:focus-visible` behaviour.

**Evidence:** [`evidence/phase8_issue70_intake_local_2026-10-15/`](evidence/phase8_issue70_intake_local_2026-10-15/) — `intake-form-{390,768,1280}-{light,dark}.jpg`, `result-emergency-{390,768,1280}-{light,dark}.jpg`, `result-{routine,prescription,vague}-{390-light,1280-dark}.jpg`, `stage-waking-1280-light.jpg`, `stage-processing-slow-1280-light.jpg`, `error-{client-validation,400-consent,422,502,503,network}-390-light.jpg`, `focus-scenario-card-390-light.jpg`, `developer-trace-1280-dark.jpg`, `measurements.json` (all 30 runs and every interaction check), `capture-cdp.mjs`, `fixtures-server.mjs`, `gen-ingest-fixtures.py`, `ingest-fixtures.json`. Screenshots of the other outcome/viewport combinations were measured but not committed, to keep the evidence size in line with earlier issues. Synthetic data only.

### 5b. Hosted validation plan (completed in §5d)

The new frontend is **not deployed**, so none of the above is a hosted result, and the #67 API checks (§2a) do not validate this UI. Hosted validation needs, in order:

1. **Owner authorization** for the frontend *Manual Deploy* (no API redeploy needed: no backend change).
2. **Webhook pre-check before any flagged preset.** The owner confirms on Render that the API service still has `WEBHOOK_URL` unset, then sends one non-flagged synthetic probe and checks that the API log shows `Escalation webhook disabled: WEBHOOK_URL and WEBHOOK_SECRET (>= 32 chars) are both required`, as in §2a. No public endpoint exposes this setting, so it cannot be checked from outside. **If it cannot be confirmed, no flagged preset is sent.**
3. The four presets in the browser at 390 and 1280 px (desktop and mobile screenshots for the PR), the cold start if the API is asleep, and the responsive matrix. Synthetic text only.

**Expected hosted difference:** the four preset texts are already stored on the hosted database (§2a), so a hosted run returns `persistence: duplicate`. The outcome card then shows the status and reasons from the escalation decision as usual, but the next step reads *"An identical description was received earlier, so no new record was created"* rather than the queue wording. This is the correct wording for that response, not a defect. A `duplicate` result also triggers no webhook (it fires only for `saved`). That does not replace the pre-check in step 2.

### 5c. Limitations

* ~~Hosted validation pending.~~ Done on 2026-10-15 (§5d).
* The browser outcomes come from real mock-pipeline responses, but `persistence: saved` is set by the fixture server. The `duplicate`/not-stored badge and wording, which is what the hosted presets will show (§5b), are covered by unit tests, not by a browser screenshot.
* Timeout (60 s) and the full 6-attempt wake failure are covered by unit tests, not browser runs; `422` with a string detail and `500` are unit-tested only.
* The counter announces only near the limit; screen-reader output itself was not tested with a real screen reader (VoiceOver/NVDA).
* The API's raw-text-in-response finding (#32) is unchanged (above).
* Chrome only; Safari/Firefox, physical devices and 200 % zoom are #72.

**Review Gate (2026-10-15).** The first candidate (`fdc2a1f`) had two #70 defects, both fixed with frontend wording only:
* A `duplicate` (or not-stored) response still showed the *Flagged for staff review* badge and *Why it was flagged*, which implied a new queue item. The badge now reports the storage result and the reasons heading is neutral; tests assert this for `duplicate`, `disabled` and `failed`.
* The network/timeout recovery note stated *"no second record is created"* as a guarantee. It now says the demo *normally* recognises identical text, *"but that cannot be guaranteed"*; a test rejects the old claim.

Two small wording fixes in the same commit: the queue sentence no longer promises review *"before your visit"*, and the blocked notice says *"prescription or dosing content"* instead of *"advice"*. Lint, typecheck, 179 tests and build pass. The 30-run browser matrix was re-run (0 overflow, no target under 44 × 44, nothing clipped, same focus and keyboard results), and the committed screenshots and `measurements.json` were refreshed.

### 5d. Hosted frontend verification (2026-10-15)

**Deploy.** PR #80 merged with a merge commit (`8f6e963`, reviewed head `6dd697a`; PR CI and `main` CI run 38725970985 — success). Frontend *Manual Deploy* by the account owner: `healthcare-ai-frontend`, source commit `8f6e963`, *Live* at 19:22:40 Taiwan time (11:22:40 UTC). The API was not redeployed (no backend change). No Render setting was changed. At 11:24:46 UTC `/intake` returned 200 with the #70 markup (scenario section, four *Expected outcome:* blocks), and `/health` returned `{"status":"ok","environment":"demo","llm_mode":"mock"}`.

**Webhook isolation, verified before any flagged preset.**
1. **Environment (owner, Render → `healthcare-ai-api` → Environment):** `WEBHOOK_URL` absent, `WEBHOOK_SECRET` configured. With a secret and no URL, `api/webhook.py::_config` logs the disabled warning and returns no configuration, so `notify_escalation` returns `disabled` for every saved record. → **PASS**
2. **Log check (Render logs, read-only, inspected in the browser):** one unique non-flagged probe was sent through the hosted UI. Text: *"Synthetic probe for issue seventy: I have had a mild cough and a runny nose for three days."*, first confirmed locally in mock mode as `submitted`, no reasons and no safety actions. It was sent at 11:25:42 UTC (POST 200; UI: *Submitted*, *"stored as submitted … no review flag was raised"*). The API logs for the last hour contain exactly one ingest request, on instance `2gh2c`:
   * `11:25:42  INFO:api.ingest:Received ingest request`
   * `11:25:43  INFO:agents.pipeline:Persisted health record | record_id=d7cdb418b38e4f2394b046f0e9958fcb | run_id=cbb5b0d0-78a0-477d-b00e-1ca6d4e28a42`
   * `11:25:43  WARNING:api.webhook:Escalation webhook disabled: WEBHOOK_URL and WEBHOOK_SECRET (>= 32 chars) are both required`

   The run ID matches the *Reference* on the hosted result page. A search for `webhook` over the hour returns only that warning: no delivery, retry or failure line. → **PASS**

   Only then were flagged presets sent. The probe is the one new record this check created (non-flagged, synthetic).

**The four presets on the hosted UI** (`capture-cdp-hosted.mjs presets`, 11:30:16–11:30:45 UTC): each card selected, consent ticked separately, submitted from the keyboard. **390 / 1280 px × light / dark**, i.e. 4 form views and 16 submissions (4 presets × 4 views).

| Preset | Badge (all 4 views) | Reasons (heading *Escalation rules this description matched*) | Other | Next step |
| --- | --- | --- | --- | --- |
| routine | *Already received · no new record* (`data-status="duplicate"`) | — | *Pre-visit report*; rule-based baseline note | *"An identical description was received earlier, so no new record was created and nothing new was added to the clinic staff queue."* |
| emergency | same | `emergency_signal` (*Emergency signal*) | emergency guidance is the first element after the heading (`role="alert"`) 4/4 | same |
| prescription | same | `blocked_prescription` | blocked notice + *Safe acknowledgement (report withheld)* 4/4 | same |
| vague | same | `low_confidence` | — | same |

* **Actual hosted behaviour: every preset submission was a duplicate.** The preset texts were stored in Phase 7 and §2a. The API log shows 16 × `Persistence skipped: identical input already stored` (11:30:19–11:30:42 UTC) and no `Persisted` line. The webhook notifier runs only for `saved`, so it never ran, and there is no webhook line after the probe's. The last run ID in the log (`c8171451…`) is the one in the hosted developer trace (*Storage: duplicate*). The UI never said *Flagged for staff review* and never claimed a queue item for these responses.
* **Consent:** unchecked after selecting each card, 16/16. The selected card is `aria-pressed="true"`, the others `false`.
* **Staged progress:** the API was awake, so each submission went *processing → done* with Submit disabled until done (about 0.2–1 s). The **waking** stage was not observed on the hosted demo: no cold start happened during this run. It is covered by unit tests and the local browser run (§5a).
* **Focus:** *Your intake has been received* heading after each result (16/16), with a 3 px focus ring after keyboard submission. Client validation (*"short"*): field focused, `aria-invalid`, `aria-describedby` `symptoms-hint symptoms-counter symptoms-error`, `role="alert"`, nothing sent.
* **Developer trace:** hidden by default; behind the reviewer toggle it showed escalation required *yes*, `needs_review`, `low_confidence`, *Storage* `duplicate`.
* **Start a new intake:** text empty, consent unchecked, no selection, result and trace gone, focus on the form heading.
* **Layout:** 20 measured views, 0 px overflow, no target under 44 × 44, nothing clipped, one `h1`, *LLM Mode: Mock* from `/health`.
* **Requests:** 17 `POST /api/ingest` in total (probe + 16), all 200; 5 `GET /health`, one per page load.

**Evidence:** [`evidence/phase8_issue70_hosted_frontend_2026-10-15/`](evidence/phase8_issue70_hosted_frontend_2026-10-15/):
* screenshots: `intake-form-{390,1280}-{light,dark}.jpg`, `result-{routine,emergency,prescription,vague}-{390,1280}-{light,dark}.jpg`, `probe-routine-unique-1280-light.jpg`, `developer-trace-1280-dark.jpg`, `error-client-validation-390-light.jpg`;
* measurements: `measurements-probe.json`, `measurements-presets.json` (per view: facts, stages, focus, request log with method/URL/status only);
* `render-api-log-excerpt.txt` (internal client addresses redacted; no environment values, secrets or tokens);
* `capture-cdp-hosted.mjs`.

No sign-in, no token, synthetic text only.

**Not verified on the hosted demo:**
* the waking stage during a real cold start;
* the *Flagged for staff review* badge with the saved-record queue wording: it needs a new, unique flagged text, which was deliberately not sent. Covered by unit tests and §5a;
* every server error class (400/422/500/502/503/network/timeout): not induced on a shared demo; covered by unit tests and §5a;
* the signed-in staff view of the probe record;
* Safari/Firefox, physical devices and 200 % zoom (#72).

**Verdict for #70 on the hosted demo:** the deployed build is `8f6e963`. Webhook isolation was confirmed by environment and log before any flagged preset. All four presets show the correct expected rule outcome, reasons, emergency prominence and blocked acknowledgement without opening the trace, and they truthfully report that a duplicate created no new record or queue item. Consent stays a deliberate action, focus and the reviewer trace behave as specified, and the layout passes at 390 and 1280 px in both themes.

---

## 6. Issue 71 — Staff Review Workspace Experience

**Status:** closed (2026-10-15): PR #82 merged (`7585f84`, reviewed head `e4dc65b`; `main` CI run 38730669057 — success); deployed and verified on the hosted demo (§6d). Frontend only: no backend, endpoint, RBAC, clinic-isolation, authentication or transition-rule change; no new dependency; no Render or environment change.

**Delivered** (`app/components/StaffReview.tsx`, `IntakeEvidence.tsx`, `FhirExport.tsx`, new `app/services/format.ts`):

* **Sign-in:** product copy; demo access explained as short-lived tokens the demo operator issues on request (#67 policy card unchanged). The `python -m api.auth issue-token` hint is removed from the UI; operator instructions remain in `docs/auth.md` and `docs/deployment.md`. The token stays in component state only; a test checks `localStorage`, `sessionStorage` and cookies after sign-in and sign-out. Specific messages:
  * 401: *"invalid or has expired"*. The API answers `Invalid or expired token` for both cases, so the UI cannot separate them and says so.
  * 403: valid token without staff access.
  * 503: staff sign-in not configured.

  The field is linked to its help text and error (`aria-describedby`, `aria-invalid`). A 401 during use still ends the session (unchanged).
* **Layout:** at ≥ 1280 px the queue and detail sit side by side (2 : 3), with an empty-state placeholder until an intake is opened. Below 1280 px they are separate views: opening an intake shows the detail with **← Back to queue**. Focus moves to the intake heading on open, and back to the opened row (post-commit) on return. The queue table uses the stacked-card layout in the desktop queue column as well, so no column hides behind horizontal scroll.
* **Queue:**
  * One unfiltered `GET …/intakes` for the **signed-in clinic only** (an existing call). The endpoint is not paginated.
  * Status tabs (*Needs review*, *Reviewed*, *Escalated*, *Submitted*, *All*) filter that response, and each tab shows its count from the same response. A scope note says the counts are *"from the N intakes returned for clinic X when the queue was loaded"*.
  * `StatusBadge`, `ReasonList`/`ReasonLabel`, readable references (`#a1f3c2d4`; the full id is shown in the detail), and loading, empty and error/retry states.
  * The clinic selector for multi-membership accounts is unchanged; switching requests only the chosen clinic.
* **Dates:** every staff timestamp (queue, detail, timeline) is formatted with `Intl.DateTimeFormat("en-US", { timeZone: "UTC" })` plus the suffix *UTC*, e.g. *Oct 01, 2026, 10:00 UTC*. Timeline entries carry `<time datetime>` with the raw value.
* **Detail:** a header with the reference, status badge, reasons, full id, received and last-updated time. A *Review action* section comes next, followed by the unchanged structured summary, report, safety result, *Why flagged* evidence with highlighted input matches, extracted fields and provenance (clinical and safety wording unchanged).
* **Timeline:** a vertical timeline of the events the API returns, in order, with markers per kind (staff transition, webhook delivery). Webhook rows show only what is recorded (status, attempts, last HTTP/error). When none is recorded, the page says *"No webhook delivery is recorded for this intake"*, never "sent" or "disabled". Actors and times are shown only when present.
* **Actions:** only for `needs_review` (rule unchanged); no bulk actions.
  * *Mark reviewed* / *Mark escalated* opens an inline confirmation step (focus moves to *Confirm*; *Cancel* sends nothing).
  * While pending, both actions are disabled and a second click sends nothing.
  * On success: a success message, the detail updated from the response, the queue refetched, and the timeline remounted and reloaded.
  * 409 and 404 reload the server's state (unchanged).
* **FHIR export:** endpoint and payload unchanged.
  * The disclaimer: synthetic demo data, export only, not a FHIR conformance or certification claim, nothing sent to a FHIR server, and the bundle contains the original intake text.
  * On demand load; a resource summary (type × count from the returned Bundle); the existing download; the JSON preview in a collapsed `<details>`.

**Tests.** `app/tests/StaffReview.test.tsx`: 27 → **41**. Updated tests: the unfiltered list call, tab counts and client filtering with no refetch, the confirmation step before a transition, and the new sign-in message.

New tests:
* no CLI text;
* token not persisted;
* 403 and 503 sign-in messages;
* UTC/en-US formatting in queue, detail and timeline (`datetime` attribute);
* readable references and focus on open;
* list/detail navigation with *Back to queue* returning focus to the row;
* confirmation cancel;
* queue, detail and timeline refresh after a transition (new `staff_transition` event with actor and time);
* no fabricated webhook delivery;
* clinic A/B: only the signed-in clinic is requested, with an explicit switch for a two-clinic admin, and a clinic-B account that never requests clinic A and sees no rows on 403;
* the FHIR resource summary, collapsed preview and disclaimer.

Existing 401/403/404, 409, pending, failure, evidence and FHIR download tests still pass. Total **193 passed** (179 before). `npm run lint`, `typecheck`, `test` and `build` pass.

### 6a. Local browser validation (2026-10-15)

Production build against the #68 synthetic fixture API (`fixtures-server.mjs`, copied; any bearer string is accepted, and sign-in used the placeholder `synthetic-fixture-not-a-token`). **No real token was generated or used.** Headless Chrome over the DevTools Protocol (`capture-cdp.mjs`), with the browser deliberately set to **`de-DE` / `Asia/Taipei`** to show that the dates do not follow the browser.

**Matrix:** sign-in, queue and detail × **390 / 768 / 1280 px × light / dark = 18 runs**.

| Check | Result |
| --- | --- |
| Horizontal page overflow | **0 px in all 18 runs** |
| Table horizontal scroll (counted as clipping for #71) | **0 in all 18 runs** |
| Touch targets ≥ 44 × 44 | **No smaller target** |
| Clipped content (cards, tabs, badges, reasons, timeline, detail values) | **None** |
| Layout | 1280: queue and detail visible together, no back control. 390/768: queue only, or detail only with *Back to queue* |
| Dates | *Oct 14, 2026, 01:00 UTC* under a `de-DE`/`Asia/Taipei` browser |
| Focus | detail heading on open (18/18 detail runs); after *Back to queue* (390 px) the opened row's button (`row:a1f3c2d4e5f60718`, the row that was opened) |
| Tab names (accessible) | *"Needs review, 3 intakes"*, *"Reviewed, 1 intake"* … (`aria-label`), not the run-together visible text |
| Confirmation | *Mark escalated* → *"Mark this intake escalated?"*, focus on *Confirm: mark escalated* (nothing sent; the fixture API has no transition endpoint) |
| FHIR | resource summary shown, preview collapsed (the fixture Bundle has one `Task`) |
| Token storage | `localStorage` 0, `sessionStorage` 0, no cookie |

**Defects found and fixed in this pass:**
* The row-open button's `data-open` attribute collided with the app shell's `nav[data-open]`, so *Back to queue* could not find the row. It is renamed `data-intake-id`, and focus is restored post-commit (the #70 lesson).
* At 1280 px the *Received (UTC)* column was hidden behind horizontal table scroll. The desktop queue column now stacks too, and the capture counts table scroll as clipping.
* The first cold navigation was measured before the stylesheet applied. The capture now waits for styles.

**Evidence:** [`evidence/phase8_issue71_staff_local_2026-10-15/`](evidence/phase8_issue71_staff_local_2026-10-15/) — `{signin,queue,detail}-{390,768,1280}-{light,dark}.jpg`, `detail-confirm-fhir-1280-light.jpg`, `measurements.json`, `capture-cdp.mjs`, `fixtures-server.mjs`. Synthetic data only.

### 6b. Hosted validation plan (completed in §6d)

Not deployed. Required after an authorized frontend deploy, with **securely issued short-lived tokens** (never committed or shown):
1. `demo-admin-a` (clinic `default`) and `demo-admin-b` (`demo-clinic-b`) each see only their clinic's queue in the new UI.
2. *Mark reviewed* and *Mark escalated* on eligible seeded `needs_review` intakes, with the timeline showing each transition (actor and time).
3. FHIR preview and download, with the downloaded file validated by `interoperability/fhir_validation.py`.
4. Hosted responsive screenshots at 390, 768 and 1280 px.

### 6c. Limitations

* ~~Hosted validation pending.~~ Done on 2026-10-15 (§6d). Before that, the real transition endpoint, real FHIR Bundle (six resource types) and download were exercised only with mocks in unit tests. The download was not validated against `fhir_validation.py` in this pass.
* Expired and invalid tokens share one message, because the API does not distinguish them.
* Counts reflect the list as loaded; they refresh after a transition or *Retry*, not live.
* Chrome only; Safari/Firefox, physical devices, 200 % zoom and a real screen reader are #72.

**Review Gate (2026-10-15).** The first candidate (`0532c3b`) had two accessibility defects, fixed in the frontend only:
* Status tabs were announced as *"Needs review3"* (label and count run together). Each tab now has the accessible name *"Needs review, 3 intakes"*; a test asserts it.
* Below 1280 px, opening an intake hides the queue and the button that opened it. If the intake then failed to load (403/404/network), focus was left on `<body>`. Focus now moves to *Back to queue* on a load error (heading on success); a test covers the 404 case.

The capture now records which row receives focus after *Back to queue*, and §6a states what was measured. Lint, typecheck, **193** tests and build pass. The 18-run matrix was re-run (0 overflow, 0 table scroll, no target < 44 × 44, nothing clipped), with screenshots and `measurements.json` refreshed. Token handling, clinic scoping, counts, UTC dates, timeline, transitions and FHIR were reviewed with no change needed. Hosted criteria remain **PENDING** (§6b).

### 6d. Hosted staff workspace verification (2026-10-15)

**Deploy.** PR #82 merged with a merge commit (`7585f84`, reviewed head `e4dc65b`; PR CI and `main` CI run 38730669057 — success). Frontend *Manual Deploy* by the account owner: `healthcare-ai-frontend`, source commit `7585f84`, *Live* at 19:56:31 Taiwan time (11:56:31 UTC). The API was not redeployed. No Render setting was changed. At 11:59:31 UTC `/staff` returned 200 with the #71 sign-in copy and no CLI hint.

**Tokens (#67 procedure).** The owner issued **1-hour** tokens for `demo-admin-a` and `demo-admin-b` locally with `python -m api.auth issue-token … --ttl-hours 1`, as described in `docs/deployment.md` §6.
* **Script:** the database URL and signing secret were entered at silent prompts and lived only in the script's process; they were never written or shown. The script was verified beforehand against a throwaway SQLite database with a fake secret, including success, partial-failure, short-secret and unreachable-host cases.
* **Storage:** the tokens were stored in `~/.hc-demo-71/tokens.env` (directory 700, file 600, outside the repository). The checks loaded them inside their own processes and never printed them.
* **Verification:** `GET /api/staff/me` returned 200 for both: `demo-admin-a` → `default` (`clinic_admin`), `demo-admin-b` → `demo-clinic-b` (`clinic_admin`).
* **Hygiene:** every signed-in page was checked for the token in its HTML, `localStorage`, `sessionStorage` and cookies (none found). Screenshots were taken only before a token was entered or after sign-in. The evidence was scanned for token, URL and secret patterns (none found).
* **Cleanup:** `~/.hc-demo-71` was deleted after the run (12:31 UTC). No token appears in the repository, logs, screenshots or chat.

**Isolation and eligibility, read-only, before any change** (`api-before.json`):

| Check | Result |
| --- | --- |
| `demo-admin-a` → `default` list / `demo-clinic-b` list | 200 (12 intakes: 4 submitted, 5 needs_review, 2 reviewed, 1 escalated) / **403** |
| `demo-admin-b` → `demo-clinic-b` list / `default` list | 200 (4 intakes, one per status) / **403** |
| Cross-clinic detail of each target | **403**; via the reader's own clinic path **404** |
| `2f005d14d0fc4de1acc4879d586481a3` | clinic `default`, **`needs_review`**, `emergency_signal`; synthetic: *"Synthetic demo intake eebac05f: crushing chest pain and trouble breathing since breakfast."* (created by `scripts/hosted_check.py` at the #67 check, §2a); mock provenance; events submitted → processed → safety_evaluated → escalation_decision; **no staff transition** |
| `demo-intake-b2` | clinic `demo-clinic-b`, **`needs_review`**, `low_confidence`; seeded (run id `demo-seed:demo-intake-b2`, synthetic text); **no staff transition** |

`demo-intake-a2` was not used: it was already marked reviewed in the Phase 7 browser check (2026-10-14), and re-seeding never resets a staff-changed status. The owner approved `2f005d14…` instead. No database was recreated or re-seeded.

**Transitions in the hosted UI** (`capture-cdp-hosted.mjs transitions`, 1280 px light, browser locale `de-DE` / time zone `Asia/Taipei`):

| | `demo-admin-a` on `2f005d14…` | `demo-admin-b` on `demo-intake-b2` |
| --- | --- | --- |
| In own *Needs review* queue | yes (tab *"Needs review, 5 intakes"*) | yes (*"Needs review, 1 intake"*) |
| Before | *Needs review*, `emergency_signal`, 4 events, no staff action | *Needs review*, `low_confidence`, 4 events, no staff action |
| Confirmation | *"Mark this intake reviewed?"*, focus on *Confirm: mark reviewed* | *"Mark this intake escalated?"*, focus on *Confirm: mark escalated* |
| Pending | *Updating status…*, both actions disabled, about 0.6 s | same, about 0.4 s |
| Success | *"Marked reviewed. The queue and timeline were refreshed."* | *"Marked escalated. …"* |
| After (UI) | **Reviewed**; timeline adds *Staff action · Oct 15, 2026, 12:29 UTC · demo-admin-a: Needs review → Reviewed* | **Escalated**; *Staff action · Oct 15, 2026, 12:29 UTC · demo-admin-b: Needs review → Escalated* |
| After (API, `api-after.json`) | `reviewed`; `staff_transition` 12:29:37.508 UTC, actor `demo-admin-a`, `needs_review → reviewed` | `escalated`; 12:29:44.192 UTC, actor `demo-admin-b`, `needs_review → escalated` |
| Webhook | no `webhook_delivery` event; the UI says *"No webhook delivery is recorded for this intake"* | same |
| Queue after | *Needs review* 4 (was 5) | *Needs review* 0, *Escalated* 2 |

Staff transitions do not call the webhook notifier (`api/routers/records.py` has no webhook call), and the webhook is disabled on the hosted API (§5d). These two transitions are the only data changes this check made.

**FHIR export** (`demo-admin-a`, after the transition):
* **Panel:** the summary showed *QuestionnaireResponse × 1, Questionnaire × 1, Task × 1, Organization × 1, Device × 1, Provenance × 2* (7 entries; the second Provenance records the staff transition). The JSON preview was collapsed by default (*"JSON preview (7 entries)"*) and opened on request. The disclaimer was present (*"… not a FHIR conformance or certification claim …"*).
* **Download:** *Download JSON* saved `intake-2f005d14d0fc4de1acc4879d586481a3-fhir-r4.json` (sha256 `6de74bb0…64104`): a `collection` Bundle tagged `synthetic-demo`, Task `completed` / `reviewed`.
* **Validation:** run on the unmodified file, `interoperability.fhir_validation.validate_bundle` returned **0 errors** (R4 4.0.1 JSON Schema per resource, required primitives, internal references; `fhir-validation.txt`). It was not run through the official HL7 validator, so this is not a conformance claim.

**Responsive matrix** (`capture-cdp-hosted.mjs matrix`): sign-in, queue and detail × **390 / 768 / 1280 px × light / dark = 18 views**, plus *Back to queue* at 390 and 768. Light used `demo-admin-a`, dark `demo-admin-b`. Read-only: rows were opened from the *All* tab and no action was taken.

| Check | Result |
| --- | --- |
| Horizontal overflow; table horizontal scroll | **0 in all views** |
| Touch targets ≥ 44 × 44; clipped content; one `h1` | **None smaller; none clipped; 18/18** |
| Layout | 1280: queue and detail side by side. 390/768: queue only, then detail only with *Back to queue* |
| Focus | detail heading on open (6/6); after *Back to queue*, the opened row (`row:d7cdb418…`, `row:demo-intake-b1`; 4/4) |
| Dates | UTC, en-US (*Oct 15, 2026, 12:29 UTC*) under a `de-DE` / `Asia/Taipei` browser |
| Isolation in the UI | `demo-admin-a` saw only `default` intakes; `demo-admin-b` only `demo-clinic-b` |
| Token in page/storage | none (all signed-in views) |

**Defect found (open, not fixed here: application code was out of scope for this check).** `intakeRef()` shows the first 8 characters of the id, so every seeded intake (`demo-intake-a1` … `b4`) appears as **`#demo-int`**. In clinic B's queue all four rows look the same, and their open buttons share the accessible name *"Open intake #demo-int"*. Hex ids (`#2f005d14`) are unaffected, and the detail view shows the full id. The local fixtures used hex ids only, so this was not caught. **Recommended follow-up:** derive the reference from the end of the id, or show the full id when it is not a hex hash, with a test for seeded ids.

**Evidence:** [`evidence/phase8_issue71_hosted_frontend_2026-10-15/`](evidence/phase8_issue71_hosted_frontend_2026-10-15/):
* screenshots: `{a,b}-queue-1280-light.jpg`, `{a,b}-detail-before-1280-light.jpg`, `{a,b}-confirm-1280-light.jpg`, `{a,b}-detail-after-1280-light.jpg`, `a-fhir-preview-1280-light.jpg`, `{signin,queue,detail}-{390,768,1280}-{light,dark}.jpg`;
* `measurements-transitions.json`, `measurements-matrix.json`, `api-before.json`, `api-after.json`;
* the downloaded `intake-2f005d14d0fc4de1acc4879d586481a3-fhir-r4.json` (synthetic) and `fhir-validation.txt`;
* `capture-cdp-hosted.mjs`.

No token, database URL or secret is included.

**Not verified on the hosted demo:** a two-clinic account and the clinic switcher (no seeded user has two memberships; unit-tested); the 409 conflict path (unit-tested); a real screen reader; Safari/Firefox, physical devices and 200 % zoom (#72).

**Verdict for #71 on the hosted demo:** the deployed build is `7585f84`.
* **PASS:** clinic isolation (UI and API), both transitions with confirmation, pending state, success and timeline/actor updates, FHIR summary, preview, download and validation, responsive layout and focus in both themes, UTC dates and token hygiene.
* **Open defect:** readable references are ambiguous for seeded ids (above). It does not affect access control or data, but it does affect the *readable intake references* criterion and needs a frontend follow-up.


### 6e. Follow-up #84 — distinct intake references

The §6d defect is tracked as #84 and was fixed in PR #85 (merged `1ed0b4a`, reviewed head `8b398d4`; `main` CI run 38737504706 — success). `intakeRef()` (`app/services/format.ts`) now shortens only hash-like ids (32-hex or a hyphenated UUID) to their first 8 characters (`#2f005d14`), and shows any other id in full (`#demo-intake-b2`). The change is display only: API calls, `data-intake-id`, transitions, FHIR and audit data keep using the full id. No backend, database, seed, auth or FHIR change.

**Tests.** New `app/tests/format.test.ts` (8):
* seeded ids, 32-hex ids and UUIDs (both cases);
* all eight seeded ids give distinct references;
* near-hash ids are not shortened;
* explicit UTC formatting.

`StaffReview.test.tsx` gains 2: four seeded clinic-B rows with distinct visible and accessible names (*"Open intake #demo-intake-b1"* …), the detail heading, and the API still receiving the full id; and the short form kept for hash ids. Four existing assertions now expect full non-hash references (`#flagged-0001`, `#clinic-a-01`, `#clinic-b-01`). Total **203 passed** (193 before). Lint, typecheck and build pass.

No local browser screenshots were taken for this change (the local fixture API uses hex ids only); it was verified on the hosted demo instead (§6f).

### 6f. Hosted verification of #84 (2026-10-15)

**Deploy.** Frontend *Manual Deploy* by the account owner: `healthcare-ai-frontend`, source commit `1ed0b4a`, *Live* at 20:50:55 Taiwan time (12:50:55 UTC). The live bundle contains the new `intakeRef` hash-id pattern. No API redeploy and no Render setting change.

**Read-only.** One-hour tokens were issued by the owner with the §6d script and verified with `GET /api/staff/me` (`demo-admin-b` → `demo-clinic-b`, `clinic_admin`). Only `demo-admin-b` was used.
* No action button was clicked. The request log (method, path and status only; no headers) contains **no non-GET request** apart from CORS preflights.
* All 7 checked signed-in views (the 1280 queue and the 6 responsive runs) were token-free (HTML, storage, cookies); the four per-row detail views opened at 1280 px were not checked individually.
* `~/.hc-demo-71` was deleted at 13:04:26 UTC. No token, URL or secret is in the evidence.

**Results** (`capture-cdp-hosted.mjs`, 12:58–13:04 UTC; `measurements.json`):

| Check | Result |
| --- | --- |
| Visible queue references (*All*, 4 intakes) | `#demo-intake-b1`, `#demo-intake-b2`, `#demo-intake-b3`, `#demo-intake-b4`: **distinct**, previously all `#demo-int` |
| Accessible row names | *"Open intake #demo-intake-b1"* … *"#demo-intake-b4"*: distinct |
| Detail headings (each row opened at 1280 px) | *Intake #demo-intake-b1* … *b4*, each with the matching full id in the detail and focus on the heading |
| Full ids preserved | `data-intake-id` = `demo-intake-b1` … `b4`; API requests `GET /api/clinics/demo-clinic-b/intakes/demo-intake-bN` and `…/timeline` use the full id |
| Layout: queue and detail at 390 / 768 / 1280 × light / dark (12 views) | **0 px overflow, 0 table scroll, no target under 44 × 44, nothing clipped**; row buttons 44 px high; 1280 side by side, 390/768 separate views |

Hash-id references keep the 8-character form: they were shown as #2f005d14 on the pre-fix build (§6d), and the new code's behaviour is covered by unit tests (format.test.ts). They were not re-captured on the hosted demo after #84.

During the run, two harness issues were fixed in the capture script (not the app):
* The first attempt clicked *Sign in* before React hydrated, which reloaded the page. The token input has no `name`, so nothing was submitted or exposed; the script now waits for hydration.
* A selector matched the reason-code chip instead of the id field.

**Evidence:** [`evidence/phase8_issue84_hosted_2026-10-15/`](evidence/phase8_issue84_hosted_2026-10-15/):
* screenshots: `queue-all-1280-light.jpg`, `detail-demo-intake-b2-1280-light.jpg`, `queue-all-{390,768,1280}-{light,dark}.jpg`, `detail-{390,768,1280}-{light,dark}.jpg`;
* `measurements.json` and `capture-cdp-hosted.mjs`.

Synthetic data only.

**Verdict for #84 on the hosted demo: PASS.** Clinic B's four seeded intakes now have distinct visible and accessible references and headings. Full ids are unchanged for data attributes and API calls, and the layout passes at 390, 768 and 1280 px in both themes.


## 7. Issue 72 — Accessibility, Frontend Quality & Browser E2E Validation (2026-10-15)

This was a 10-minute timeboxed pass, so the PR is **partial**. This section lists only what was actually run. It makes no WCAG conformance claim.

### 7a. Implemented

* Route-level error boundary (`components/ErrorBoundary.tsx`, wired in `pages/_app.tsx` and keyed by route). It shows a styled fallback, never renders error details and only logs to the browser console.
* Styled `pages/404.tsx` and `pages/500.tsx`, rendered inside the app shell through a shared `components/ErrorPage.tsx`.
* `tests/ErrorHandling.test.tsx`: 404, 500 and boundary fallback, with no leaked error message.
* `tests/contrast.test.ts`: computes WCAG contrast ratios from `styles/tokens.css` for 16 foreground/background token pairs in both the light and dark themes.

### 7b. Accessibility findings (2026-10-15, initial pass; superseded by §7g)

| Criterion | Page | Finding | Status | Evidence |
|---|---|---|---|---|
| 1.4.3 Contrast (Minimum) | All (tokens) | Text, muted text, link, on-primary, on-danger, danger and highlight pairs are ≥ 4.5:1 in light and dark | PASS (token level only) | `tests/contrast.test.ts` |
| 1.4.11 Non-text Contrast | All (tokens) | Focus ring and strong control border are ≥ 3:1 against bg/surface in both themes | PASS (token level only) | `tests/contrast.test.ts` |
| 2.4.1 Bypass Blocks | All | A skip link targets `main#main` | Present in code | `components/AppShell.tsx` |
| 2.4.7 / 2.4.11 Focus Visible / Not Obscured | All | Global 3px `:focus-visible` outline exists. Obscuring was not tested in a browser | NOT VERIFIED | `styles/globals.css` |
| 1.3.1 / 2.4.6 Landmarks, headings | All + error pages | header/nav/main/footer landmarks; error pages have an h1 | Partially verified (unit tests) | `tests/ErrorHandling.test.tsx`, existing `ui.test.tsx` |
| 2.1.1 Keyboard | All | Full keyboard-only walkthrough not performed | NOT VERIFIED | — |
| 3.3.1 / 4.1.3 Errors, live regions | Intake, Staff | Not re-audited in this pass | NOT VERIFIED | — |
| 1.4.4 / 1.4.10 Resize 200% / Reflow | All | Not tested | NOT VERIFIED | — |
| 2.3.3 Reduced motion | All | A `prefers-reduced-motion` rule exists. Not tested in a browser | NOT VERIFIED | `styles/globals.css` |

No critical keyboard or contrast **defect** was found in what was tested. Because keyboard behaviour was not verified in a browser, the "no open critical keyboard failures" criterion is still **pending**.

### 7c. Frontend quality (run locally, 2026-10-15)

* `npm run lint`: pass. `npm run typecheck`: pass. `npm test`: 10 files, 238 tests passed. `npm run build`: compiled successfully. Routes `/`, `/404`, `/500`, `/intake`, `/staff` and `/system-card` were all prerendered as static. Page sizes were not printed by this Next.js version and are not recorded.
* Bundle scan of `.next/static`: the only `NEXT_PUBLIC_*` names are `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_DEMO_MODE`. A grep for API-key, token, database-URL and private-key patterns found no secrets. The only hits were the UI constant name `WEBHOOK_BRANCH` (system-card copy).

### 7d. Browser E2E, accessibility and resilience (Playwright, local, 2026-10-15)

Command (from `app/`, Docker running):
`E2E_DATABASE_URL=$(../scripts/e2e_local_db.sh start) npm run e2e` (add `E2E_ALL_BROWSERS=1` for Firefox and WebKit), then `../scripts/e2e_local_db.sh stop`.
The stack is a throwaway `postgres:15` container, the API in mock mode via `scripts/e2e_api.sh` (test-only user, a one-hour token signed with a per-run random secret, webhook URL and secret empty, non-local DB refused), and a production build pointed at it. The hosted demo is never contacted.

* `app/e2e/smoke.spec.ts`: landing → routine intake → outcome (`submitted`); staff sign-in with the test token → queue (All) → detail → FHIR preview (`"resourceType": "Bundle"`); unknown route → styled 404 (HTTP 404).
* `app/e2e/a11y.spec.ts` (automated): on all four pages in light and dark themes, one banner/main/contentinfo, the nav landmark, exactly one h1, skip link as the first Tab stop (visible, moves focus to `main`), a visible focus indicator on the next 15 Tab stops, and no horizontal overflow at 320 CSS px (1.4.10). Also no animation or transition over 10 ms with `prefers-reduced-motion: reduce`, keyboard-only intake completion and submission, `aria-invalid` on empty staff sign-in, and Escape closing the mobile menu with focus returned to the toggle.
* `app/e2e/resilience.spec.ts`: requests to the API blocked in the browser. Dashboard: waking notice, then "Unreachable" plus "Try again". System card: load error alert. Intake (network lost after load): unreachable alert, with the text kept. Staff sign-in: unreachable alert. No code change was needed; existing handling behaved as designed.
* **Results:** 27 tests × Chromium 153.0.8010.12, Firefox 155.0 and WebKit 26.6 (Playwright builds) = **81 passed**, run twice consecutively with no failures (about 4.2 min each). WebKit stands in for Safari; native Safari was not tested. In WebKit, keyboard tests use Option+Tab, because by macOS default Tab skips links and buttons. This is platform behaviour, not an app defect.
* CI: the new `e2e` job runs the suite on Chromium against a PostgreSQL service with a test token generated in the job.

### 7e. CI result for the Playwright job

Run https://github.com/cindy12651269/healthcare-ai-platform/actions/runs/38745649052 on head `7767fb8`: all four jobs passed. Backend 48s, benchmark 18s, frontend 1m6s, and Browser E2E 3m7s (`27 passed (1.7m)` on Chromium).

### 7f. Lighthouse on the hosted frontend (2026-10-15)

* URL: https://healthcare-ai-frontend-1s23.onrender.com/ (dashboard only, read-only: no forms submitted, no sign-in).
* Tooling: Lighthouse 13.5.0 CLI (`npx lighthouse@13.5.0`), headless Google Chrome 155.0.8059.40 on macOS, one run per preset.
* Conditions: the frontend was asleep beforehand (a warm-up `GET /` took 12.6 s), so these are runs on a warmed instance. Lighthouse loads the page once and does not wait out a backend cold start. Single runs vary; these are not averages.

| Run (fetch time UTC) | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| Mobile (default), 13:50:18 | 96 | 96 | 96 | 90 |
| Desktop (`--preset=desktop`), 13:50:44 | 100 | 96 | 96 | 90 |

Mobile: FCP 1.4 s, LCP 1.9 s, TBT 0 ms, CLS 0.004. Desktop: FCP 0.4 s, LCP 0.5 s, TBT 0 ms, CLS 0.003.

Findings below 0.9:
* `html-has-lang` (WCAG 3.1.1). **Fixed** in this PR with `pages/_document.tsx` (`<html lang="en">`) and an E2E assertion on all four pages.
* `meta-description`. **Fixed**: a site description was added in `_document.tsx`.
* `errors-in-console`. The only error was a 404 for `/favicon.ico`. **Fixed** with an inline SVG icon link.
* `unused-javascript`, `legacy-javascript-insight`, `render-blocking-insight`, and mobile `speed-index` (0.67). Recorded, not changed: these are framework bundle and CSS delivery and out of scope.

The fixes are not yet deployed, so the hosted scores above are from **before** them. No score target is claimed.

### 7g. Accessibility findings, final for this PR (2026-10-15)

Evidence types:
* **Automated** means asserted by a committed Playwright or Vitest test.
* **Agent-observed** means I reviewed screenshots or tab-order listings produced by the browser; this is not a human tester.
* No human manual test or screen-reader test was performed. This is not a WCAG 2.2 AA conformance claim.

Pages: `/`, `/intake`, `/staff` (signed-out view, plus the signed-in queue, detail and FHIR flow in the smoke test) and `/system-card`. Browsers: Chromium 153, Firefox 155 and WebKit 26.6 (Playwright builds).

| Criterion | Pages | Result | Status | Evidence |
|---|---|---|---|---|
| 1.3.1 Info and relationships (landmarks, headings) | all 4, light and dark | One banner, main and contentinfo; labelled nav; exactly one h1 | PASS (automated) | `e2e/a11y.spec.ts` |
| 1.3.2 / 2.4.3 Meaningful sequence / Focus order | all 4 | Full Tab walk recorded: 31 stops on `/`, 13 on `/intake`, 10 on `/staff` (signed out), 13 on `/system-card`. Order is header → nav → main content in reading order. On `/staff`, the access-policy links come before the token field, matching the visual layout (policy card above the sign-in form) | PASS (automated walk + agent-observed order) | `e2e/a11y.spec.ts` (tab-order attachment), screenshot review |
| 1.4.3 / 1.4.11 Contrast | all (tokens) | Token pairs ≥ 4.5:1 for text and ≥ 3:1 for focus and borders, light and dark. Lighthouse colour-contrast audit passed on the hosted `/` (light) | PASS (token level + Lighthouse on `/`) | `tests/contrast.test.ts`, §7f |
| 1.4.4 Resize text | all 4 | Root font size 200% at 1280 px: no horizontal scrolling. Type is rem-based | PASS (automated proxy) | `e2e/a11y.spec.ts` |
| 1.4.10 Reflow / 200% zoom | all 4, light and dark | 320 CSS px and a 640 CSS px viewport at 2× scale (equivalent to 200% zoom of 1280 px): no horizontal scrolling. At 200% in dark theme the layout collapses to the mobile menu and focus rings remain visible | PASS (automated + agent-observed screenshot) | `e2e/a11y.spec.ts` |
| 2.1.1 Keyboard | intake, staff, nav | Intake completed and submitted with keyboard only; staff token field and Sign in reachable; menu opens with Enter and Escape closes it, returning focus | PASS (automated) | `e2e/a11y.spec.ts` |
| 2.3.3 / reduced motion | all 4 | No animation or transition over 10 ms with `prefers-reduced-motion: reduce` | PASS (automated) | `e2e/a11y.spec.ts` |
| 2.4.1 Bypass blocks | all 4 | Skip link is the first stop, visible, and focuses `main` | PASS (automated) | `e2e/a11y.spec.ts` |
| 2.4.7 Focus visible | all 4, every Tab stop | Outline ≥ 2 px or a box-shadow on every stop | PASS (automated) | `e2e/a11y.spec.ts` |
| 2.4.11 Focus not obscured (minimum) | all 4, every Tab stop | The site has no sticky or fixed UI. The point under the centre of each focused element's first line box is the element itself | PASS (automated) | `e2e/a11y.spec.ts` |
| 3.1.1 Language of page | all 4 | `lang` was missing (Lighthouse). Fixed with `<html lang="en">` | FIXED, PASS (automated) | `pages/_document.tsx`, `e2e/a11y.spec.ts` |
| 3.3.1 / 3.3.2 Errors, labels | intake, staff | `aria-invalid` on an empty token; errors use `role=alert`; unreachable-API errors render on every page | PASS (automated) | `e2e/*.spec.ts`, `tests/*` |
| 4.1.3 Status messages | intake, dashboard | Progress and system status use `role=status` | PASS (unit level) | `tests/IntakePage.test.tsx`, `tests/Dashboard.test.tsx` |
| Screen-reader output | all | VoiceOver is installed but was not run; it can't be driven and heard reliably from this environment | NOT VERIFIED (deferred) | — |
| Native Safari | all | Safari 18.1 is present, but WebDriver needs "Allow remote automation" turned on in Safari settings, which the session could not enable. WebKit 26.6 was used as a substitute | NOT VERIFIED (deferred) | — |

Defects found and fixed: missing page language (3.1.1). No critical keyboard or contrast failure was found.

### 7h. Remaining limitations

* There is no human screen-reader pass (VoiceOver or NVDA) and no native Safari run. Both need a person at the machine.
* Rendered-pixel contrast on every state (for example hover or disabled) was not measured beyond tokens and Lighthouse on `/`. Lighthouse was run on the hosted `/` only, not on `/intake`, `/staff` or `/system-card`.
* The hosted scores in §7f predate the `_document.tsx` fixes. Re-running after deployment is a post-merge check.
* CI runs Chromium only; Firefox and WebKit run locally with `E2E_ALL_BROWSERS=1`.
* Bundle re-scan after the final changes (2026-10-15): `NEXT_PUBLIC_*` is only `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_DEMO_MODE`. A grep of `.next/static` and the prerendered HTML for key, secret, database-URL, private-key and staff-token patterns found no matches.
* Final local run: 35 Playwright tests × 3 browsers = **105 passed** (4.3 min). 238 Vitest tests passed; lint, typecheck and build passed.
