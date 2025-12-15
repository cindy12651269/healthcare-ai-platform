import json
from pathlib import Path
from datetime import datetime
from jsonschema import validate, ValidationError
from openai import OpenAI
from llm.schemas.report_output import ReportOutput
from llm.safety_guard import guard_text

# Final report generator — LLM → JSON → PHI-safe → schema-validated.
class OutputAgent:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model

        # Load report prompt
        prompt_path = Path("llm/prompts/report.txt")
        self.prompt_template = prompt_path.read_text()

        # Load true JSON Schema (draft-07) rather than Pydantic internal schema
        schema_path = Path("llm/schemas/report_output.json")
        self.schema = json.loads(schema_path.read_text())

    def _build_prompt(self, structured_data: dict) -> str:
        sd_json = json.dumps(structured_data, indent=2)
        return (
            self.prompt_template
            + "\n\n----- STRUCTURED INPUT -----\n"
            + sd_json
            + "\n----- END INPUT -----"
        )
    
    # Apply safety guard to all string fields in the report JSON and enforce allow/block decisions.
    def _apply_safety_guard(self, report_json: dict) -> dict:
        safety_events = []
        phi_masked = False
        diagnostic_blocked = False

        def walk(obj):
            nonlocal phi_masked, diagnostic_blocked

            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [walk(i) for i in obj]
            if isinstance(obj, str):
                result = guard_text(obj)

                if result.reasons:
                    safety_events.append({
                        "severity": result.severity,
                        "actions": result.actions,
                        "reasons": result.reasons,
                    })

                if "mask_phi" in result.actions:
                    phi_masked = True

                if not result.allowed:
                    diagnostic_blocked = True
                    raise ValueError(
                            "[OutputAgent][SafetyGuard] Output blocked due to unsafe medical content"
                )

                return result.masked_text
            return obj

        sanitized = walk(report_json)

        # Build schema-compatible safety_checks
        sanitized["safety_checks"] = {
            "diagnostic_check_passed": not diagnostic_blocked,
            "phi_safe": not phi_masked,
            "compliance_notes": "Safety guard applied at output stage.",
            # optional internal metadata (schema allows extra fields)
            "guard_passed": True,
            "events": safety_events,
        }

        return sanitized

    # Public entry point used by pipeline & API
    def run(self, structured_data: dict) -> dict:
        prompt = self._build_prompt(structured_data)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        raw_text = response.choices[0].message.content

        # Parse JSON
        try:
            report_json = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"[OutputAgent] Invalid JSON from LLM: {e}")

        # Safety Guard — final gate
        report_json = self._apply_safety_guard(report_json)

        # Schema validation
        try:
            validate(instance=report_json, schema=self.schema)
        except ValidationError as e:
            raise ValueError(f"[OutputAgent] JSON schema validation failed: {e}")

        return report_json