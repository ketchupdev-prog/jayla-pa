# LangGraph workflow: agent → authorization | tools → agent. See PERSONAL_ASSISTANT_PATTERNS.md C.2.

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from agent import call_agent
from nodes import authorize, should_continue


async def _tools_node(state, config):
    """Lazy tools node so get_tool_node() (and thus ARCADE_API_KEY) is only needed when tools run."""
    from tools import get_tool_node
    return await get_tool_node().ainvoke(state, config)


def build_graph(checkpointer=None):
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", _tools_node)
    workflow.add_node("authorization", authorize)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, ["authorization", "tools", END])
    workflow.add_edge("authorization", "tools")
    workflow.add_edge("tools", "agent")
    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory)
