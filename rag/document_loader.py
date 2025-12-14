from __future__ import annotations
from pathlib import Path
from typing import List


class DocumentLoader:
    """
    Utility class for loading and chunking knowledge base documents
    before embedding and indexing.
    """

    def __init__(self, chunk_size: int = 500):
        self.chunk_size = chunk_size
    
    # Load a single markdown file and split it into chunks.
    def load_markdown(self, path: str) -> List[str]:
        text = Path(path).read_text(encoding="utf-8")
        return self._chunk_text(text)

    # Load all markdown files in a directory.
    def load_directory(self, dir_path: str) -> List[str]:
        chunks: List[str] = []
        for file_path in Path(dir_path).glob("*.md"):
            chunks.extend(self.load_markdown(str(file_path)))
        return chunks

    # Split raw text into paragraph-level chunks.
    def _chunk_text(self, text: str) -> List[str]:
        paragraphs = [
            p.strip()
            for p in text.split("\n\n")
            if p.strip()
        ]
        return paragraphs
