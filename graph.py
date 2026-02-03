# LangGraph workflow: agent → authorization | tools → agent. See PERSONAL_ASSISTANT_PATTERNS.md C.2.

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from agent import call_agent
from nodes import authorize, should_continue
from tools import get_tool_node


def build_graph(checkpointer=None):
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", get_tool_node())
    workflow.add_node("authorization", authorize)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, ["authorization", "tools", END])
    workflow.add_edge("authorization", "tools")
    workflow.add_edge("tools", "agent")
    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory)
