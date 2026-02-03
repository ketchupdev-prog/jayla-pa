# Agent node: LLM + tools + memory. See PERSONAL_ASSISTANT_PATTERNS.md C.4.

import re
import os
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:
    ChatDeepSeek = None
from langchain_groq import ChatGroq

from tools import get_tools_for_model
from memory import get_memory_namespace, get_memories
from prompts import JAYLA_SYSTEM_PROMPT

MAX_CONTENT_CHARS = int(os.environ.get("PA_MAX_CONTENT_CHARS", "3500"))


def _truncate(content: str) -> str:
    if not content or len(content) <= MAX_CONTENT_CHARS:
        return content
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[: MAX_CONTENT_CHARS - 20] + "\n\n...[truncated]"


def _get_model():
    if os.environ.get("DEEPSEEK_API_KEY") and ChatDeepSeek:
        return ChatDeepSeek(
            model=os.environ.get("LLM_MODEL", "deepseek-chat"),
            api_key=os.environ["DEEPSEEK_API_KEY"],
            temperature=0,
        )
    return ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
    )


def call_agent(state: MessagesState, config: RunnableConfig, *, store=None):
    messages = state["messages"]
    memory_context = ""
    if store:
        namespace, _ = get_memory_namespace(config)
        last_user = next(
            (m for m in reversed(messages) if getattr(m, "type", None) == "human"),
            None,
        )
        if last_user:
            memories = get_memories(store, namespace, str(last_user.content))
            memory_context = "\n".join(f"- {m}" for m in memories) if memories else ""
    system_content = JAYLA_SYSTEM_PROMPT.format(
        memory_context=memory_context or "(None)", current_activity=""
    )
    trimmed = [
        m
        if not (
            isinstance(m, ToolMessage)
            and len((m.content or "")) > MAX_CONTENT_CHARS
        )
        else ToolMessage(
            content=_truncate(m.content), tool_call_id=m.tool_call_id
        )
        for m in messages
    ]
    model = _get_model()
    model_with_tools = model.bind_tools(get_tools_for_model())
    msgs = [SystemMessage(content=system_content)] + list(trimmed)
    response = model_with_tools.invoke(msgs)
    return {"messages": [response]}
