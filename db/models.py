from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
    PrimaryKeyConstraint,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Required report sections (llm/schemas/report_output.json)
REPORT_SECTION_KEYS = (
    "overview",
    "symptom_analysis",
    "clinical_insights",
    "risk_summary",
    "recommendations",
)

# Data model v2 (db/migrations/002_clinics_users_review_status.sql)
# Clinic that /api/ingest assigns intakes to; seeded by migration 002.
DEFAULT_CLINIC_ID = "default"

ROLES = ("clinic_staff", "clinic_admin")

# submitted: stored, not flagged; needs_review / reviewed / escalated: staff review workflow
REVIEW_STATUSES = ("submitted", "needs_review", "reviewed", "escalated")
DEFAULT_REVIEW_STATUS = "submitted"


def _in_check(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(String, primary_key=True, default=lambda: uuid4().hex)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: uuid4().hex)
    email = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)


class ClinicMembership(Base):
    """A user's role within one clinic."""

    __tablename__ = "clinic_memberships"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "clinic_id"),
        CheckConstraint(_in_check("role", ROLES), name="ck_clinic_memberships_role"),
        Index("ix_clinic_memberships_clinic_id", "clinic_id"),
    )


class HealthRecord(Base):
    """
    Audit-ready persistence model for Healthcare AI pipeline outputs.

    Stores:
    - Intake (PHI-masked)
    - Structured output (clinical NLP)
    - Final report (JSON + human-readable summary)
    - Safety guard audit trail
    - Traceability & idempotency metadata
    """

    __tablename__ = "health_records"

    # Primary key 
    id = Column(String, primary_key=True, default=lambda: uuid4().hex)

    # Trace & versioning
    trace_id = Column(String, nullable=False)
    pipeline_version = Column(String, nullable=False)

    # Core payloads 
    intake_json = Column(JSON, nullable=False)
    structured_output_json = Column(JSON, nullable=False)   

    # Final output
    report_json = Column(JSON, nullable=False)
    
    # Human-readable report text built from report_json["report_sections"]
    report_text = Column(Text, nullable=False)

    # Safety / compliance audit
    safety_audit_json = Column(JSON, nullable=False)

    # Idempotency 
    input_hash = Column(String, nullable=True)

    # Clinic ownership & review workflow (v2)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    review_status = Column(
        String,
        nullable=False,
        default=DEFAULT_REVIEW_STATUS,
        server_default=DEFAULT_REVIEW_STATUS,
    )
    escalation_reason = Column(Text, nullable=True)

    # Timestamps 
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Constraints & Indexes 
    __table_args__ = (
        Index("ix_health_records_trace_id", "trace_id"),
        UniqueConstraint("input_hash", name="uq_health_records_input_hash"),
        CheckConstraint(
            _in_check("review_status", REVIEW_STATUSES),
            name="ck_health_records_review_status",
        ),
        Index("ix_health_records_clinic_review_status", "clinic_id", "review_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<HealthRecord id={self.id} "
            f"trace_id={self.trace_id} "
            f"pipeline_version={self.pipeline_version} "
            f"created_at={self.created_at}>"
        )

    @classmethod
    # Factory helper to build a HealthRecord from pipeline artifacts.
    def from_pipeline_trace(
        cls,
        *,
        trace_id: str,
        pipeline_version: str,
        intake: dict,
        structured_output: dict,
        report_json: dict,
        safety_audit: dict,
        input_hash: Optional[str] = None,
        clinic_id: str = DEFAULT_CLINIC_ID,
    ) -> "HealthRecord":
   
        # Deterministic extraction of human-readable report text
        # (section order follows llm/schemas/report_output.json)
        try:
            sections = report_json["report_sections"]
            report_text = "\n\n".join(
                f"{key}: {sections[key]}" for key in REPORT_SECTION_KEYS
            )
        except (KeyError, TypeError) as e:
            raise ValueError(
                "report_json missing report_sections "
                f"({', '.join(REPORT_SECTION_KEYS)})"
            ) from e

        return cls(
            trace_id=trace_id,
            pipeline_version=pipeline_version,
            intake_json=intake,
            structured_output_json=structured_output,
            report_json=report_json,
            report_text=report_text,
            safety_audit_json=safety_audit,
            input_hash=input_hash,
            clinic_id=clinic_id,
            review_status=DEFAULT_REVIEW_STATUS,
        )
