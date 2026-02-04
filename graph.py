# LangGraph workflow: agent → authorization | tools → agent. See PERSONAL_ASSISTANT_PATTERNS.md C.2, §10 (max steps).

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent import call_agent
from nodes import authorize, should_continue
from state import JaylaState


async def _tools_node(state: JaylaState, config):
    """Lazy tools node; increment step_count so we cap agent→tools→agent iterations."""
    from tools import get_tool_node
    result = await get_tool_node().ainvoke(state, config)
    result["step_count"] = state.get("step_count", 0) + 1
    return result


def build_graph(checkpointer=None):
    workflow = StateGraph(JaylaState)
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", _tools_node)
    workflow.add_node("authorization", authorize)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, ["authorization", "tools", END])
    workflow.add_edge("authorization", "tools")
    workflow.add_edge("tools", "agent")
    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory)
