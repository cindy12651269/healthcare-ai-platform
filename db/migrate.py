"""
Apply the SQL migrations in db/migrations/ in filename order.

Applied files are recorded in schema_migrations, so the runner is safe to
run on every start, against a new or an existing database.

Usage:
    python -m db.migrate
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List
from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

logger = logging.getLogger("db.migrate")


def run_migrations(engine: Engine, migrations_dir: Path = MIGRATIONS_DIR) -> List[str]:
    """Apply pending migrations. Returns the filenames applied in this call."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        ))
        applied = set(conn.execute(text("SELECT filename FROM schema_migrations")).scalars())

    newly_applied: List[str] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        # One transaction per file: the SQL and its schema_migrations row commit together
        with engine.begin() as conn:
            conn.exec_driver_sql(path.read_text())
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": path.name},
            )
        logger.info(f"Applied migration {path.name}")
        newly_applied.append(path.name)

    return newly_applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    from db.session import engine

    applied_now = run_migrations(engine)
    logger.info(f"Migrations complete ({len(applied_now)} applied)")
