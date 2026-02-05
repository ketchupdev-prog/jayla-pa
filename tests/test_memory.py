"""Integration tests for Qdrant memory operations against real Qdrant cluster."""

import pytest
from memory import get_memory_store, QdrantMemoryStore


@pytest.fixture
def memory_store():
    """Get a memory store instance connected to real Qdrant."""
    store = get_memory_store()
    if store is None:
        pytest.skip("QDRANT_URL not configured")
    return store


def test_qdrant_connection(memory_store):
    """Test that we can connect to Qdrant."""
    assert memory_store is not None
    assert memory_store._client is not None
    print("✅ Qdrant connection successful")


def test_memory_roundtrip(memory_store):
    """Test saving and retrieving a memory."""
    namespace = ("test", "pytest")
    test_memory = "Test memory from pytest at 2025-02-05"
    
    # Clear any existing test data first
    try:
        memory_store.put_sync(namespace, "test_key", {"data": ""})
    except Exception:
        pass
    
    # Store a memory
    memory_store.put_sync(namespace, "test_key", {"data": test_memory})
    
    # Retrieve it
    results = memory_store.search_sync(namespace, "test memory", limit=5)
    
    assert isinstance(results, list)
    assert any(test_memory in r for r in results), f"Expected to find '{test_memory}' in results: {results}"
    print(f"✅ Memory roundtrip successful: found {len(results)} memories")


def test_memory_search(memory_store):
    """Test similarity search for memories."""
    namespace = ("test", "search_test")
    
    # Add multiple memories
    memories = [
        "Python programming language",
        "Machine learning and AI",
        "FastAPI web framework",
        "PostgreSQL database",
    ]
    
    for i, mem in enumerate(memories):
        memory_store.put_sync(namespace, f"mem_{i}", {"data": mem})
    
    # Search for programming-related
    results = memory_store.search_sync(namespace, "coding software", limit=2)
    
    assert isinstance(results, list)
    print(f"✅ Memory search successful: found {len(results)} results")
