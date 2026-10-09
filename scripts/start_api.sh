#!/bin/sh
# Hosted demo start (Issue #35, render.yaml): migrations, then the idempotent synthetic demo seed,
# then the server. `set -e` stops the start if either step fails, so /health never passes on an
# unmigrated database.
set -e

# Render's connectionString is postgresql://…; SQLAlchemy 2.1 maps that scheme to psycopg (v3),
# which is not installed. Pin the installed psycopg2 driver (requirements.txt).
case "$DATABASE_URL" in
  postgresql://*) DATABASE_URL="postgresql+psycopg2://${DATABASE_URL#postgresql://}" ;;
  postgres://*) DATABASE_URL="postgresql+psycopg2://${DATABASE_URL#postgres://}" ;;
esac
export DATABASE_URL

python -m db.migrate
python -m db.seed_demo
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
