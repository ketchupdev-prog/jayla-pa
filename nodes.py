# Routing and authorization nodes. See PERSONAL_ASSISTANT_PATTERNS.md C.3, §10 (max steps).

import os
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END

from state import MAX_GRAPH_STEPS
from tools import get_manager


def should_continue(state):
    if state.get("step_count", 0) >= MAX_GRAPH_STEPS:
        return END
    if not state.get("messages"):
        return END
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return END
    try:
        manager = get_manager()
    except Exception:
        manager = None  # No Arcade (e.g. ARCADE_API_KEY unset) — all tools (e.g. generate_image) go to tools
    for tc in last.tool_calls:
        name = tc.get("name", "")
        if manager is None:
            continue
        try:
            if manager.requires_auth(name):
                return "authorization"
        except (ValueError, KeyError):
            # Tool not in Arcade manager (e.g. list_projects, generate_image) — no Arcade auth needed
            continue
    return "tools"


def authorize(state, config: RunnableConfig):
    """Arcade auth (same for Gmail and Google Calendar): authorize first, then continue. Uses manager.authorize(tool_name, user_id). If not completed, show URL and either block (CLI) or return link in ToolMessages (webhook)."""
    user_id = config.get("configurable", {}).get("user_id") or os.environ.get("EMAIL", "")
    try:
        manager = get_manager()
    except Exception:
        manager = None
    if manager is None:
        return {"messages": []}
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    auth_url = None
    pending_ids = []  # tool_call ids that required auth and were not completed
    for tc in tool_calls:
        name = tc.get("name", "")
        try:
            if not manager.requires_auth(name):
                continue
        except (ValueError, KeyError):
            continue  # Custom tool — skip Arcade auth
        auth_response = manager.authorize(name, user_id)
        if auth_response.status != "completed":
            auth_url = auth_response.url
            pending_ids.append(tc.get("id"))
            print("\n🔐 Authorization required:", auth_url)
            # CLI/local: block until user authorizes (docs: authorize first, then continue)
            if not os.environ.get("PA_AUTH_NONBLOCK"):
                manager.wait_for_auth(auth_response.id)
            break  # one URL per flow
    # Webhook (PA_AUTH_NONBLOCK=1): can't block — add ToolMessages with link so agent replies "Open this link, then ask again"
    if auth_url and os.environ.get("PA_AUTH_NONBLOCK") and pending_ids:
        link_msg = (
            f"Authorization required. To connect your calendar/Gmail, open this link in your browser: {auth_url} "
            "After connecting, ask your question again."
        )
        return {
            "messages": [ToolMessage(content=link_msg, tool_call_id=tid) for tid in pending_ids if tid]
        }
    return {"messages": []}
