# Tests for state (JaylaState, MAX_GRAPH_STEPS). See PERSONAL_ASSISTANT_PATTERNS.md §10.

from state import JaylaState, MAX_GRAPH_STEPS


def test_max_graph_steps_defined():
    """MAX_GRAPH_STEPS is a positive int."""
    assert MAX_GRAPH_STEPS == 20


def test_jayla_state_has_messages_and_step_count():
    """JaylaState TypedDict allows messages and step_count."""
    state: JaylaState = {"messages": [], "step_count": 0}
    assert state["step_count"] == 0
    assert state["messages"] == []
