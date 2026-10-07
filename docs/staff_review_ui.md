# Staff Review UI (Issue #31)

Code: `app/pages/staff.tsx` (route `/staff`), `app/components/StaffReview.tsx`, `app/services/staffApi.ts`. Tests: `app/tests/StaffReview.test.tsx`.

The patient intake page (`/`) and its developer trace panel are unchanged.

## Sign-in and session

* Staff paste the bearer token issued by an operator with the #28 CLI (`python -m api.auth issue-token`). There is no login endpoint, password or new auth mechanism.
* The UI verifies the token with `GET /api/staff/me` and uses the first clinic membership (a selector appears when there are several).
* The token is kept only in React state for the open tab: it is not written to `localStorage`, `sessionStorage` or cookies, and is cleared on sign-out or reload.
* No server secret reaches the browser. The only `NEXT_PUBLIC_` variable is the existing `NEXT_PUBLIC_API_BASE_URL`.
* The backend remains the authorization boundary: every call is checked by `require_clinic_role` and clinic-scoped queries (#28, #30). The UI only hides buttons that the server would reject anyway.
* CORS now allows the `Authorization` request header from the configured origins so the browser can send the token. Credentials (cookies) are still not allowed.

## Workflow

1. **Queue:** `GET /api/clinics/{clinic_id}/intakes?review_status=…`, filterable by Needs review (default), Reviewed, Escalated, Submitted or All. Rows show received time, status and escalation reason.
2. **Detail:** `GET /api/clinics/{clinic_id}/intakes/{id}` shows review status, escalation reason, structured summary, report sections and safety result.
3. **Transition:** for a `needs_review` intake, Mark reviewed / Mark escalated call `POST …/{id}/transition` with `{"review_status": …}`. Buttons are disabled while the request is in flight and hidden once the intake is no longer `needs_review`. The queue is refetched after a transition.

Errors: 401 returns to sign-in with an expired-session message. 403 shows "no staff access". 404 shows "not found". On 409 the intake and queue are reloaded so the server's current state wins. 422, other HTTP errors and network failures show a retryable error in place.

## Browser check (flagged intake → sign-in → queue → open → transition)

Executed locally on 2026-10-07 against a throwaway SQLite database in mock mode, with the backend on :8000 and `next dev` on :3000:

```bash
export DATABASE_URL=sqlite:////tmp/demo.db LLM_MODE=mock ENABLE_AUDIT_JSONL=false \
       AUTH_TOKEN_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
python - <<'PY'
from db.session import init_db, transactional_session
from db.models import Clinic
init_db()
with transactional_session() as db:
    db.add(Clinic(id="default", name="Demo Clinic"))
PY
STAFF=$(python -m api.auth create-user --email staff@clinic.test --clinic default --role clinic_staff)
python -m api.auth issue-token --user-id $STAFF        # token for the sign-in form
uvicorn api.main:app --port 8000 &
(cd app && npx next dev -p 3000 &)
curl -X POST localhost:8000/api/ingest -H 'Content-Type: application/json' \
  -d '{"text":"I have chest pain and shortness of breath since this morning.","consent_granted":true}'
```

With PostgreSQL (`docker compose up`), apply the migrations instead of `init_db()`; migration 002 seeds the `default` clinic.

Observed in Chrome at `http://localhost:3000/staff`:

1. An invalid token: the CORS preflight succeeded, `GET /api/staff/me` returned 401, and the sign-in error was shown.
2. The issued token: signed in as `staff@clinic.test` (clinic `default`, `clinic_staff`). The Needs review queue listed the flagged intake with reason `emergency_signal`, and did not list the normal (`submitted`) intake.
3. Opened the intake: review status, escalation reason, structured summary, report (including the unchanged emergency guidance) and safety result (severity high, `add_emergency_guidance`) were shown.
4. Mark escalated: `POST …/transition` returned 200, "Marked escalated." was shown, the transition buttons disappeared, and the Needs review queue refetched as empty. The Escalated filter listed the intake.
5. Server state: the record was `escalated` with `escalation_reason = emergency_signal`, and the normal intake was still `submitted`. Audit events `intake.list`, `intake.read` and `intake.transition` carried the staff `actor_id`, and the API log contained no intake text.
6. The patient page `/` still rendered the intake form unchanged.
