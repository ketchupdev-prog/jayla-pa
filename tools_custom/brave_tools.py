# Brave Search tool for "current" / "latest" / "news" queries. See PERSONAL_ASSISTANT_PATTERNS.md §10.

import os
import time
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _search_brave_sync(api_key: str, query: str, count: int = 5) -> list[dict[str, Any]]:
    """Call Brave Search API (sync). Returns list of {title, url, description, score}."""
    if not api_key or not query or not query.strip():
        return []
    count = min(max(count, 1), 10)
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; pip install httpx for Brave search")
        return []
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    params = {"q": query.strip(), "count": count}
    time.sleep(0.5)  # Light rate limiting
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
            )
            if r.status_code != 200:
                logger.warning(f"Brave API {r.status_code}: {r.text[:200]}")
                return []
            data = r.json()
            web = data.get("web", {}).get("results", [])
            out = []
            for i, item in enumerate(web):
                score = max(0.1, 1.0 - (i * 0.05))
                out.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "score": score,
                })
            return out
    except Exception as e:
        logger.warning(f"Brave search failed: {e}")
        return []


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for current information (news, trends, latest). Call this when the user asks for "latest", "current", "news", "what's happening", or real-time info. Use search_my_documents for the user's uploaded docs."""
    api_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not api_key:
        return "Web search is not configured (BRAVE_API_KEY missing). I can only search your uploaded documents."
    try:
        results = _search_brave_sync(api_key, query, max_results)
    except Exception as e:
        return f"Web search failed: {e}"
    if not results:
        return "No web results found for that query."
    lines = ["Web search results:\n"]
    for r in results[:max_results]:
        lines.append(f"- **{r.get('title', '')}**\n  {r.get('url', '')}\n  {r.get('description', '')}")
    return "\n".join(lines)


def get_brave_tools():
    """Return list of Brave tools (empty if BRAVE_API_KEY not set)."""
    if os.environ.get("BRAVE_API_KEY", "").strip():
        return [search_web]
    return []
