from __future__ import annotations
from typing import List, Optional
from pathlib import Path
from rag.embeddings import Embeddings
from rag.vector_store import InMemoryVectorStore


class Retriever:
    """Wrapper for embedding + vector store retrieval with optional knowledge loading."""

    def __init__(
        self,
        embeddings: Embeddings,
        store: InMemoryVectorStore,
        top_k: int = 3,
        kb_path: Optional[str] = None,
    ):
        self.embeddings = embeddings
        self.store = store
        self.top_k = top_k

        # If knowledge-base path is provided, ingest its content into vector store
        if kb_path:
            self.ingest_knowledge_source(kb_path)

    # Read markdown knowledge source and index it into vector store.
    def ingest_knowledge_source(self, file_path: str) -> None:
        p = Path(file_path)
        if not p.exists():
            return

        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return

        # Simple segmentation: split by blank lines for small chunks
        blocks = [blk.strip() for blk in text.split("\n\n") if blk.strip()]
        if not blocks:
            return

        embeddings = self.embeddings.embed_texts(blocks)
        self.store.add_batch(blocks, embeddings)

    def build_query(self, text: str) -> str:
        # Minimal query builder; can be expanded later
        return text.strip()

    def retrieve(self, text: str) -> List[str]:
        q = self.build_query(text)
        if not q:
            return []

        q_emb = self.embeddings.embed_text(q)
        results = self.store.query(q_emb, top_k=self.top_k)
        return [doc for doc, _score in results]

    def add_documents(self, docs: List[str]) -> None:
        embeddings = self.embeddings.embed_texts(docs)
        self.store.add_batch(docs, embeddings)
