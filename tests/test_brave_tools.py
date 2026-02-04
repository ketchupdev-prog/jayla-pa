# Tests for Brave Search tool. See PERSONAL_ASSISTANT_PATTERNS.md §10, tools_custom/brave_tools.py.

import pytest
from unittest.mock import patch

from tools_custom.brave_tools import (
    _search_brave_sync,
    search_web,
    get_brave_tools,
)


def test_get_brave_tools_empty_when_no_key(monkeypatch):
    """When BRAVE_API_KEY is not set, get_brave_tools returns empty list."""
    monkeypatch.setenv("BRAVE_API_KEY", "")
    tools = get_brave_tools()
    assert tools == []


def test_get_brave_tools_returns_search_web_when_key_set(monkeypatch):
    """When BRAVE_API_KEY is set, get_brave_tools returns list with search_web tool."""
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    tools = get_brave_tools()
    assert len(tools) == 1
    assert tools[0].name == "search_web"


def test_search_web_no_api_key_returns_message(monkeypatch):
    """search_web with no BRAVE_API_KEY returns friendly message."""
    monkeypatch.setenv("BRAVE_API_KEY", "")
    result = search_web.invoke({"query": "latest news"})
    assert "BRAVE_API_KEY" in result or "not configured" in result.lower()


def test_search_web_with_mock_api_returns_formatted_results(monkeypatch):
    """search_web with mocked API returns formatted string with title, url, description."""
    fake_results = [
        {"title": "Test Title", "url": "https://example.com", "description": "A test result.", "score": 1.0},
    ]
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    with patch("tools_custom.brave_tools._search_brave_sync", return_value=fake_results):
        result = search_web.invoke({"query": "test query", "max_results": 5})
    assert "Web search results" in result
    assert "Test Title" in result
    assert "https://example.com" in result
    assert "A test result" in result


def test_search_brave_sync_empty_without_key():
    """_search_brave_sync returns [] when api_key is empty."""
    assert _search_brave_sync("", "query") == []
    assert _search_brave_sync("  ", "query") == []


def test_search_brave_sync_empty_query():
    """_search_brave_sync returns [] when query is empty."""
    assert _search_brave_sync("key", "") == []
    assert _search_brave_sync("key", "   ") == []


def test_search_brave_sync_mock_httpx():
    """_search_brave_sync with mocked httpx returns list of dicts with title, url, description, score."""
    mock_response = type("Res", (), {
        "status_code": 200,
        "json": lambda self=None: {"web": {"results": [
            {"title": "A", "url": "https://a.com", "description": "Desc A"},
            {"title": "B", "url": "https://b.com", "description": "Desc B"},
        ]}},
    })()

    with patch("tools_custom.brave_tools.time.sleep"), patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.get.return_value = mock_response
        results = _search_brave_sync("fake-key", "test", count=5)

    assert len(results) == 2
    assert results[0]["title"] == "A"
    assert results[0]["url"] == "https://a.com"
    assert results[0]["description"] == "Desc A"
    assert "score" in results[0]
    assert results[1]["title"] == "B"
    assert results[1]["url"] == "https://b.com"
