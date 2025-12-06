from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Human-readable and PHI-free narrative report sections.
class ReportSections(BaseModel):
    overview: str = Field(..., description="High-level summary of the user's health concerns.")
    symptom_analysis: str = Field(..., description="Narrative analysis of symptoms and patterns.")
    clinical_insights: str = Field(..., description="Non-diagnostic clinical-style insights.")
    risk_summary: str = Field(..., description="Potential risks or patterns, PHI-free.")
    recommendations: str = Field(..., description="Safe wellness or monitoring suggestions.")

# Safety validation ensuring the report does not contain PHI and is non-diagnostic.
class SafetyChecks(BaseModel):
    diagnostic_check_passed: bool = Field(
        ..., description="Ensures the LLM did NOT generate medical diagnoses."
    )
    phi_safe: bool = Field(
        ..., description="True if the system confirmed all content contains no PHI."
    )
    compliance_notes: Optional[str] = Field(
        None, description="Optional compliance notes for audit logs."
    )

# Metadata for auditing and reproducibility. This supports HIPAA audit requirements.
class ReportMetadata(BaseModel):
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of report generation in ISO-8601 format."
    )
    model_version: str = Field(..., description="LLM version used to generate the report.")
    prompt_version: str = Field(..., description="Prompt template version.")
    latency_ms: Optional[float] = Field(
        None, description="Optional latency measurement of LLM call."
    )

#  Final LLM-generated report object. This is validated after LLM response before being returned to API clients.
class ReportOutput(BaseModel):
    source_struct_id: str = Field(
        ..., description="ID linking back to structured_output that produced this report."
    )
    report_sections: ReportSections = Field(
        ..., description="Human-readable, PHI-free report sections."
    )
    input_context: Optional[str] = Field(
        None,
        max_length=200,
        description="Optional short descriptor of the input source. Must be PHI-free."
    )
    safety_checks: SafetyChecks = Field(
        ..., description="Ensures content safety, PHI compliance, non-diagnostic behavior."
    )
    report_metadata: ReportMetadata = Field(
        ..., description="Audit metadata for compliance and reproducibility."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source_struct_id": "struct_12345",
                "report_sections": {
                    "overview": "The user reports intermittent fatigue and low energy.",
                    "symptom_analysis": "Symptoms appear correlated with inconsistent sleep patterns.",
                    "clinical_insights": "The pattern suggests lifestyle contributors, not clinical diagnosis.",
                    "risk_summary": "No immediate red flags. Mild risk relating to prolonged poor sleep quality.",
                    "recommendations": "Consider consistent sleep schedule, hydration, and journaling symptoms."
                },
                "input_context": "intake_form",
                "safety_checks": {
                    "diagnostic_check_passed": True,
                    "phi_safe": True,
                    "compliance_notes": "Validated by Pydantic model."
                },
                "report_metadata": {
                    "generated_at": "2025-01-15T05:30:00Z",
                    "model_version": "gpt-4o-2025-01",
                    "prompt_version": "v1.0",
                    "latency_ms": 563.2
                }
            }
        }
