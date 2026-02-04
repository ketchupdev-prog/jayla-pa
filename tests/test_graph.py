# Tests for graph build and invoke. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.

import pytest
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage

from graph import build_graph
from state import JaylaState


def test_build_graph():
    """Graph builds and compiles."""
    graph = build_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_invoke():
    """Graph ainvoke returns state with messages and step_count (mocked agent to avoid LLM call)."""
    def mock_call_agent(state, config=None, *, store=None):
        return {"messages": [AIMessage(content="Hi there!")], "step_count": state.get("step_count", 0) + 1}

    with patch("graph.call_agent", side_effect=mock_call_agent):
        graph = build_graph()
        config = {
            "configurable": {
                "thread_id": "test",
                "user_id": "test@example.com",
                "user_name": "",
                "user_role": "",
                "user_company": "",
            }
        }
        inputs: JaylaState = {"messages": [HumanMessage(content="Hello")], "step_count": 0}
        result = await graph.ainvoke(inputs, config=config)
        assert "messages" in result
        assert "step_count" in result
        assert result["step_count"] >= 0
