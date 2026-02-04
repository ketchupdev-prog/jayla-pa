# Tests for RAG retrieve. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.
# Unit tests run always; integration test runs only when DATABASE_URL is set (real Neon/Postgres).

import os
import pytest
from rag import retrieve


def test_retrieve_empty_query():
    """Empty query returns empty list."""
    assert retrieve("", user_id="test-user") == []
    assert retrieve("   ", user_id="test-user") == []


def test_retrieve_no_db_raises(monkeypatch):
    """When DATABASE_URL is missing, _get_conn() raises RuntimeError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from rag import _get_conn
    with pytest.raises((RuntimeError, Exception)):
        _get_conn()


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; integration test needs real DB")
def test_retrieve_with_real_db():
    """Integration: call retrieve against real DB. Returns list (may be empty if no docs)."""
    result = retrieve("test query", user_id="test-integration-user", limit=3)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, str)
        assert len(item) > 0
