import logging
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

from rag.document_loader import DocumentLoader
from rag.embeddings import Embeddings
from rag.vector_store import InMemoryVectorStore

# Persistence imports (isolated)
from api.config import get_settings
from db.models import HealthRecord
from db.session import SessionLocal

logger = logging.getLogger(__name__)

class HealthcarePipeline:
    """
    Production-grade multi-agent pipeline.

    Week 1–2:
        - StructuringAgent: mock-only
        - OutputAgent: mock-only
        - No external API calls
        - Fully testable & CI-safe

    Week 3: Real LLM agents are injected explicitly
    """

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

    # Persistence Helper (isolated DB side-effect)
    def _compute_input_hash(self, raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    # Isolated persistence helper. 
    # Opens its own DB session, commits safely, rolls back on failure, and never crashes the pipeline
    def save_record(
        self,
        *,
        raw_text: str,
        trace: Dict[str, Any],
    ) -> None:
       
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
    def run(self, raw_text: str, meta: dict) -> Dict[str, Any]:
        trace: Dict[str, Any] = {
            "success": False,
            "intake": None,
            "structured": None,
            "retrieval_context": None,
            "report": None,
            "safety": None,
            "errors": [],
        }

        # 1. Intake
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

        # 2. Structuring
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

        # 3. Retrieval (optional, non-fatal)
        retrieval_results: List[str] = []

        if self.enable_retrieval and self.retrieval:
            try:
                retrieval_results = self.retrieval.run(structured)
                trace["retrieval_context"] = retrieval_results

            except Exception as e:
                logger.warning(
                    "Retrieval failed, continuing without context", exc_info=e
                )
                trace["errors"].append(
                    {
                        "stage": "retrieval",
                        "error_type": type(e).__name__,
                        "message": str(e),
                    }
                )

        # 4. Output + Safety
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

        trace["success"] = True

        # Step 5 — Optional Persistence Integration
        try:
            self.save_record(
                raw_text=raw_text,
                trace=trace,
            )
        except Exception:
            # Absolute isolation — pipeline must NEVER fail due to DB
            logger.warning("Persistence hook failed but pipeline succeeded.")

        return trace


# RAG Vector Store Seeding (startup-time only)
def seed_vector_store(
    loader: DocumentLoader,
    embedder: Embeddings,
    store: InMemoryVectorStore,
    source_path: str,
) -> int:
    documents = loader.load_directory(source_path)
    if not documents:
        logger.warning("No documents found for RAG seeding.")
        return 0

    embeddings = embedder.embed_texts(documents)
    store.add_batch(documents, embeddings)

    logger.info("Seeded vector store with %d documents.", len(documents))
    return len(documents)