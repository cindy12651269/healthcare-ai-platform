# Screenshots

Actual captures of the hosted demo at https://healthcare-ai-frontend-1s23.onrender.com, used by the repository [README](../../README.md). No mockups, design comps or generated images. Every screenshot shows synthetic data only and contains no token, secret, `Authorization` header or real personal data. The seeded staff e-mail addresses (`admin-a@demo.example.test`, `admin-b@demo.example.test`) are synthetic identities on the reserved `.test` domain.

The date in each filename is the **capture date** (UTC). Images captured for an earlier issue keep their original date: they are reused with that date, not presented as new captures.

## Captured for #73 on 2026-10-16 (public pages, read-only)

Captured by [`capture-hosted-public.mjs`](capture-hosted-public.mjs) at 05:43:02–05:43:12 UTC with headless Chromium (Playwright 1.63, light theme, `en-US`, UTC). Viewport 1280 × 900 at 1× for desktop, 390 × 844 at 2× for mobile; viewport only, not full page. Converted from PNG to JPEG (quality 82) with `sips`; no other edit.

* No sign-in and no bearer token. No intake was submitted: choosing a scenario card only fills the text field, and consent stayed unticked.
* [`capture-log-2026-10-16.json`](capture-log-2026-10-16.json) lists every request (method and URL only, no headers): 132 GET requests, **0 non-GET**. The API received 5 × `GET /health` and 1 × `GET /api/system-card`.
* Browser storage and cookies were empty on every page.
* Deployed frontend at capture time: the #72 build (PR #87, merge `68db16a`). The served `/` has the `<html lang="en">` and the meta description that only that build contains. API `/health`: `{"status":"ok","environment":"demo","llm_mode":"mock"}`.

| File | Subject |
| --- | --- |
| `dashboard-desktop-2026-10-16.jpg` | Product dashboard, 1280 px: product statement, live system status from `/health` (*Reachable*, `demo`, `mock`), workflow and *What is real vs. mock* |
| `dashboard-mobile-2026-10-16.jpg` | Product dashboard, 390 px, collapsed navigation |
| `intake-form-routine-selected-desktop-2026-10-16.jpg` | Patient intake with the *Routine symptoms* scenario selected (not submitted); each card shows its expected outcome |
| `staff-signin-access-policy-desktop-2026-10-16.jpg` | Staff sign-in with the public-demo access policy (tokens issued on request, never published); token field empty |
| `system-card-desktop-2026-10-16.jpg` | System card / AI transparency: *Not a medical device* notice and known limitations |

## Reused from verified Phase 8 hosted evidence (2026-10-15)

Cropped from full-page screenshots already committed under [`../project_journal/evidence/`](../project_journal/evidence/). Crop and JPEG re-encode (quality 82) with `sips`; no pixel edits. The originals and their verification are in the [Phase 8 journal](../project_journal/phase8_Frontend_Experience_&_Portfolio_Presentation.md).

| File | Subject | Source (original capture) | Journal |
| --- | --- | --- | --- |
| `intake-outcome-routine-submitted-desktop-2026-10-15.jpg` | Routine outcome: *Submitted*, stored with no review flag, rule-based extraction note. The unique synthetic probe text from the #70 webhook pre-check, sent 11:25:42 UTC | `phase8_issue70_hosted_frontend_2026-10-15/probe-routine-unique-1280-light.jpg` | §5d |
| `intake-outcome-emergency-flagged-desktop-2026-10-15.jpg` | Emergency preset outcome: urgent-care guidance first, `emergency_signal` rule matched | `phase8_issue70_hosted_frontend_2026-10-15/result-emergency-1280-light.jpg` | §5d |
| `intake-outcome-emergency-flagged-mobile-2026-10-15.jpg` | Same outcome, 390 px | `phase8_issue70_hosted_frontend_2026-10-15/result-emergency-390-light.jpg` | §5d |
| `staff-queue-clinic-b-desktop-2026-10-15.jpg` | Staff queue for `demo-admin-b` (clinic `demo-clinic-b` only), status tabs with counts, distinct references after #84 | `phase8_issue84_hosted_2026-10-15/queue-all-1280-light.jpg` (uncropped copy) | §6f |
| `staff-queue-clinic-b-mobile-2026-10-15.jpg` | Same queue, 390 px | `phase8_issue84_hosted_2026-10-15/queue-all-390-light.jpg` (uncropped copy) | §6f |
| `staff-detail-reviewed-desktop-2026-10-15.jpg` | `demo-admin-a` (clinic `default`): queue beside the intake detail after *Mark reviewed* | `phase8_issue71_hosted_frontend_2026-10-15/a-detail-after-1280-light.jpg` (top) | §6d |
| `staff-detail-evidence-timeline-desktop-2026-10-15.jpg` | Same intake: *Why flagged* evidence, original input vs. extracted fields, provenance (`mock`), timeline ending in the staff action, *No webhook delivery is recorded* | same file (detail column, lower part) | §6d |
| `staff-fhir-export-preview-desktop-2026-10-15.jpg` | FHIR R4 export panel: disclaimer, resource summary (7 entries), collapsed-by-default JSON preview opened | `phase8_issue71_hosted_frontend_2026-10-15/a-fhir-preview-1280-light.jpg` (FHIR section) | §6d |

**What the reused images show, honestly:**

* The **emergency outcome is a duplicate submission.** The preset text was already stored, so the badge reads *Already received · no new record* and the page says nothing new was added to the queue. The safety guidance and the matched rule are real API output for that submission. No new flagged text was sent to obtain a *Flagged for staff review* badge (§5d).
* The staff captures used **1-hour tokens issued by the account owner** under the #67 procedure. The tokens were never shown, stored in the repository or committed, and were deleted after the run (§6d, §6f). The only hosted data changes were the two #71 verification transitions (`2f005d14…` reviewed, `demo-intake-b2` escalated); the queue capture comes from the read-only #84 run.
* The staff workspace was **not** re-captured for #73: no new token was issued and no hosted staff record was touched.

## Re-capturing

From the repository root, with `app/` dependencies and the Playwright Chromium build installed:

```bash
node docs/screenshots/capture-hosted-public.mjs <output-dir> <yyyy-mm-dd>
```

The script exits non-zero if the page makes any non-GET request other than a CORS preflight. It never signs in.
