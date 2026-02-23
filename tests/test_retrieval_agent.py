from rag.embeddings import MockEmbeddings
from rag.vector_store import InMemoryVectorStore
from rag.retriever import Retriever
from agents.retrieval_agent import RetrievalAgent


def test_retrieval_agent_basic_flow():
    embed = MockEmbeddings(dim=8)
    store = InMemoryVectorStore()
    retriever = Retriever(embed, store, top_k=2)

    docs = [
        "Patient reports mild chest pain during exercise.",
        "Symptoms include shortness of breath and dizziness.",
        "Unrelated document about nutrition."
    ]

    retriever.add_documents(docs)

    agent = RetrievalAgent(retriever)

    structured = {
        "chief_complaint": "chest pain",
        "symptoms": ["shortness of breath"]
    }

    result = agent.retrieve(structured)

    # RetrievalResult structure validation
    assert result.query != ""
    assert result.k == 3
    assert isinstance(result.chunks, list)
    assert len(result.chunks) == 3

    # Each chunk must contain required fields
    for chunk in result.chunks:
        assert hasattr(chunk, "text")
        assert hasattr(chunk, "score")
        assert hasattr(chunk, "source")
        assert isinstance(chunk.text, str)
        assert isinstance(chunk.score, float)

    # At least one clinically relevant doc should appear
    joined = " ".join(c.text for c in result.chunks).lower()
    assert "chest pain" in joined or "shortness of breath" in joined


def test_retrieval_agent_disabled():
    embed = MockEmbeddings(dim=8)
    store = InMemoryVectorStore()
    retriever = Retriever(embed, store)

    agent = RetrievalAgent(retriever, enabled=False)

    structured = {"chief_complaint": "fever"}

    result = agent.retrieve(structured)

    # Disabled mode returns empty but well-formed result
    assert result.query == ""
    assert result.k == 0
    assert result.chunks == []