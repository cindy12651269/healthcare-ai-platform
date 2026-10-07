"""
Staff records and review-queue endpoints (Issue #30). Every route is
clinic-scoped through api.auth (the caller must hold a staff or admin
membership of the `{clinic_id}` in the path), and every query filters on that
authorized clinic, so another clinic's intakes are never listed and read as 404.
Each successful call emits an audit event with the actor, action and intake id.
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.auth import Principal, require_clinic_role
from db.models import HealthRecord
from db.session import get_db
from observability.audit_logger import build_event, log_run

router = APIRouter()

staff_or_admin = require_clinic_role("clinic_staff", "clinic_admin")

ReviewStatus = Literal["submitted", "needs_review", "reviewed", "escalated"]

# Staff transitions: only an intake waiting for review can be resolved; everything else is rejected (409)
ALLOWED_TRANSITIONS: Dict[str, frozenset] = {
    "needs_review": frozenset({"reviewed", "escalated"}),
}


class IntakeSummary(BaseModel):
    id: str
    trace_id: str
    review_status: str
    escalation_reason: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class IntakeDetail(IntakeSummary):
    clinic_id: str
    structured: Dict[str, Any]
    report: Dict[str, Any]
    safety: Dict[str, Any]


class TransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_status: Literal["reviewed", "escalated"]


def _summary(r: HealthRecord) -> Dict[str, Any]:
    return dict(
        id=r.id,
        trace_id=r.trace_id,
        review_status=r.review_status,
        escalation_reason=r.escalation_reason,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _detail(r: HealthRecord) -> IntakeDetail:
    return IntakeDetail(
        **_summary(r),
        clinic_id=r.clinic_id,
        structured=r.structured_output_json,
        report=r.report_json,
        safety=r.safety_audit_json,
    )


def _get_owned(db: Session, clinic_id: str, intake_id: str) -> HealthRecord:
    record = (
        db.query(HealthRecord)
        .filter(HealthRecord.id == intake_id, HealthRecord.clinic_id == clinic_id)
        .one_or_none()
    )
    if record is None:
        # Same response whether the intake is missing or owned by another clinic
        raise HTTPException(status_code=404, detail="Intake not found")
    return record


def _audit(principal: Principal, action: str, clinic_id: str, started: float, *, resource_id=None, **flags):
    log_run(
        build_event(
            run_id=uuid4().hex,
            status="success",
            latency_ms=int((time.perf_counter() - started) * 1000),
            safety_violation_count=0,
            retrieval_hit_count=0,
            flags={"clinic_id": clinic_id, **flags},
            actor_id=principal.user_id,
            action=action,
            resource_id=resource_id,
        )
    )


@router.get("/clinics/{clinic_id}/intakes", response_model=List[IntakeSummary])
def list_intakes(
    clinic_id: str,
    review_status: Optional[ReviewStatus] = None,
    principal: Principal = Depends(staff_or_admin),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    query = db.query(HealthRecord).filter(HealthRecord.clinic_id == clinic_id)
    if review_status is not None:
        query = query.filter(HealthRecord.review_status == review_status)
    rows = query.order_by(HealthRecord.created_at.desc(), HealthRecord.id).all()

    _audit(principal, "intake.list", clinic_id, started, review_status=review_status, result_count=len(rows))
    return [IntakeSummary(**_summary(r)) for r in rows]


@router.get("/clinics/{clinic_id}/intakes/{intake_id}", response_model=IntakeDetail)
def get_intake(
    clinic_id: str,
    intake_id: str,
    principal: Principal = Depends(staff_or_admin),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    record = _get_owned(db, clinic_id, intake_id)

    _audit(principal, "intake.read", clinic_id, started, resource_id=record.id)
    return _detail(record)


@router.post("/clinics/{clinic_id}/intakes/{intake_id}/transition", response_model=IntakeDetail)
def transition_intake(
    clinic_id: str,
    intake_id: str,
    body: TransitionIn,
    principal: Principal = Depends(staff_or_admin),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    record = _get_owned(db, clinic_id, intake_id)
    current = record.review_status

    if body.review_status not in ALLOWED_TRANSITIONS.get(current, ()):
        raise HTTPException(
            status_code=409,
            detail=f"Transition {current} -> {body.review_status} is not allowed",
        )

    # Conditional update so two concurrent transitions cannot both succeed
    updated = (
        db.query(HealthRecord)
        .filter(
            HealthRecord.id == record.id,
            HealthRecord.clinic_id == clinic_id,
            HealthRecord.review_status == current,
        )
        .update({HealthRecord.review_status: body.review_status}, synchronize_session=False)
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Intake status changed concurrently; reload and retry")
    db.commit()
    db.refresh(record)

    _audit(
        principal,
        "intake.transition",
        clinic_id,
        started,
        resource_id=record.id,
        from_status=current,
        to_status=record.review_status,
    )
    return _detail(record)
