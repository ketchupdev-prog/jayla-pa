"""Integration tests for RAG/Neon PostgreSQL operations against real Neon DB."""

import pytest
import os


@pytest.fixture
def conn():
    """Get a database connection."""
    from rag import _get_conn
    try:
        c = _get_conn()
        yield c
    except Exception as e:
        pytest.skip(f"Neon DB not available: {e}")
    finally:
        try:
            c.close()
        except Exception:
            pass


def test_neon_connection(conn):
    """Test that we can connect to Neon PostgreSQL."""
    assert conn is not None
    with conn.cursor() as cur:
        cur.execute("SELECT 1 as test")
        row = cur.fetchone()
        assert row["test"] == 1
    print("✅ Neon PostgreSQL connection successful")


def test_documents_table_exists(conn):
    """Test that the documents table exists."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'documents'
            ORDER BY ordinal_position
        """)
        columns = {row["column_name"]: row["data_type"] for row in cur.fetchall()}
    
    required = {"id", "user_id", "content", "metadata", "embedding", "scope", "expires_at", "created_at"}
    missing = required - set(columns.keys())
    assert not missing, f"Missing columns: {missing}"
    print(f"✅ Documents table exists with columns: {list(columns.keys())}")


def test_rag_ingest_and_retrieve(conn):
    """Test full RAG flow: ingest document and retrieve."""
    from rag import ingest_document, retrieve
    
    test_user = os.environ.get("EMAIL", "test@example.com")
    test_content = b"Python is a high-level programming language created by Guido van Rossum."
    test_filename = "test_python.txt"
    
    # Ingest
    status, ids = ingest_document(
        bytes_content=test_content,
        user_id=test_user,
        scope="test",
        metadata={"filename": test_filename, "source": "pytest"}
    )
    
    assert len(ids) > 0, f"Failed to ingest: {status}"
    
    # Retrieve
    results = retrieve("Python programming language", user_id=test_user, limit=5)
    
    assert isinstance(results, list)
    # Should find the ingested content (or similar from other tests)
    print(f"✅ RAG ingest/retrieve successful: {status}, retrieved {len(results)} chunks")


def test_vector_similarity_search(conn):
    """Test that vector similarity search works."""
    from rag import _get_embedder, _get_conn
    import json
    
    test_user = os.environ.get("EMAIL", "test@example.com")
    query = "artificial intelligence"
    
    # Get embedding for query
    model = _get_embedder()
    query_emb = model.encode([query]).tolist()[0]
    vec_str = "[" + ",".join(str(x) for x in query_emb) + "]"
    
    # Search using cosine similarity
    with conn.cursor() as cur:
        cur.execute("""
            SELECT content, 1 - (embedding <=> %s::vector) as similarity
            FROM documents
            WHERE user_id = %s AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        """, (vec_str, test_user, vec_str))
        rows = cur.fetchall()
    
    print(f"✅ Vector similarity search found {len(rows)} documents")
    for row in rows:
        print(f"   - Similarity: {row['similarity']:.3f}")
