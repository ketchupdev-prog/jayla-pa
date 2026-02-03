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
        if manager.requires_auth(tc.get("name", "")):
            return "authorization"
    return "tools"


def authorize(state: MessagesState, config: RunnableConfig):
    user_id = config.get("configurable", {}).get("user_id") or os.environ.get("EMAIL", "")
    manager = get_manager()
    for tc in state["messages"][-1].tool_calls:
        name = tc.get("name", "")
        if not manager.requires_auth(name):
            continue
        auth_response = manager.authorize(name, user_id)
        if auth_response.status != "completed":
            print("\n🔐 Authorization required:", auth_response.url)
            manager.wait_for_auth(auth_response.id)
    return {"messages": []}
