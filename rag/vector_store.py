from __future__ import annotations
from typing import List, Tuple, Optional
import math

# Compute cosine similarity between two vectors.
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

class InMemoryVectorStore:
    """
    Lightweight in-memory vector store for development and testing.
    This class intentionally mimics a minimal FAISS / Chroma-style API.
    """

    def __init__(self, dim: Optional[int] = None):
        # Optional embedding dimension (not strictly enforced in mock mode)
        self.dim = dim

        # Stored embeddings and corresponding documents
        self.embeddings: List[List[float]] = []
        self.documents: List[str] = []
    
    # Return number of stored vectors/documents.
    def count(self) -> int:
        return len(self.embeddings)
    
    # Remove all stored vectors and documents for test isolation and index reseeding.
    def clear(self) -> None:
        self.embeddings.clear()
        self.documents.clear()

    #  Insert a single document and its embedding.
    def add(self, text: str, embedding: List[float]) -> None:
        self.documents.append(text)
        self.embeddings.append(embedding)

    # Bulk insert multiple documents and embeddings.
    def add_batch(self, texts: List[str], embeddings: List[List[float]]) -> None:
        for text, emb in zip(texts, embeddings):
            self.add(text, emb)

    # Update an existing document and/or embedding by index.
    def update(self, index: int, *, text: Optional[str] = None, embedding: Optional[List[float]] = None) -> None:
        
        if index < 0 or index >= self.count(): # Raises: IndexError: if index is out of range.
            raise IndexError("VectorStore index out of range")

        if text is not None:
            self.documents[index] = text
        if embedding is not None:
            self.embeddings[index] = embedding

    # Delete a document and embedding by index.
    def delete(self, index: int) -> None:
        # Raises: IndexError: if index is out of range.
        if index < 0 or index >= self.count():
            raise IndexError("VectorStore index out of range")

        del self.documents[index]
        del self.embeddings[index]

    # Perform cosine similarity search against stored embeddings.
    def query(
        self,
        query_embedding: List[float],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        # Returns: List of (document_text, similarity_score), sorted by score descending.
        if not self.embeddings:
            return []

        scored: List[Tuple[str, float]] = []
        for doc, emb in zip(self.documents, self.embeddings):
            sim = cosine_similarity(query_embedding, emb)
            scored.append((doc, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
