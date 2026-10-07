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
from agents.output_agent import OutputAgent, SafetyBlockedError
from agents.escalation import (
    REASON_EMERGENCY,
    blocked_acknowledgement,
    blocked_safety_audit,
    evaluate_escalation,
)
from agents.retrieval_agent import RetrievalAgent, RetrievalResult
from llm.safety_guard import GuardResult
from api.config import get_settings
from api.webhook import notify_escalation
from db.models import DEFAULT_CLINIC_ID, DEFAULT_REVIEW_STATUS, HealthRecord
from db.session import SessionLocal
from sqlalchemy.exc import IntegrityError

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

    # Best-effort persistence: a DB problem never fails the patient's request,
    # but every outcome is returned (and recorded in trace["persistence"]) and
    # unexpected failures are logged with a traceback.
    #   disabled  — turned off by the caller or ENABLE_PERSISTENCE
    #   skipped   — the run did not succeed, so there is no report to store
    #   saved     — record inserted (record_id set)
    #   duplicate — identical input text already stored (input_hash unique constraint)
    #   failed    — any other error
    def save_record(
        self,
        *,
        raw_text: str,
        trace: Dict[str, Any],
        persistence_enabled: bool,
    ) -> Dict[str, Any]:

        settings = get_settings()

        if not persistence_enabled or not settings.enable_persistence:
            return {"status": "disabled", "record_id": None}

        if not trace.get("success"):
            return {"status": "skipped", "record_id": None}

        session = SessionLocal()

        try:
            input_hash = self._compute_input_hash(raw_text)
            escalation = trace.get("escalation") or {}

            record = HealthRecord.from_pipeline_trace(
                trace_id=trace["run_id"],
                pipeline_version=settings.pipeline_version,
                intake=trace["intake"],
                structured_output=trace["structured"],
                report_json=trace["report"],
                safety_audit=trace["safety"],
                input_hash=input_hash,
                # Unauthenticated intake goes to the single seeded clinic (Issue #27 decision)
                clinic_id=DEFAULT_CLINIC_ID,
                review_status=escalation.get("review_status", DEFAULT_REVIEW_STATUS),
                escalation_reason=",".join(escalation.get("reasons") or []) or None,
            )

            session.add(record)
            session.commit()
            logger.info(f"Persisted health record | record_id={record.id} | run_id={trace['run_id']}")
            return {"status": "saved", "record_id": record.id}

        except IntegrityError as e:
            session.rollback()
            if "input_hash" in str(e.orig):
                logger.warning(f"Persistence skipped: identical input already stored | run_id={trace['run_id']}")
                return {"status": "duplicate", "record_id": None}
            logger.exception("Persistence failed")
            return {"status": "failed", "record_id": None}

        except Exception:
            session.rollback()
            logger.exception("Persistence failed")
            return {"status": "failed", "record_id": None}

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
            # Execution mode of the structuring agent (None for injected test doubles)
            "llm_mode": getattr(self.struct, "mode", None),
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
            # Escalation decision (Issue #29): reason codes only, no intake text
            "escalation": None,
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
            blocked: Optional[SafetyBlockedError] = None
            try:
                output_result = self.output.run(
                    structured_data=structured,
                    retrieval_context=retrieval_results,
                )
            except SafetyBlockedError as e:
                # Blocked report is never returned: the patient gets a controlled acknowledgement
                blocked = e
                output_result = {}
            ctx.output_ms = (time.perf_counter() - t) * 1000

            trace["report"] = output_result.get("report")

            # Safety 
            t = time.perf_counter()
            safety: Optional[GuardResult] = output_result.get("_safety")

            if blocked is not None:
                trace["safety"] = blocked_safety_audit(blocked.guard)
            elif safety:
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

            # Escalation
            trace["escalation"] = evaluate_escalation(
                intake_text=raw_text,
                structured=structured,
                safety_actions=trace["safety"]["actions"],
            )
            if blocked is not None:
                trace["report"] = blocked_acknowledgement(
                    structured,
                    emergency=REASON_EMERGENCY in trace["escalation"]["reasons"],
                )

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
                trace["persistence"] = self.save_record(
                    raw_text=raw_text,
                    trace=trace,
                    persistence_enabled=persistence_enabled,
                )
            except Exception:
                logger.exception("Persistence hook failed")
                trace["persistence"] = {"status": "failed", "record_id": None}
            ctx.persistence_ms = (time.perf_counter() - t) * 1000

            # Escalation webhook (Issue #33): only for a newly persisted record; the notifier re-reads the
            # stored review_status. Best-effort and kept out of the trace, so the patient response never
            # carries webhook details and a delivery problem cannot fail the request.
            if trace["persistence"].get("status") == "saved":
                try:
                    notify_escalation(trace["persistence"]["record_id"], session_factory=SessionLocal)
                except Exception:
                    logger.exception("Escalation webhook hook failed")

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
                flags={
                    "rag_enabled": rag_enabled,
                    "escalation_required": bool((trace["escalation"] or {}).get("required")),
                    "escalation_reasons": list((trace["escalation"] or {}).get("reasons") or []),
                },
                error=error_message,
            )

            log_run(event)

        return trace