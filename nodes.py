# Routing and authorization nodes. See PERSONAL_ASSISTANT_PATTERNS.md C.3.

import os
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, MessagesState
from tools import get_manager


def should_continue(state: MessagesState):
    if not state["messages"]:
        return END
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return END
    manager = get_manager()
    for tc in last.tool_calls:
        name = tc.get("name", "")
        try:
            if manager.requires_auth(name):
                return "authorization"
        except (ValueError, KeyError):
            # Tool not in Arcade manager (e.g. list_projects, create_project) — no Arcade auth needed
            continue
    return "tools"


def authorize(state: MessagesState, config: RunnableConfig):
    user_id = config.get("configurable", {}).get("user_id") or os.environ.get("EMAIL", "")
    manager = get_manager()
    for tc in state["messages"][-1].tool_calls:
        name = tc.get("name", "")
        try:
            if not manager.requires_auth(name):
                continue
        except (ValueError, KeyError):
            continue  # Custom tool (e.g. list_projects) — skip Arcade auth
        auth_response = manager.authorize(name, user_id)
        if auth_response.status != "completed":
            print("\n🔐 Authorization required:", auth_response.url)
            manager.wait_for_auth(auth_response.id)
    return {"messages": []}
