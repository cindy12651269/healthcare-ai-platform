# Phase 8 — Frontend Experience & Portfolio Presentation

Healthcare AI Platform
Timeline: Phase 8 (from 2026-10-14)
Scope: Issues #67–#69 (items 1–3 of 7) so far
Status: In progress — #67 closed (2026-10-14): PR #74 merged (`f84a1da`, `main` CI run 38537057498 — success); hosted API validated (§2a) and hosted frontend deployed and verified (§2c). #68 closed (2026-10-14): PR #76 merged (`ba028df`); hosted frontend verified on the public pages (§3c), signed-in staff workspace pending a token.

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

**Status:** implemented on branch `feat/issue-69-product-dashboard`; in review. No backend change, no new endpoint, no API-contract, auth, RBAC, clinic-isolation or workflow change; no new dependency (`app/package.json` unchanged). The hosted frontend still serves the #68 build (`ba028df`); nothing here is hosted-verified.

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

* **Hosted validation: pending.** The hosted frontend serves the #68 build; this branch is not deployed and no Render change was made.
* The unavailable and waking dashboard states are covered by unit tests, not by browser screenshots (the real wake window is ~75–105 s).
* The API's pipeline text still states the webhook unconditionally (see wording review); the UI qualifies it in place, the source text is unchanged.

**Review Gate (2026-10-14).** The first candidate (`8dff155`) qualified the webhook only in a small note below the pipeline grid, after the unconditional stage text, and the dashboard's webhook card opened with *"one … notification per escalation"*. Fixed with frontend wording only (above); tests, lint, typecheck, build and the 30-run browser matrix re-run (0 overflow, no target < 44 × 44, no clipped content); screenshots refreshed.
* Chrome only; Safari/Firefox, physical devices and 200 % zoom are #72.
