"""
Deterministic synthetic demo seed for the hosted demo (Issue #35).

Creates a second clinic and three staff users with fixed ids, so the hosted
acceptance flow (flagged intake -> correct clinic's review queue -> signed
webhook) and cross-clinic denial can be exercised. Idempotent: existing rows
are left unchanged, so it is safe to run on every deploy after migrations.

No passwords or tokens are created here. Tokens are issued by an operator with
`python -m api.auth issue-token --user-id <id>` (docs/deployment.md).

Usage:
    python -m db.seed_demo
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from db.models import DEFAULT_CLINIC_ID, Clinic, ClinicMembership, User

logger = logging.getLogger("db.seed_demo")

# Synthetic only. example.test is a reserved, non-routable domain (RFC 2606).
DEMO_CLINICS = (
    (DEFAULT_CLINIC_ID, "Default Clinic"),  # also seeded by migration 002; receives all public intakes
    ("demo-clinic-b", "Demo Clinic B"),
)
DEMO_USERS = (
    # (user id, email, display name, clinic, role)
    ("demo-staff-a", "staff-a@demo.example.test", "Demo Staff A", DEFAULT_CLINIC_ID, "clinic_staff"),
    ("demo-admin-a", "admin-a@demo.example.test", "Demo Admin A", DEFAULT_CLINIC_ID, "clinic_admin"),
    ("demo-admin-b", "admin-b@demo.example.test", "Demo Admin B", "demo-clinic-b", "clinic_admin"),
)


def seed_demo(db: Session) -> List[str]:
    """Insert missing demo rows. Returns a description of each row created in this call."""
    created: List[str] = []

    for clinic_id, name in DEMO_CLINICS:
        if db.get(Clinic, clinic_id) is None:
            db.add(Clinic(id=clinic_id, name=name))
            created.append(f"clinic {clinic_id}")
    db.flush()

    for user_id, email, display_name, clinic_id, role in DEMO_USERS:
        if db.get(User, user_id) is None:
            db.add(User(id=user_id, email=email, display_name=display_name))
            created.append(f"user {user_id}")
        db.flush()
        if db.get(ClinicMembership, (user_id, clinic_id)) is None:
            db.add(ClinicMembership(user_id=user_id, clinic_id=clinic_id, role=role))
            created.append(f"membership {user_id}@{clinic_id}:{role}")

    db.flush()
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    from db.session import transactional_session

    with transactional_session() as session:
        rows = seed_demo(session)
    logger.info(f"Demo seed complete ({len(rows)} rows created)")
