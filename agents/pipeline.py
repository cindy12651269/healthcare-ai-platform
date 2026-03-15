import logging
import time
import random
from typing import Any, Dict, Optional, List
import hashlib
from uuid import uuid4
from agents.intake_agent import process_raw_input, IntakeValidationError
from agents.structuring_agent import (
    StructuringAgent,
    StructuringError,
    JSONParsingError,
    SchemaValidationError,
)
from agents.output_agent import OutputAgent
from agents.retrieval_agent import RetrievalAgent
from llm.safety_guard import GuardResult
from api.config import get_settings
from db.models import HealthRecord
from db.session import SessionLocal

logger = logging.getLogger(__name__)


class HealthcarePipeline:

    def __init__(
        self,
        structuring_agent: StructuringAgent,
        output_agent: OutputAgent,
        retrieval_agent: Optional[RetrievalAgent] = None,
        enable_retrieval: bool = False,
    ):
        self.struct = structuring_agent
        self.output = output_agent
        self.retrieval = retrieval_agent
        self.enable_retrieval = enable_retrieval

    
    # Deterministic Input Hash
    def _compute_input_hash(self, raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    # Persistence (side-effect layer)
    def save_record(
        self,
        *,
        raw_text: str,
        trace: Dict[str, Any],
        persistence_enabled: bool,
    ) -> None:

        if not persistence_enabled:
            return

        settings = get_settings()

        if not settings.enable_persistence:
            return

        session = SessionLocal()

        try:
            input_hash = self._compute_input_hash(raw_text)

            record = HealthRecord.from_pipeline_trace(
                trace_id=str(uuid4()),
                pipeline_version=settings.pipeline_version,
                intake=trace["intake"],
                structured_output=trace["structured"],
                report_json=trace["report"],
                safety_audit=trace["safety"],
                input_hash=input_hash,
            )

            session.add(record)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error("Persistence failed", exc_info=e)

        finally:
            session.close()

    # Main Pipeline
    def run(
        self,
        raw_text: str,
        meta: dict,
        *,
        enable_rag: Optional[bool] = None,
        rag_top_k: int = 3,
        persistence_enabled: bool = True,
        seed: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        # Deterministic seed
        if seed is not None:
            random.seed(seed)

        start_time = time.perf_counter()

        rag_enabled = enable_rag if enable_rag is not None else self.enable_retrieval

        trace: Dict[str, Any] = {
            "run_id": run_id or str(uuid4()),
            "success": False,
            "intake": None,
            "structured": None,
            "rag": {
                "enabled": rag_enabled,
                "used": False,
                "query": None,
                "top_k": rag_top_k,
                "chunks": [],
                "error": None,
            },
            "report": None,
            "safety": None,
            "errors": [],
            "telemetry": {
                "latency_ms": None,
                "retrieval_hits": 0,
                "safety_violations": 0,
            },
        }

        # Step 1. Intake
        try:
            intake_model = process_raw_input(
                raw_text=raw_text,
                source=meta.get("source", "web"),
                input_type=meta.get("input_type", "chat"),
                consent_granted=meta.get("consent_granted", False),
                user_id=meta.get("user_id"),
            )

            trace["intake"] = intake_model.dict()

        except IntakeValidationError as e:

            trace["errors"].append(
                {
                    "stage": "intake",
                    "error_type": "IntakeValidationError",
                    "message": str(e),
                }
            )

            raise

        
        # Step 2. Structuring
        try:

            structured = self.struct.run(trace["intake"])
            trace["structured"] = structured

        except (JSONParsingError, SchemaValidationError, StructuringError) as e:

            trace["errors"].append(
                {
                    "stage": "structuring",
                    "error_type": type(e).__name__,
                    "message": str(e),
                }
            )

            raise StructuringError(str(e))

        # Step 3. Retrieval (optional)
        retrieval_results: List[Any] = []

        if rag_enabled and self.retrieval:

            try:

                retrieval_payload = self.retrieval.run(
                    structured_data=structured,
                    top_k=rag_top_k,
                )

                retrieval_results = retrieval_payload.get("chunks", [])

                trace["rag"].update(
                    {
                        "used": True,
                        "query": retrieval_payload.get("query"),
                        "chunks": retrieval_results,
                    }
                )

            except Exception as e:

                logger.warning(
                    "Retrieval failed. Continuing without RAG context.",
                    exc_info=e,
                )

                trace["rag"].update(
                    {
                        "used": False,
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e),
                        },
                    }
                )

        # Step 4. Output + Safety
        try:

            output_result = self.output.run(
                structured_data=structured,
                retrieval_context=retrieval_results,
            )

            trace["report"] = output_result.get("report")

            safety: Optional[GuardResult] = output_result.get("_safety")

            if safety:
                trace["safety"] = safety.to_dict()
            else:
                trace["safety"] = GuardResult(
                    allowed=True,
                    masked_text=trace["report"] or "",
                    actions=[],
                    reasons=[],
                    severity="low",
                ).to_dict()

        except Exception as e:

            trace["errors"].append(
                {
                    "stage": "output",
                    "error_type": type(e).__name__,
                    "message": str(e),
                }
            )

            raise

        # Success
        trace["success"] = True
       
        # Telemetry
        latency_ms = (time.perf_counter() - start_time) * 1000

        trace["telemetry"]["latency_ms"] = latency_ms
        trace["telemetry"]["retrieval_hits"] = len(trace["rag"]["chunks"])
        trace["telemetry"]["safety_violations"] = len(trace["safety"]["actions"])

        
        # Optional persistence
        try:

            self.save_record(
                raw_text=raw_text,
                trace=trace,
                persistence_enabled=persistence_enabled,
            )

        except Exception:

            logger.warning("Persistence hook failed but pipeline succeeded.")

        return trace