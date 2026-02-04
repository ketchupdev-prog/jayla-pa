# Agent node: LLM + tools + memory. See PERSONAL_ASSISTANT_PATTERNS.md C.4.

import re
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
from prompts import JAYLA_SYSTEM_PROMPT, JAYLA_USER_CONTEXT_KNOWN, JAYLA_USER_CONTEXT_UNKNOWN
from rag import retrieve as rag_retrieve

MAX_CONTENT_CHARS = int(os.environ.get("PA_MAX_CONTENT_CHARS", "3500"))

# Timezone for greeting and current date (e.g. "Africa/Windhoek"). Default UTC.
def _get_tz():
    tz_name = os.environ.get("TIMEZONE", "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _get_time_of_day() -> str:
    tz = _get_tz()
    hour = datetime.now(tz).hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "evening"  # night -> "Good evening"


def _get_datetime_context() -> dict:
    """Return full date/time for system prompt so the agent never guesses — weekday, month, year, today, tomorrow, current time (Telegram + CLI)."""
    tz = _get_tz()
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    tomorrow_dt = now + timedelta(days=1)
    tomorrow = tomorrow_dt.strftime("%Y-%m-%d")
    timezone_name = os.environ.get("TIMEZONE", "UTC")
    return {
        "current_date": today,
        "tomorrow_date": tomorrow,
        "timezone": timezone_name,
        "weekday": now.strftime("%A"),           # e.g. Monday
        "month_name": now.strftime("%B"),         # e.g. February
        "year": now.strftime("%Y"),               # e.g. 2025
        "day_of_month": str(now.day),  # e.g. 3
        "current_time_iso": now.strftime("%H:%M"),  # e.g. 14:30
        "current_datetime_iso": now.strftime("%Y-%m-%dT%H:%M:%S"),  # full ISO for "now"
    }


def _truncate(content: str) -> str:
    if not content or len(content) <= MAX_CONTENT_CHARS:
        return content
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[: MAX_CONTENT_CHARS - 20] + "\n\n...[truncated]"


def _ensure_tool_responses(messages: list) -> list:
    """Ensure every AIMessage with tool_calls is followed by a ToolMessage per tool_call_id.
    If auth timed out or tools never ran, inject synthetic ToolMessages so the LLM API (Groq/OpenAI) does not return 400."""
    out = []
    i = 0
    while i < len(messages):
        m = messages[i]
        out.append(m)
        if getattr(m, "tool_calls", None):
            ids_needed = {tc.get("id") for tc in m.tool_calls if tc.get("id")}
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                j += 1
            seen_ids = {messages[k].tool_call_id for k in range(i + 1, j)}
            for tid in ids_needed:
                if tid not in seen_ids:
                    out.append(
                        ToolMessage(
                            content="Error: Tool could not be run (authorization required or request interrupted). Please tell the user they may need to connect their calendar in a browser or try again.",
                            tool_call_id=tid,
                        )
                    )
            for k in range(i + 1, j):
                out.append(messages[k])
            i = j
        else:
            i += 1
    return out


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
    # Store comes from config if not passed (webhook/pa_cli set config["configurable"]["store"])
    store = store or (config.get("configurable") or {}).get("store")
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
    conf = config.get("configurable") or {}
    user_name = (conf.get("user_name") or "").strip()
    user_role = (conf.get("user_role") or "").strip()
    user_company = (conf.get("user_company") or "").strip()
    key_dates = (conf.get("key_dates") or "").strip()
    communication_preferences = (conf.get("communication_preferences") or "").strip()
    current_work_context = (conf.get("current_work_context") or "").strip()
    if user_name or user_role or user_company:
        role_part = f", {user_role}" if user_role else ""
        company_part = f" at {user_company}" if user_company else ""
        user_context = JAYLA_USER_CONTEXT_KNOWN.format(
            user_name=user_name or "the user",
            role_part=role_part,
            company_part=company_part,
        )
    else:
        user_context = JAYLA_USER_CONTEXT_UNKNOWN
    # Build onboarding block for system prompt: preferences and work context (injected so Jayla follows them)
    parts = []
    if key_dates:
        parts.append(f"Key dates to remember: {key_dates}")
    if communication_preferences:
        parts.append(f"Communication preferences: {communication_preferences}. Follow these when replying (e.g. brief vs detailed, boundaries).")
    if current_work_context:
        parts.append(f"Current work: projects, deadlines, tasks, reminders: {current_work_context}. Use this to prioritise and suggest follow-up.")
    onboarding_context = "\n".join(parts) if parts else ""
    dt_ctx = _get_datetime_context()
    # RAG: retrieve top-k chunks for last user message and inject as document context (ONBOARDING_PLAN.md §5, Phase 3)
    last_user_text = ""
    for m in reversed(messages):
        if getattr(m, "type", None) == "human" and getattr(m, "content", None):
            last_user_text = (m.content if isinstance(m.content, str) else str(m.content)).strip()
            break
    user_id_rag = conf.get("user_id") or os.environ.get("EMAIL", "") or (conf.get("thread_id") if isinstance(conf.get("thread_id"), str) else "")
    doc_chunks = rag_retrieve(last_user_text, user_id=user_id_rag or None, limit=5) if last_user_text else []
    document_context = (
        "Document context (use to ground answers):\n" + "\n\n---\n\n".join(doc_chunks)
        if doc_chunks
        else "Document context: (None)"
    )
    system_content = JAYLA_SYSTEM_PROMPT.format(
        **dt_ctx,
        user_context=user_context,
        time_of_day=_get_time_of_day(),
        memory_context=memory_context or "(None)",
        onboarding_context=onboarding_context,
        document_context=document_context,
        current_activity="",
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
    # Ensure every AIMessage with tool_calls has a ToolMessage per tool_call_id (Groq/OpenAI require this)
    trimmed = _ensure_tool_responses(trimmed)
    model = _get_model()
    model_with_tools = model.bind_tools(get_tools_for_model())
    msgs = [SystemMessage(content=system_content)] + list(trimmed)
    response = model_with_tools.invoke(msgs)
    return {"messages": [response]}
