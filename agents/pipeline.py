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
from agents.retrieval_agent import RetrievalAgent   # Week 2 addition (optional)
from rag.document_loader import DocumentLoader
from rag.embeddings import Embeddings
from rag.vector_store import InMemoryVectorStore

logger = logging.getLogger(__name__)


class HealthcarePipeline:
    """
    Production-grade multi-agent pipeline:
    Raw → Intake → Structuring → (Retrieval optional) → Output Report
    """

    def __init__(
        self,
        retrieval_agent: Optional[RetrievalAgent] = None,
        enable_retrieval: bool = False,
    ):
        self.struct = StructuringAgent()
        self.output = OutputAgent()

        # Week 2+ RAG components
        self.retrieval = retrieval_agent
        self.enable_retrieval = enable_retrieval

    def run(self, raw_text: str, meta: dict) -> Dict[str, Any]:
        trace = {
            "success": False,
            "intake": None,
            "structured": None,
            "retrieval_context": None,   # ← new (safe for Week 1: always None)
            "report": None,
            "errors": []
        }

        # 1. Intake Layer
        try:
            intake_model = process_raw_input(
                raw_text=raw_text,
                source=meta.get("source", "web"),
                input_type=meta.get("input_type", "chat"),
                consent_granted=meta.get("consent_granted", False),
                user_id=meta.get("user_id"),
            )
            intake_dict = intake_model.dict()
            trace["intake"] = intake_dict

        except IntakeValidationError as e:
            trace["errors"].append({
                "stage": "intake",
                "error_type": "IntakeValidationError",
                "message": str(e),
            })
            raise

        # 2. Structuring Layer
        try:
            structured = self.struct.run(intake_dict)
            trace["structured"] = structured

        except (JSONParsingError, SchemaValidationError, StructuringError) as e:
            trace["errors"].append({
                "stage": "structuring",
                "error_type": type(e).__name__,
                "message": str(e),
            })
            # Normalize all structuring-stage errors to StructuringError
            raise StructuringError(str(e))

        # 3. Retrieval Layer (Optional)
        retrieval_results: List[str] = []

        if self.enable_retrieval and self.retrieval:
            try:
                retrieval_results = self.retrieval.run(structured)
                trace["retrieval_context"] = retrieval_results

            except Exception as e:
                trace["errors"].append({
                    "stage": "retrieval",
                    "error_type": type(e).__name__,
                    "message": str(e),
                })
                # Retrieval failures do NOT crash the pipeline — safe fallback
                retrieval_results = []

        # 4. Output Agent
        try:
            # OutputAgent may optionally use retrieval context later
            report_json = self.output.run(structured)
            trace["report"] = report_json

        except Exception as e:
            trace["errors"].append({
                "stage": "output",
                "error_type": type(e).__name__,
                "message": str(e),
            })
            raise

        trace["success"] = True
        return trace
    
# Initialize the RAG vector store with source documents.
# This is a one-time setup step executed at startup,not during request-time pipeline execution.
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
    logger.info(f"Seeded vector store with {len(documents)} documents.")
    return len(documents)

