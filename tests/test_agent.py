# Tests for agent node. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from agent import call_agent


@pytest.fixture
def minimal_config():
    return {
        "configurable": {
            "thread_id": "test",
            "user_id": "test@example.com",
            "user_name": "",
            "user_role": "",
            "user_company": "",
            "key_dates": "",
            "communication_preferences": "",
            "current_work_context": "",
        }
    }


def test_call_agent_returns_messages(minimal_config):
    """call_agent returns dict with messages and step_count."""
    fake_response = AIMessage(content="Hello!")
    with patch("agent.get_tools_for_model", return_value=[]):
        with patch("agent._get_model") as mock_model:
            mock_model.return_value.bind_tools.return_value.invoke.return_value = fake_response
            state = {"messages": [HumanMessage(content="Hi")], "step_count": 0}
            out = call_agent(state, minimal_config)
            assert "messages" in out
            assert len(out["messages"]) == 1
            assert "step_count" in out
            assert out["step_count"] == 1
