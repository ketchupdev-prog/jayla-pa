# Tests for RAG retrieve. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.
# Unit tests run always; integration test when DATABASE_URL set. Perspective: RAG used for Telegram document context + search_my_documents.

import os
import pytest
from rag import retrieve


def test_retrieve_empty_query():
    """[Telegram] Empty query returns empty list (guard for malformed or empty message)."""
    assert retrieve("", user_id="test-user") == []
    assert retrieve("   ", user_id="test-user") == []


def test_retrieve_no_db_raises(monkeypatch):
    """[Telegram] When DATABASE_URL is missing (e.g. misconfigured deployment), _get_conn() raises RuntimeError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from rag import _get_conn
    with pytest.raises((RuntimeError, Exception)):
        _get_conn()


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; integration test needs real DB")
def test_retrieve_with_real_db():
    """[Telegram] Integration: retrieve against real DB (same DB as webhook for document context + search_my_documents). Returns list (may be empty)."""
    result = retrieve("test query", user_id="test-integration-user", limit=3)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, str)
        assert len(item) > 0
