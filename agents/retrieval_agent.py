from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from rag.retriever import Retriever

# Data Contracts
@dataclass
class RetrievalChunk:
    """Represents a single retrieved context chunk."""
    text: str  # Retrieved content text
    source: Optional[str]  # Origin of the document
    score: Optional[float]  # Similarity score


@dataclass
class RetrievalResult:
    """
    Stable retrieval result contract used by the pipeline.
    Includes hit_count for observability metrics.
    """
    query: str  # Final semantic query used
    chunks: List[RetrievalChunk]  # Retrieved chunks
    k: int  # requested top_k
    hit_count: int  # number of retrieved results (for observability)


# Retrieval Agent responsible for deterministic interface for tests, clear traceability (query is exposed), and Observability (hit_count metric)
class RetrievalAgent:

    def __init__(self, retriever: Retriever, enabled: bool = True):
        self.retriever = retriever
        self.enabled = enabled

    # Step 1 — Build semantic query
    def build_query(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Construct a semantic query from structured + optional intake data.

        Priority:
        1. chief_complaint
        2. symptoms
        3. contextual fields
        4. intake fallback
        """

        parts: List[str] = []

        # Chief complaint (highest signal)
        cc = structured.get("chief_complaint")
        if isinstance(cc, str) and cc.strip():
            parts.append(cc.strip())

        # Symptoms
        symptoms = structured.get("symptoms")
        if isinstance(symptoms, list):
            parts.extend([str(s).strip() for s in symptoms if s])

        # Additional structured context
        for key in ["context", "duration", "onset", "additional_notes"]:
            val = structured.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())

        # Fallback to intake raw text
        if not parts and intake:
            raw = intake.get("raw_text") or intake.get("text")
            if isinstance(raw, str) and raw.strip():
                parts.append(raw.strip())

        return " ".join(parts).strip()

    # Step 2 — Retrieval execution
    def retrieve(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
        *,
        top_k: int = 3,
    ) -> RetrievalResult:
        """
        Execute retrieval and return structured result.

        Failure policy:
        - If disabled → empty result
        - If query empty → empty result
        - Retriever errors propagate to pipeline
        """

        # Disabled → return empty result
        if not self.enabled:
            return RetrievalResult(query="", chunks=[], k=0, hit_count=0)

        # Build query
        query = self.build_query(structured, intake)

        # Empty query → no retrieval
        if not query:
            return RetrievalResult(query="", chunks=[], k=top_k, hit_count=0)

        # Call underlying retriever
        raw_results = self.retriever.retrieve(query, top_k=top_k)

        # Normalize into RetrievalChunk
        chunks: List[RetrievalChunk] = []
        for item in raw_results:
            chunks.append(
                RetrievalChunk(
                    text=item.get("text"),
                    source=item.get("source"),
                    score=item.get("score"),
                )
            )

        # Return structured result + observability metric
        return RetrievalResult(
            query=query,
            chunks=chunks,
            k=top_k,
            hit_count=len(chunks),  # key metric for observability
        )

    # Backward compatibility for pipeline
    def run(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
    ) -> RetrievalResult:
        return self.retrieve(structured, intake, top_k=top_k)
