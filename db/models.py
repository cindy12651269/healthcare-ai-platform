from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


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
    
    # Human-readable summary extracted from:
    # report_json["clinical_structuring"]["clinical_summary"]
    report_text = Column(Text, nullable=False)

    # Safety / compliance audit
    safety_audit_json = Column(JSON, nullable=False)

    # Idempotency 
    input_hash = Column(String, nullable=True)

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
    ) -> "HealthRecord":
   
        # Deterministic extraction of human-readable report text
        try:
            report_text = (
                report_json["clinical_structuring"]["clinical_summary"]
            )
        except KeyError as e:
            raise ValueError(
                "report_json missing clinical_structuring.clinical_summary"
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
        )
