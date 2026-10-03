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

# Required report sections (llm/schemas/report_output.json)
REPORT_SECTION_KEYS = (
    "overview",
    "symptom_analysis",
    "clinical_insights",
    "risk_summary",
    "recommendations",
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
        )
