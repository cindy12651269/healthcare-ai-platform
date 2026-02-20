from __future__ import annotations
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from api.config import get_settings
from db.models import Base

# Engine Initialization
settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    future=True,
    pool_pre_ping=True,  # avoids stale connections
)

# Session factory (NOT a session instance)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


# DB Initialization (optional helper)
# Initialize database tables. Used for Local development, and CI test environments
def init_db() -> None:
    Base.metadata.create_all(bind=engine)

# FastAPI Dependency
# Ensures: session is created per request, rollback on failure, and always closed properly.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Manual Transaction Context (for internal pipeline use)
@contextmanager
def transactional_session() -> Generator[Session, None, None]:
    """
    Context manager for non-FastAPI usage (e.g., pipeline-level persistence).
    Example:
        with transactional_session() as db:
            db.add(record)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()