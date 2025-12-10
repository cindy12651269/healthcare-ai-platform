from rag.embeddings import MockEmbeddings
from rag.vector_store import InMemoryVectorStore
from rag.retriever import Retriever
from agents.retrieval_agent import RetrievalAgent


def test_retrieval_agent_basic_flow():
    # Setup mock embedding + vector store (dim comes from embeddings)
    embed = MockEmbeddings(dim=8)
    store = InMemoryVectorStore()
    retriever = Retriever(embed, store, top_k=2)

    # Seed vector store
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

    results = agent.run(structured)

    # Expect top_k=2 results returned
    assert len(results) == 2

    # Should retrieve at least one clinically relevant document
    joined = " ".join(results).lower()
    assert "chest pain" in joined or "shortness of breath" in joined


def test_retrieval_agent_disabled():
    embed = MockEmbeddings(dim=8)
    store = InMemoryVectorStore()
    retriever = Retriever(embed, store)

    agent = RetrievalAgent(retriever, enabled=False)

    structured = {"chief_complaint": "fever"}
    results = agent.run(structured)

    assert results == []  # disabled mode returns nothing
