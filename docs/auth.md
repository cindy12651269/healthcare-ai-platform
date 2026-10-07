# Staff Authentication, RBAC & Clinic Isolation (Issue #28)

Code: `api/auth.py` (tokens, dependencies, operator CLI), `api/routers/clinics.py` (staff endpoints).
Data model: `users`, `clinics`, `clinic_memberships` ([`data_model.md`](data_model.md)).

Patient intake (`POST /api/ingest`) is unchanged: unauthenticated, same consent gate, and every intake is stored for the seeded `default` clinic. A `clinic_id` sent to `/api/ingest` is ignored.

---

## Authentication

**Mechanism:** staff send `Authorization: Bearer <token>`. A token is `v1.<payload>.<signature>`, where the payload is `{"sub": <user id>, "exp": <unix time>}` and the signature is HMAC-SHA256 with `AUTH_TOKEN_SECRET`. Tokens are issued by an operator from the command line; there is no login endpoint and no password storage.

```bash
python -m api.auth create-user --email admin@clinic.test --clinic default --role clinic_admin   # prints the user id
python -m api.auth issue-token --user-id <id>                                                    # prints a bearer token
```

**Why:** it is server-side, uses only the standard library (no new dependency or migration), and keeps the secret in the server environment. On every request the user and their clinic memberships are read from the database, so removing a membership or changing a role takes effect immediately even for an unexpired token. Trade-off: an individual token cannot be revoked before it expires except by deleting the user or rotating `AUTH_TOKEN_SECRET` (which invalidates all tokens). SSO / external identity providers are out of scope.

| Request | Result |
| --- | --- |
| No `Authorization` header, or a scheme other than `Bearer` | 401, `WWW-Authenticate: Bearer` |
| Malformed, tampered, wrongly signed or expired token, or unknown user | 401 |
| `AUTH_TOKEN_SECRET` unset or shorter than 32 characters | 503 on staff endpoints (no unsigned tokens are ever accepted); `/api/ingest` unaffected |

### Configuration (server environment only)

| Variable | Default | Purpose |
| --- | --- | --- |
| `AUTH_TOKEN_SECRET` | unset | HMAC key, ≥ 32 characters, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit it or put it in a `NEXT_PUBLIC_` variable. |
| `AUTH_TOKEN_TTL_HOURS` | `8` | Default lifetime of tokens issued by the CLI. |

The patient UI never receives tokens. The Staff Review UI (#31) takes an operator-issued token pasted by the staff member and keeps it in memory only; CORS allows the `Authorization` header from the configured origins, still without credentials ([`staff_review_ui.md`](staff_review_ui.md)).

---

## Roles and clinic isolation

Authorization is decided only from the caller's own rows in `clinic_memberships`. Clinic-scoped routes take the clinic from the path, and the caller must hold a membership for exactly that clinic; a clinic id in the query string or body is never used for authorization, and the admin request body rejects unknown fields (`clinic_id` → 422).

Reusable dependencies: `get_current_principal` (401 handling, loads memberships) and `require_clinic_role(*roles)` (403 if the caller is not a member of the path clinic or lacks a listed role).

| Endpoint | `clinic_staff` | `clinic_admin` | Other clinic / no membership |
| --- | --- | --- | --- |
| `GET /api/staff/me` — caller's id, email and memberships | ✓ | ✓ | ✓ (own data only) |
| `GET /api/clinics/{clinic_id}/members` | ✓ own clinic | ✓ own clinic | 403 |
| `PUT /api/clinics/{clinic_id}/members/{user_id}` body `{"role": "clinic_staff" \| "clinic_admin"}` — grant or change membership | 403 | ✓ own clinic | 403 |
| `DELETE /api/clinics/{clinic_id}/members/{user_id}` — remove membership | 403 | ✓ own clinic | 403 |

Minimal admin capability: a clinic admin grants, changes or removes memberships of existing users in their own clinic. Users are created by the operator CLI. An admin cannot change or remove their own membership (409), so a clinic cannot lose its admin by accident. Unknown user → 404; invalid role → 422.

The records and review-queue API (#30) uses the same `require_clinic_role` dependency; see [`review_queue_api.md`](review_queue_api.md).

---

## Tests

* `tests/test_auth_rbac.py` (SQLite): token signing/tampering/expiry; 401 for missing and invalid authentication; 503 without a secret; staff read allowed; staff management denied (403); admin grant/promote/remove; cross-clinic read and management denied; client-supplied `clinic_id` cannot bypass isolation; removed membership takes effect immediately; `/api/ingest` unauthenticated with the consent gate and default clinic unchanged.
* `tests/test_persistence_postgres.py::test_staff_auth_rbac_and_isolation_on_postgres` (PostgreSQL in CI): the same boundaries against the migrated schema.
