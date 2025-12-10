from __future__ import annotations
from typing import List, Dict, Any
from rag.retriever import Retriever

class RetrievalAgent:
    """
    Agent responsible for building a semantically meaningful query from
    structured health data and retrieving relevant context from the vector store.
    """

    def __init__(self, retriever: Retriever, enabled: bool = True):
        self.retriever = retriever
        self.enabled = enabled
    
    # Build a clinically meaningful query from structured inputs.
    def build_query(self, structured: Dict[str, Any]) -> str:

        parts = []

        # Chief complaint usually has highest signal
        cc = structured.get("chief_complaint")
        if isinstance(cc, str) and cc.strip():
            parts.append(cc)

        # Symptoms list
        symptoms = structured.get("symptoms")
        if isinstance(symptoms, list):
            parts.extend([str(s) for s in symptoms if s])

        # Optional extra clinical context
        ctx = structured.get("context")
        if isinstance(ctx, str) and ctx.strip():
            parts.append(ctx)

        # Other optional fields (if exist)
        for key in ["duration", "onset", "additional_notes"]:
            val = structured.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val)

        # Returns a single query string suitable for embedding search.
        query = " ".join(parts).strip()
        return query 
    
    # Execute retrieval based on structured health data.
    def run(self, structured: Dict[str, Any]) -> List[str]:
        if not self.enabled:
            return []

        query = self.build_query(structured)
        if not query:
            return []

        return self.retriever.retrieve(query)
