# Tests for state (JaylaState, MAX_GRAPH_STEPS). See PERSONAL_ASSISTANT_PATTERNS.md §10.
# Perspective: state shape as used by graph when processing Telegram messages.

from state import JaylaState, MAX_GRAPH_STEPS


def test_max_graph_steps_defined():
    """[Telegram] MAX_GRAPH_STEPS caps agent→tools→agent iterations (same cap for webhook)."""
    assert MAX_GRAPH_STEPS == 20


def test_jayla_state_has_messages_and_step_count():
    """[Telegram] JaylaState TypedDict allows messages and step_count (inputs from webhook)."""
    state: JaylaState = {"messages": [], "step_count": 0}
    assert state["step_count"] == 0
    assert state["messages"] == []
