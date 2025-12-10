from __future__ import annotations
import random
from typing import List, Protocol


class Embeddings(Protocol):
    """Abstract embedding interface for single and batch text embedding."""

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class MockEmbeddings:
    """Deterministic pseudo-random embeddings for development and testing."""

    def __init__(self, dim: int = 16):
        self.dim = dim

    def embed_text(self, text: str) -> List[float]:
        # derive deterministic seed from text
        seed = int.from_bytes(text.encode("utf-8"), "little") % (2**32 - 1)
        rnd = random.Random(seed)
        return [rnd.random() for _ in range(self.dim)]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OpenAIEmbeddings(Embeddings):
    """Placeholder for real embedding provider (Week 3)."""

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError("Real embedding backend will be implemented in Week 3.")
