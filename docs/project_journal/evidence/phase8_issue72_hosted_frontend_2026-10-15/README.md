# Issue #72: post-deployment hosted validation (2026-10-15)

Read-only checks of https://healthcare-ai-frontend-1s23.onrender.com after PR #87 (merge `68db16a`) was deployed:
* No form was submitted, nobody signed in, no staff transition was made, and no webhook was involved.
* The API was blocked only inside the test browser, using Playwright request routing.

| File | Content |
|---|---|
| `lighthouse_summary.json` | Lighthouse 13.5.0 scores, metrics and failing audits, before and after deployment (single runs) |
| `hosted_checks_results.json` | 45 Playwright checks (Chromium 153, Firefox 155, WebKit 26.6): status, Tab-stop counts, console errors and favicon requests per page |
| `hosted_checks.spec.ts.txt` | The spec that produced these results (evidence copy, not part of the repo suite) |
| `*-skiplink-1280-{light,dark}.jpg` | Skip link focused, 1280 px, both themes |
| `*-zoom200-{light,dark}.jpg` | 640 CSS px at 2× (200% zoom of 1280 px), both themes |
| `*-390-light.jpg` | 390 px mobile viewport |
| `404-1280-light.jpg` | Styled 404 for `/does-not-exist-issue-72` |
| `dashboard-api-blocked-1280-light.jpg` | Dashboard with the API blocked in the browser: "Unavailable", "Unreachable", "Try again" |

Page prefixes: `dashboard` (`/`), `intake`, `staff` (signed-out view), `system-card`.
