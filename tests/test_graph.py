# Tests for graph build and invoke. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.
# Tests use a Telegram perspective: config and message shape as from telegram_bot/webhook.py.

import pytest
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage

from graph import build_graph
from state import JaylaState


def test_build_graph():
    """[Telegram] Graph builds and compiles (same graph used by webhook on POST /webhook)."""
    graph = build_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_invoke():
    """[Telegram] Graph ainvoke with Telegram-style config (thread_id=chat_id, empty profile) returns state (mocked agent)."""
    def mock_call_agent(state, config=None, *, store=None):
        return {"messages": [AIMessage(content="Hi there!")], "step_count": state.get("step_count", 0) + 1}

    with patch("graph.call_agent", side_effect=mock_call_agent):
        graph = build_graph()
        # Config shape as set by telegram_bot/webhook.py for a Telegram user (thread_id=chat_id, optional empty profile)
        config = {
            "configurable": {
                "thread_id": "123456789",
                "user_id": "test@example.com",
                "user_name": "",
                "user_role": "",
                "user_company": "",
                "key_dates": "",
                "communication_preferences": "",
                "current_work_context": "",
                "onboarding_step": 0,
                "store": None,
            }
        }
        inputs: JaylaState = {"messages": [HumanMessage(content="Hello")], "step_count": 0}
        result = await graph.ainvoke(inputs, config=config)
        assert "messages" in result
        assert "step_count" in result
        assert result["step_count"] >= 0


@pytest.mark.asyncio
async def test_graph_invoke_telegram_web_search_message(monkeypatch):
    """[Telegram] When user sends 'find out more about X on the internet', graph runs with Telegram config (empty profile). When BRAVE_API_KEY set, search_web is available for agent."""
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    def mock_call_agent(state, config=None, *, store=None):
        return {"messages": [AIMessage(content="Here is what I found.")], "step_count": state.get("step_count", 0) + 1}

    with patch("graph.call_agent", side_effect=mock_call_agent):
        graph = build_graph()
        # Exact message shape as from Telegram: user may not have provided name/role/company yet
        telegram_message = "Okay find out more about MTC maris and Kazang deal on the internet"
        config = {
            "configurable": {
                "thread_id": "987654321",
                "user_id": "",
                "user_name": "",
                "user_role": "",
                "user_company": "",
                "key_dates": "",
                "communication_preferences": "",
                "current_work_context": "",
                "onboarding_step": 0,
                "store": None,
            }
        }
        inputs: JaylaState = {"messages": [HumanMessage(content=telegram_message)], "step_count": 0}
        result = await graph.ainvoke(inputs, config=config)
        assert "messages" in result
        assert result.get("step_count", 0) >= 0
    # When BRAVE_API_KEY set, Brave tools include search_web so agent can fulfill "on the internet" requests
    from tools_custom.brave_tools import get_brave_tools
    brave_tools = get_brave_tools()
    assert len(brave_tools) == 1 and brave_tools[0].name == "search_web"
