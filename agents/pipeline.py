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
from agents.retrieval_agent import RetrievalAgent, RetrievalResult
from llm.safety_guard import GuardResult
from api.config import get_settings
from db.models import HealthRecord
from db.session import SessionLocal

# Audit Logger
from observability.audit_logger import build_event, log_run

# Metrics
from observability.tracing import TraceContext
from observability.metrics import build_run_metrics

logger = logging.getLogger(__name__)


class HealthcarePipeline:

    def __init__(
        self,
        structuring_agent: Optional[StructuringAgent] = None,
        output_agent: Optional[OutputAgent] = None,
        retrieval_agent: Optional[RetrievalAgent] = None,
        enable_retrieval: bool = False,
    ):
        self.struct = structuring_agent or StructuringAgent()
        self.output = output_agent or OutputAgent()
        self.retrieval = retrieval_agent
        self.enable_retrieval = enable_retrieval

    def _compute_input_hash(self, raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

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

        if seed is not None:
            random.seed(seed)

        ctx = TraceContext(run_id=run_id)

        start_time = time.perf_counter()
        final_status = "failure"
        error_message = None

        safety_violation_count = 0
        retrieval_hit_count = 0

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

        try:

            # Intake 
            t = time.perf_counter()
            intake_model = process_raw_input(
                raw_text=raw_text,
                source=meta.get("source", "web"),
                input_type=meta.get("input_type", "chat"),
                consent_granted=meta.get("consent_granted", False),
                user_id=meta.get("user_id"),
            )
            ctx.intake_ms = (time.perf_counter() - t) * 1000
            trace["intake"] = intake_model.dict()

            # Structuring 
            t = time.perf_counter()
            structured = self.struct.run(trace["intake"])
            ctx.structuring_ms = (time.perf_counter() - t) * 1000
            trace["structured"] = structured

            safety_violation_count = structured.get("safety_violation_count", 0)

            # Retrieval 
            retrieval_results: List[Any] = []

            if rag_enabled and self.retrieval is not None:
                t = time.perf_counter()
                try:
                    try:
                        retrieval_payload = self.retrieval.run(
                            structured,
                            top_k=rag_top_k,
                        )
                    except TypeError:
                        retrieval_payload = self.retrieval.run(
                            structured_data=structured,
                            top_k=rag_top_k,
                        )

                    retrieval_results = [c.text for c in retrieval_payload.chunks]

                    retrieval_hit_count = getattr(
                        retrieval_payload, "hit_count", len(retrieval_results)
                    )

                    trace["rag"].update(
                        {
                            "used": True,
                            "query": retrieval_payload.query,
                            "chunks": retrieval_results,
                        }
                    )

                except Exception as e:
                    trace["rag"]["error"] = str(e)

                ctx.retrieval_ms = (time.perf_counter() - t) * 1000
            else:
                ctx.retrieval_ms = 0.0

            # Output 
            t = time.perf_counter()
            output_result = self.output.run(
                structured_data=structured,
                retrieval_context=retrieval_results,
            )
            ctx.output_ms = (time.perf_counter() - t) * 1000

            trace["report"] = output_result.get("report")

            # Safety 
            t = time.perf_counter()
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

            ctx.safety_ms = (time.perf_counter() - t) * 1000

            trace["success"] = True
            final_status = "success"

        except Exception as e:
            error_message = str(e)
            trace["errors"].append(error_message)
            raise

        finally:

            # Persistence 
            t = time.perf_counter()
            try:
                self.save_record(
                    raw_text=raw_text,
                    trace=trace,
                    persistence_enabled=persistence_enabled,
                )
            except Exception:
                logger.warning("Persistence hook failed but pipeline succeeded.")
            ctx.persistence_ms = (time.perf_counter() - t) * 1000

            # Total 
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            ctx.latency_ms = latency_ms

            # Existing telemetry
            trace["telemetry"]["latency_ms"] = latency_ms
            trace["telemetry"]["retrieval_hits"] = retrieval_hit_count
            trace["telemetry"]["safety_violations"] = safety_violation_count

            # NEW metrics
            trace["metrics"] = build_run_metrics(
                intake_ms=ctx.intake_ms,
                structuring_ms=ctx.structuring_ms,
                retrieval_ms=ctx.retrieval_ms,
                output_ms=ctx.output_ms,
                safety_ms=ctx.safety_ms,
                persistence_ms=ctx.persistence_ms,
                latency_ms=ctx.latency_ms,
                safety_violation_count=safety_violation_count,
                retrieval_hit_count=retrieval_hit_count,
            )

            event = build_event(
                run_id=trace["run_id"],
                status=final_status,
                latency_ms=latency_ms,
                safety_violation_count=safety_violation_count,
                retrieval_hit_count=retrieval_hit_count,
                flags={"rag_enabled": rag_enabled},
                error=error_message,
            )

            log_run(event)

        return trace