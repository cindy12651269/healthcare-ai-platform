import logging
from typing import Any, Dict, Optional, List
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
        # Pipeline NEVER instantiates agents that may touch real APIs.
        # All agents must be injected explicitly.
        self.struct = structuring_agent
        self.output = output_agent
        self.retrieval = retrieval_agent
        self.enable_retrieval = enable_retrieval

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

            # Safety trace MUST always exist
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
