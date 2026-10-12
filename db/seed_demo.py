"""
Deterministic synthetic demo seed for the hosted demo (Issue #35).

Creates a second clinic and three staff users with fixed ids, so the hosted
acceptance flow (flagged intake -> correct clinic's review queue -> signed
webhook) and cross-clinic denial can be exercised. Idempotent: existing rows
are left unchanged, so it is safe to run on every deploy after migrations.

Issue #43: also seeds eight synthetic intakes with fixed ids, four per clinic,
covering every review status, so each clinic's queue and isolation are visible
on first sign-in. Each is processed by the real pipeline in mock mode (no
persistence, so no webhook is sent); the review status and reason are the
pipeline's own. `reviewed` / `escalated` intakes get one seeded transition by a
demo staff user, recorded in review_events like a real one. The texts are
synthetic and the seeded transitions are demo history, not real staff actions.

The CLI refuses to run unless APP_ENV=demo (render.yaml sets it for the hosted demo).

No passwords or tokens are created here. Tokens are issued by an operator with
`python -m api.auth issue-token --user-id <id>` (docs/deployment.md).

Usage:
    python -m db.seed_demo
"""
from __future__ import annotations

import logging
import os
import sys
from typing import List

from sqlalchemy.orm import Session

from db.models import DEFAULT_CLINIC_ID, Clinic, ClinicMembership, HealthRecord, ReviewEvent, User

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


# (intake id, clinic, synthetic text, status the pipeline must assign, staff transition or None)
DEMO_INTAKES = (
    ("demo-intake-a1", DEFAULT_CLINIC_ID, "I have had a sore throat and a mild fever for two days.", "submitted", None),
    ("demo-intake-a2", DEFAULT_CLINIC_ID, "I have chest pain and shortness of breath since this morning.", "needs_review", None),
    ("demo-intake-a3", DEFAULT_CLINIC_ID, "I just don't feel right lately.", "needs_review", ("demo-staff-a", "reviewed")),
    ("demo-intake-a4", DEFAULT_CLINIC_ID, "Should I take 400 mg of ibuprofen for my knee?", "needs_review", ("demo-admin-a", "escalated")),
    ("demo-intake-b1", "demo-clinic-b", "I have a cough and a runny nose since yesterday.", "submitted", None),
    ("demo-intake-b2", "demo-clinic-b", "Something feels off and I wanted to check in.", "needs_review", None),
    ("demo-intake-b3", "demo-clinic-b", "I fainted twice this morning and feel dizzy.", "needs_review", ("demo-admin-b", "escalated")),
    ("demo-intake-b4", "demo-clinic-b", "I am not sure what is wrong, I just feel unwell.", "needs_review", ("demo-admin-b", "reviewed")),
)


def _demo_pipeline():
    # Always mock, whatever LLM_MODE is: the seed never calls a provider
    from agents.output_agent import OutputAgent
    from agents.pipeline import HealthcarePipeline
    from agents.structuring_agent import StructuringAgent

    return HealthcarePipeline(
        structuring_agent=StructuringAgent(mode="mock"),
        output_agent=OutputAgent(mode="mock"),
        retrieval_agent=None,
        enable_retrieval=False,
    )


def seed_demo_intakes(db: Session) -> List[str]:
    created: List[str] = []
    pipeline = None
    for idx, (intake_id, clinic_id, text, expected_status, transition) in enumerate(DEMO_INTAKES):
        if db.get(HealthRecord, intake_id) is not None:
            continue
        pipeline = pipeline or _demo_pipeline()
        trace = pipeline.run(
            raw_text=text,
            meta={"source": "web", "input_type": "chat", "user_id": f"demo-patient-{idx + 1}", "consent_granted": True},
            enable_rag=False,
            persistence_enabled=False,
            seed=42 + idx,
            run_id=f"demo-seed:{intake_id}",
        )
        escalation = trace.get("escalation") or {}
        status = escalation.get("review_status")
        if not trace.get("success") or status != expected_status:
            raise RuntimeError(f"Demo intake {intake_id}: pipeline returned {status!r}, expected {expected_status!r}")

        record = HealthRecord.from_pipeline_trace(
            trace_id=trace["run_id"],
            pipeline_version=_pipeline_version(),
            intake=trace["intake"],
            structured_output=trace["structured"],
            report_json=trace["report"],
            safety_audit=trace["safety"],
            clinic_id=clinic_id,
            review_status=status,
            escalation_reason=",".join(escalation.get("reasons") or []) or None,
        )
        record.id = intake_id
        db.add(record)
        db.flush()
        created.append(f"intake {intake_id}@{clinic_id}:{status}")

        if transition:
            actor_id, to_status = transition
            record.review_status = to_status
            db.add(ReviewEvent(intake_id=intake_id, clinic_id=clinic_id, actor_id=actor_id,
                               from_status=status, to_status=to_status))
            db.flush()
            created.append(f"transition {intake_id}:{status}->{to_status} by {actor_id}")
    return created


def _pipeline_version() -> str:
    from api.config import get_settings

    return get_settings().pipeline_version


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
    created.extend(seed_demo_intakes(db))
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    if os.getenv("APP_ENV", "").lower() != "demo":
        logger.error("Refusing to seed demo data: APP_ENV is not 'demo'")
        sys.exit(2)
    from db.session import transactional_session

    with transactional_session() as session:
        rows = seed_demo(session)
    logger.info(f"Demo seed complete ({len(rows)} rows created)")
