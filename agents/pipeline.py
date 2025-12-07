import logging
from typing import Any, Dict
from agents.intake_agent import process_raw_input, IntakeValidationError
from agents.structuring_agent import (
    StructuringAgent,
    StructuringError,
    JSONParsingError,
    SchemaValidationError,
)
from agents.output_agent import OutputAgent

logger = logging.getLogger(__name__)

# Production-grade pipeline: Raw → Intake → Structuring → Output Report
class HealthcarePipeline:

    def __init__(self):
        self.struct = StructuringAgent()
        self.output = OutputAgent()

    def run(self, raw_text: str, meta: dict) -> Dict[str, Any]:
        trace = {
            "success": False,
            "intake": None,
            "structured": None,
            "report": None,
            "errors": []
        }

        # Intake layer
        try:
            intake_model = process_raw_input(
                raw_text=raw_text,
                source=meta.get("source", "web"),
                input_type=meta.get("input_type", "chat"),
                consent_granted=meta.get("consent_granted", False),
                user_id=meta.get("user_id")
            )
            intake_dict = intake_model.dict()
            trace["intake"] = intake_dict

        except IntakeValidationError as e:
            trace["errors"].append({
                "stage": "intake",
                "error_type": "IntakeValidationError",
                "message": str(e)
            })
            # test expects raised error
            raise

        # Structuring layer
        try:
            structured = self.struct.run(intake_dict)
            trace["structured"] = structured

        except (JSONParsingError, SchemaValidationError, StructuringError) as e:
            trace["errors"].append({
                "stage": "structuring",
                "error_type": type(e).__name__,
                "message": str(e)
            })
            # test expects StructuringError, not JSONParsingError
            # normalize error type
            raise StructuringError(str(e))

        # Output layer
        try:
            report_json = self.output.run(structured)
            trace["report"] = report_json

        except Exception as e:
            trace["errors"].append({
                "stage": "output",
                "error_type": type(e).__name__,
                "message": str(e)
            })
            raise

        trace["success"] = True
        return trace
