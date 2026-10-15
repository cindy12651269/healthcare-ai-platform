#!/usr/bin/env bash
# Throwaway PostgreSQL 15 container for local browser E2E (#72): no volume, bound to 127.0.0.1:54329,
# separate from the Compose `db` service and its data. CI uses its own PostgreSQL service instead.
# Usage: scripts/e2e_local_db.sh start|stop
# Then (in app/): E2E_DATABASE_URL=postgresql+psycopg2://e2e:e2e@127.0.0.1:54329/healthcare_e2e npm run e2e
set -euo pipefail
NAME=healthcare-e2e-pg
case "${1:-}" in
  start)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --rm --name "$NAME" -e POSTGRES_USER=e2e -e POSTGRES_PASSWORD=e2e -e POSTGRES_DB=healthcare_e2e \
      -p 127.0.0.1:54329:5432 postgres:15 >/dev/null
    for _ in $(seq 1 60); do
      docker exec "$NAME" pg_isready -U e2e -d healthcare_e2e >/dev/null 2>&1 && break
      sleep 1
    done
    echo "postgresql+psycopg2://e2e:e2e@127.0.0.1:54329/healthcare_e2e"
    ;;
  stop) docker rm -f "$NAME" >/dev/null ;;
  *) echo "usage: $0 start|stop" >&2; exit 2 ;;
esac
