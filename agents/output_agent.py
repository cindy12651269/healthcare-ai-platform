import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from jsonschema import validate, ValidationError
from llm.schemas.report_output import ReportOutput
from llm.safety_guard import GuardResult, guard_text, max_severity
from llm.provider import LLMProvider, build_provider, resolve_llm_mode

# Report fields that carry human-readable content and therefore go through the safety guard
GUARDED_FIELDS = ("report_sections", "input_context")

# Final report generator and RAG-aware
# If retrieval_context is provided, it will be injected into the prompt 
# under a dedicated "Retrieved Context" section.
# Mode mirrors StructuringAgent: "mock" (default) is deterministic and offline; "real" calls OpenAI.
# Both modes go through the shared provider interface (llm/provider.py), safety guard and schema validation.
class OutputAgent:

    def __init__(
        self,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ):
        self.mode = resolve_llm_mode(mode)

        # The OpenAI client only exists in real mode, so mock mode never needs a key or makes a network call
        self.provider = provider or build_provider(
            self.mode,
            mock_builder=lambda ctx: self._mock_report(ctx["structured_data"], ctx["retrieval_context"]),
            model=model,
        )
        self.model = getattr(self.provider, "model", None) or model or "mock"

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

    # Deterministic report built from structured data (mock mode). Wording must stay non-diagnostic:
    # it passes through the same safety guard and schema validation as real LLM output.
    def _mock_report(
        self,
        structured_data: Dict[str, Any],
        retrieval_context: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:

        trace = structured_data.get("trace") or {}
        clinical = structured_data.get("clinical_structuring") or {}
        metadata = structured_data.get("output_metadata") or {}

        concern = (clinical.get("chief_complaint") or "").strip()
        symptoms = [str(s) for s in clinical.get("symptoms") or [] if s]

        recommendations = (
            "Keep a note of when your symptoms occur and how they change, "
            "and share it with your care team at your visit."
        )
        if retrieval_context:
            recommendations += f" Reference material consulted: {len(retrieval_context)} item(s)."

        return {
            "source_struct_id": str(trace.get("input_id") or "unknown"),
            "report_sections": {
                "overview": (
                    f"Pre-visit intake received. Reported concern: {concern}"
                    if concern
                    else "Pre-visit intake received."
                ),
                "symptom_analysis": (
                    "Symptoms noted: " + ", ".join(symptoms) + "."
                    if symptoms
                    else "No discrete symptoms were extracted; the reported concern is summarised above."
                ),
                "clinical_insights": (
                    "This summary was generated in deterministic demo mode from your structured intake. "
                    "It is not a medical assessment; your care team will review it with you."
                ),
                "risk_summary": (
                    "No risk scoring is performed in demo mode. "
                    "If your symptoms are severe or getting worse quickly, seek urgent care."
                ),
                "recommendations": recommendations,
            },
            "input_context": f"{trace.get('input_type') or 'intake'} entry",
            "report_metadata": {
                "generated_at": metadata.get("generated_at") or "2025-01-01T00:00:00Z",
                "model_version": "mock",
                "prompt_version": "v1",
            },
        }

    # Safety Guard: Apply safety guard to all human-readable string fields recursively.
    # Identifiers and metadata (source_struct_id, report_metadata) are not narrative text and are skipped,
    # so the PHI regexes cannot mangle IDs such as UUIDs.
    # Hard blocks unsafe diagnostic or prescription content.
    # Returns the sanitized report and the aggregated GuardResult for the pipeline trace.
    def _apply_safety_guard(self, report_json: Dict[str, Any]) -> tuple[Dict[str, Any], GuardResult]:

        safety_events = []
        phi_masked = False
        diagnostic_blocked = False
        actions: List[str] = []
        reasons: List[Dict[str, Any]] = []
        severity = "low"

        def walk(obj):
            nonlocal phi_masked, diagnostic_blocked, severity

            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}

            if isinstance(obj, list):
                return [walk(i) for i in obj]

            if isinstance(obj, str):
                result = guard_text(obj)

                actions.extend(a for a in result.actions if a not in actions)
                reasons.extend(result.reasons)
                severity = max_severity(severity, result.severity)

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

        sanitized = {
            k: walk(v) if k in GUARDED_FIELDS else v
            for k, v in report_json.items()
        }

        sanitized["safety_checks"] = {
            "diagnostic_check_passed": not diagnostic_blocked,
            "phi_safe": not phi_masked,
            "compliance_notes": "Safety guard applied at output stage.",
            "guard_passed": True,
            "events": safety_events,
        }

        sections = sanitized.get("report_sections")
        guard = GuardResult(
            allowed=True,  # blocked content raises above
            masked_text="\n\n".join(
                v for v in (sections.values() if isinstance(sections, dict) else []) if isinstance(v, str)
            ),
            actions=actions,
            reasons=reasons,
            severity=severity,
        )

        return sanitized, guard

 
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
        Returns the pipeline contract: {"report": <HealthReportOutput>, "_safety": <GuardResult>}
        """

        report_json = self.provider.generate_json(
            system="Return ONLY valid JSON. No explanations.",
            prompt=(
                self._build_prompt(structured_data=structured_data, retrieval_context=retrieval_context)
                if self.mode == "real"
                else ""
            ),
            context={"structured_data": structured_data, "retrieval_context": retrieval_context},
        )
        if self.mode == "real" and isinstance(report_json.get("report_metadata"), dict):
            # Record what actually produced the report, regardless of what the model claims
            report_json["report_metadata"]["model_version"] = self.model

        # Safety enforcement
        report_json, guard = self._apply_safety_guard(report_json)

        # JSON schema validation
        try:
            validate(instance=report_json, schema=self.schema)
        except ValidationError as e:
            raise ValueError(f"[OutputAgent] JSON schema validation failed: {e}")

        return {"report": report_json, "_safety": guard}
