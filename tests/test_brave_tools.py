# Tests for Brave Search tool. See PERSONAL_ASSISTANT_PATTERNS.md §10, tools_custom/brave_tools.py.
# All tests use a Telegram perspective: message text as it would come from a Telegram user.

import pytest
from unittest.mock import patch

from tools_custom.brave_tools import (
    _search_brave_sync,
    search_web,
    get_brave_tools,
)


def test_get_brave_tools_empty_when_no_key(monkeypatch):
    """[Telegram] When BRAVE_API_KEY is not set (e.g. Railway without key), get_brave_tools returns empty list."""
    monkeypatch.setenv("BRAVE_API_KEY", "")
    tools = get_brave_tools()
    assert tools == []


def test_get_brave_tools_returns_search_web_when_key_set(monkeypatch):
    """[Telegram] When BRAVE_API_KEY is set on deployment, get_brave_tools returns search_web so agent can use it."""
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    tools = get_brave_tools()
    assert len(tools) == 1
    assert tools[0].name == "search_web"


def test_search_web_no_api_key_returns_message(monkeypatch):
    """[Telegram] If user asks to search the internet but BRAVE_API_KEY is missing, return friendly message."""
    monkeypatch.setenv("BRAVE_API_KEY", "")
    result = search_web.invoke({"query": "latest news"})
    assert "BRAVE_API_KEY" in result or "not configured" in result.lower()


def test_search_web_telegram_style_message_find_out_on_internet(monkeypatch):
    """[Telegram] User sends 'Okay find out more about MTC maris and Kazang deal on the internet' — search_web gets topic query."""
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    # Query as agent would pass to search_web (topic extracted from Telegram message)
    query = "MTC Maris Kazang deal"
    fake_results = [
        {"title": "MTC Maris Kazang", "url": "https://example.com", "description": "Deal news.", "score": 1.0},
    ]
    with patch("tools_custom.brave_tools._search_brave_sync", return_value=fake_results):
        result = search_web.invoke({"query": query, "max_results": 3})
    assert "Web search results" in result
    assert "MTC Maris Kazang" in result or "example.com" in result


def test_search_web_with_mock_api_returns_formatted_results(monkeypatch):
    """[Telegram] search_web with mocked API returns formatted string (as would be shown in Telegram reply)."""
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
    """[Telegram] _search_brave_sync returns [] when api_key is empty (e.g. unset on server)."""
    assert _search_brave_sync("", "query") == []
    assert _search_brave_sync("  ", "query") == []


def test_search_brave_sync_empty_query():
    """[Telegram] _search_brave_sync returns [] when query is empty (guard against malformed request)."""
    assert _search_brave_sync("key", "") == []
    assert _search_brave_sync("key", "   ") == []


def test_search_brave_sync_mock_httpx():
    """[Telegram] _search_brave_sync with mocked Brave API returns list of dicts (title, url, description, score)."""
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
