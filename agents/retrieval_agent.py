from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from rag.retriever import Retriever


@dataclass
# Represents a single retrieved context chunk.
class RetrievalChunk:
    text: str # Retrieved content text
    source: Optional[str]  # Origin of the document (file, URL, KB id, etc.)
    score: Optional[float] # Similarity score (higher = more relevant)

@dataclass
#  Stable retrieval result contract used by the pipeline.
class RetrievalResult:
    query: str # Final semantic query used for embedding search
    chunks: List[RetrievalChunk] # List of structured retrieval chunks
    k: int # Number of top results requested


# Agent responsible for deterministic interface for tests, 
# clear traceability (query is exposed), and compatibility with RAG-aware pipeline execution
class RetrievalAgent:
  
    def __init__(self, retriever: Retriever, enabled: bool = True):
        self.retriever = retriever
        self.enabled = enabled

    # Step 1 — Build semantic query from structured + optional intake
    def build_query(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Construct a clinically meaningful semantic query.

        Priority order:
            1. chief_complaint
            2. symptoms
            3. contextual fields (duration, onset, notes)
            4. raw intake fallback (if structured is sparse)
        """

        parts: List[str] = []

        # Chief complaint (highest signal)
        cc = structured.get("chief_complaint")
        if isinstance(cc, str) and cc.strip():
            parts.append(cc.strip())

        # Symptoms list
        symptoms = structured.get("symptoms")
        if isinstance(symptoms, list):
            parts.extend([str(s).strip() for s in symptoms if s])

        # Additional structured context
        for key in ["context", "duration", "onset", "additional_notes"]:
            val = structured.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())

        # Fallback to intake raw text if structured insufficient
        if not parts and intake:
            raw = intake.get("raw_text") or intake.get("text")
            if isinstance(raw, str) and raw.strip():
                parts.append(raw.strip())

        return " ".join(parts).strip()

    # Step 2 — Stable retrieve interface for pipeline
    def retrieve(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
        *,
        top_k: int = 3,
    ) -> RetrievalResult:
        """
        Execute retrieval and return structured RetrievalResult.

        Failure policy:
            - If disabled → empty result
            - If query empty → empty result
            - Retriever exceptions propagate to pipeline (pipeline decides fatal/non-fatal)
        """
        if not self.enabled:
            return RetrievalResult(query="", chunks=[], k=0)

        query = self.build_query(structured, intake)
        if not query:
            return RetrievalResult(query="", chunks=[], k=top_k)

        raw_results = self.retriever.retrieve(query, top_k=top_k)

        chunks: List[RetrievalChunk] = []
        for item in raw_results:
            chunks.append(
                RetrievalChunk(
                    text=item.get("text"),
                    source=item.get("source"),
                    score=item.get("score"),
                )
            )

        return RetrievalResult(
            query=query,
            chunks=chunks,
            k=top_k,
        )

    # Backward compatibility shim for older pipeline calls
    def run(
        self,
        structured: Dict[str, Any],
        intake: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
    ) -> RetrievalResult:
        return self.retrieve(structured, intake, top_k=top_k)
