#!/bin/sh
# Hosted demo start (Issue #35, render.yaml): migrations, then the idempotent synthetic demo seed,
# then the server. `set -e` stops the start if either step fails, so /health never passes on an
# unmigrated database.
set -e
python -m db.migrate
python -m db.seed_demo
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
