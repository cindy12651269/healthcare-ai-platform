from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol
import hashlib

class Embeddings(Protocol):
    """
    Minimal embedding interface. Implementations must provide deterministic single-text embeddings.
    """

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

@dataclass(frozen=True)
class MockEmbeddings:
    """
    Deterministic mock embeddings for local development and tests.
    Stable across environments and suitable for cosine similarity search.
    """
    dim: int = 16

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dim

        needed_bytes = self.dim * 4
        buf = bytearray()
        counter = 0
        base = text.encode("utf-8")

        while len(buf) < needed_bytes:
            h = hashlib.sha256(base + counter.to_bytes(4, "little")).digest()
            buf.extend(h)
            counter += 1

        vectors: List[float] = []
        for i in range(self.dim):
            chunk = buf[i * 4 : (i + 1) * 4]
            n = int.from_bytes(chunk, "little")
            vectors.append((n % 10_000_000) / 10_000_000.0)

        return vectors
    
    # Batch embedding interface for vector store and RAG seeding.
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

class OpenAIEmbeddings(Embeddings):
    """
    Placeholder for real embedding backend (Week 3+).
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError("Real embedding backend will be implemented in Week 3.")
