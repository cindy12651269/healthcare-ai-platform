import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from jsonschema import validate, ValidationError
from openai import OpenAI
from llm.schemas.report_output import ReportOutput
from llm.safety_guard import guard_text

# Final report generator and RAG-aware
# If retrieval_context is provided, it will be injected into the prompt 
# under a dedicated "Retrieved Context" section.
class OutputAgent:

    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model

        prompt_path = Path("llm/prompts/report.txt")
        self.prompt_template = prompt_path.read_text()

        schema_path = Path("llm/schemas/report_output.json")
        self.schema = json.loads(schema_path.read_text())

    # Build RAG-aware prompt (structured data + optional retrieval context)
    def _build_prompt(
        self,
        structured_data: Dict[str, Any],
        retrieval_context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Build final prompt including structured input and optional RAG context.

        Retrieval context format expected:
            [
                {"text": "...", "source": "...", "score": 0.87},
                ...
            ]
        """

        sd_json = json.dumps(structured_data, indent=2)

        prompt_parts = [
            self.prompt_template,
            "\n\n----- STRUCTURED INPUT -----\n",
            sd_json,
            "\n----- END INPUT -----",
        ]

        # Inject retrieved context if present
        if retrieval_context:
            context_blocks = []

            for idx, chunk in enumerate(retrieval_context, start=1):
                text = chunk.get("text", "")
                source = chunk.get("source", "unknown")
                score = chunk.get("score", 0.0)

                context_blocks.append(
                    f"[Context {idx}] (source: {source}, score: {score:.4f})\n{text}"
                )

            prompt_parts.extend([
                "\n\n----- RETRIEVED CONTEXT -----\n",
                "\n\n".join(context_blocks),
                "\n----- END CONTEXT -----",
            ])

        return "".join(prompt_parts)

    # Safety Guard: Apply safety guard to all string fields recursively.
    # Hard blocks unsafe diagnostic or prescription content.
    def _apply_safety_guard(self, report_json: Dict[str, Any]) -> Dict[str, Any]:

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

        sanitized["safety_checks"] = {
            "diagnostic_check_passed": not diagnostic_blocked,
            "phi_safe": not phi_masked,
            "compliance_notes": "Safety guard applied at output stage.",
            "guard_passed": True,
            "events": safety_events,
        }

        return sanitized

 
    # Public Entry Point (RAG-aware)
    def run(
        self,
        structured_data: Dict[str, Any],
        retrieval_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate final report JSON.
        retrieval_context:
            Optional list of retrieved chunks injected into prompt.
        """

        prompt = self._build_prompt(
            structured_data=structured_data,
            retrieval_context=retrieval_context,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        raw_text = response.choices[0].message.content

        try:
            report_json = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"[OutputAgent] Invalid JSON from LLM: {e}")

        # Safety enforcement
        report_json = self._apply_safety_guard(report_json)

        # JSON schema validation
        try:
            validate(instance=report_json, schema=self.schema)
        except ValidationError as e:
            raise ValueError(f"[OutputAgent] JSON schema validation failed: {e}")

        return report_json
