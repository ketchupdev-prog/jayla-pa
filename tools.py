# Arcade (Gmail, Calendar) + custom project/task tools. See PERSONAL_ASSISTANT_PATTERNS.md C.5.

import os
from langchain_arcade import ToolManager

try:
    from langgraph.prebuilt import ToolNode
except ImportError:
    from langgraph.prebuilt.tool_node import ToolNode

_manager = None
_tool_node = None


def get_manager():
    global _manager
    if _manager is None:
        _manager = ToolManager(api_key=os.environ["ARCADE_API_KEY"])
        _manager.init_tools(toolkits=["Gmail", "GoogleCalendar"])
    return _manager


def get_tools():
    from tools_custom.project_tasks import get_project_tools
    from tools_custom.rag_tools import get_rag_tools
    from tools_custom.brave_tools import get_brave_tools
    manager = get_manager()
    arcade_tools = manager.to_langchain(use_interrupts=True)
    return arcade_tools + get_project_tools() + get_rag_tools() + get_brave_tools()


def get_tools_for_model():
    return get_tools()


def get_tool_node():
    global _tool_node
    if _tool_node is None:
        _tool_node = ToolNode(get_tools())
    return _tool_node
