#!/usr/bin/env bash
# Browser E2E backend (#72): migrate an isolated local test database, create a test-only staff user,
# issue a short-lived test token, then serve the API in mock mode. Never points at the hosted demo.
#   E2E_DATABASE_URL  required; must be a localhost PostgreSQL URL for a throwaway test database
#   E2E_TOKEN_FILE    where the test token is written (default app/e2e/.auth/staff-token, git-ignored)
set -euo pipefail
cd "$(dirname "$0")/.."

: "${E2E_DATABASE_URL:?E2E_DATABASE_URL must point at a local test database}"
case "$E2E_DATABASE_URL" in
  *@localhost:*|*@127.0.0.1:*) ;;
  *) echo "Refusing to run E2E against a non-local database" >&2; exit 2 ;;
esac

PY="${PYTHON:-python3}"
TOKEN_FILE="${E2E_TOKEN_FILE:-app/e2e/.auth/staff-token}"

export DATABASE_URL="$E2E_DATABASE_URL"
export APP_ENV=test LLM_MODE=mock OPENAI_API_KEY=""
# No webhook receiver: both empty disables delivery (api/webhook.py) and overrides any value in .env.
export WEBHOOK_URL="" WEBHOOK_SECRET=""
export CORS_ALLOWED_ORIGINS="http://127.0.0.1:3010"
# Test-only signing secret generated per run; never written to disk.
export AUTH_TOKEN_SECRET="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')"

"$PY" -m db.migrate
user_id="$("$PY" -m api.auth create-user --email "e2e-$(date +%s)-$$@e2e.example.test" --display-name "E2E Staff" --clinic default --role clinic_staff | tail -n 1)"
mkdir -p "$(dirname "$TOKEN_FILE")"
( umask 077; "$PY" -m api.auth issue-token --user-id "$user_id" --ttl-hours 1 | tail -n 1 > "$TOKEN_FILE" )

exec "$PY" -m uvicorn api.main:app --host 127.0.0.1 --port 8010
