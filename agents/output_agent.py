import json
from pathlib import Path
from datetime import datetime
from jsonschema import validate, ValidationError
from openai import OpenAI
from llm.safety_guard import apply_safety_filters
from llm.schemas.report_output import ReportOutput

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

    def _sanitize_dict(self, obj):
        if isinstance(obj, dict):
            return {k: self._sanitize_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_dict(i) for i in obj]
        elif isinstance(obj, str):
            return apply_safety_filters(obj)
        return obj

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

        # PHI sanitization
        report_json = self._sanitize_dict(report_json)

        # Schema validation (real JSON schema)
        try:
            validate(instance=report_json, schema=self.schema)
        except ValidationError as e:
            raise ValueError(f"[OutputAgent] JSON schema validation failed: {e}")

        return report_json
