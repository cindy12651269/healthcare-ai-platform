from rag.vector_store import InMemoryVectorStore
from rag.embeddings import MockEmbeddings

# Vector store should correctly count inserted documents.
def test_add_and_count():
    store = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    text = "Hypertension is a common condition."
    emb = embedder.embed_text(text)

    store.add(text, emb)

    assert store.count() == 1

# Clear should remove all documents and embeddings.
def test_clear_resets_store():
    store = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    texts = ["Doc A", "Doc B"]
    embs = embedder.embed_texts(texts)

    store.add_batch(texts, embs)
    assert store.count() == 2

    store.clear()
    assert store.count() == 0
    assert store.query(embs[0]) == []

# Query should return top-k documents ranked by cosine similarity.
def test_query_returns_ranked_results():
    store = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    docs = [
        "Hypertension treatment includes lifestyle changes.",
        "Diabetes affects blood sugar regulation.",
        "Asthma is a chronic respiratory disease.",
    ]
    embeddings = embedder.embed_texts(docs)
    store.add_batch(docs, embeddings)

    query_emb = embedder.embed_text("blood pressure treatment")
    results = store.query(query_emb, top_k=2)

    assert len(results) == 2
    assert results[0][1] >= results[1][1]  # sorted by similarity desc

# Same input should always produce the same ranking (mock embeddings).
def test_deterministic_behavior():
    store1 = InMemoryVectorStore()
    store2 = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    docs = ["Doc A", "Doc B", "Doc C"]
    embs = embedder.embed_texts(docs)

    store1.add_batch(docs, embs)
    store2.add_batch(docs, embs)

    query = embedder.embed_text("Doc A")
    result1 = store1.query(query)
    result2 = store2.query(query)

    assert result1 == result2

# Update should modify stored document and/or embedding.
def test_update_document_and_embedding():
    store = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    store.add("Old Doc", embedder.embed_text("Old Doc"))
    assert store.documents[0] == "Old Doc"

    store.update(0, text="New Doc")
    assert store.documents[0] == "New Doc"

# Delete should remove the correct document by index.
def test_delete_document():
    store = InMemoryVectorStore()
    embedder = MockEmbeddings(dim=8)

    docs = ["Doc A", "Doc B"]
    store.add_batch(docs, embedder.embed_texts(docs))

    store.delete(0)

    assert store.count() == 1
    assert store.documents[0] == "Doc B"

# Invalid index operations should raise IndexError.
def test_invalid_index_raises_error():
    store = InMemoryVectorStore()

    try:
        store.delete(0)
    except IndexError:
        assert True
    else:
        assert False
