from __future__ import annotations
from typing import List, Tuple
import math


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    # Basic cosine similarity
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class InMemoryVectorStore:
    """Lightweight in-memory vector index for development/testing."""

    def __init__(self, dim: int | None = None):
        self.dim = dim
        self.embeddings: List[List[float]] = []  # stored vectors
        self.documents: List[str] = []           # raw text

    def add(self, text: str, embedding: List[float]) -> None:
        # Insert a new document + embedding
        self.documents.append(text)
        self.embeddings.append(embedding)

    def add_batch(self, texts: List[str], embeddings: List[List[float]]) -> None:
        # Bulk insert
        for t, emb in zip(texts, embeddings):
            self.add(t, emb)

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        # Rank by cosine similarity
        if not self.embeddings:
            return []

        scored: List[Tuple[str, float]] = []
        for doc, emb in zip(self.documents, self.embeddings):
            sim = cosine_similarity(query_embedding, emb)
            scored.append((doc, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
