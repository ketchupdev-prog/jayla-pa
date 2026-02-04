# LangGraph state for jayla-pa: messages + step_count (max-iteration cap). See PERSONAL_ASSISTANT_PATTERNS.md §10.

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class JaylaState(TypedDict, total=False):
    """State with messages and step_count for max-iteration cap."""
    messages: Annotated[list, add_messages]
    step_count: int


MAX_GRAPH_STEPS = 20
