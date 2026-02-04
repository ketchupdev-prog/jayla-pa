# Best Patterns for a Personal Assistant Agent (Jayla)

> Synthesized from **arcade-ai-agent**, **pa-agent**, **pa-agent2**, and **pa-agent3** for building **jayla-pa**: single-user PA with Gmail, Calendar, Telegram, user profiles, onboarding, and optional RAG.

**Principle: an assistant that can’t remember is not acceptable.** Conversation history (messages, tool calls, tool outputs) and long-term facts (“remember X”) must persist. Use a **Postgres checkpointer** for conversation persistence and **Qdrant + memory writing** for long-term semantic memory so the assistant retains past engagements and user-stated facts. See §1.1 and §2.3; implementation status in **docs/WHERE_DATA_IS_STORED.md**.

---

## 1. Architecture Overview

| Layer | Recommended pattern | Source |
|-------|---------------------|--------|
| **LLM** | **Groq** or **DeepSeek** (recommended for less rate limiting; see §1.2) | arcade_1_basics, pa-agent, pa-agent3; §1.2 |
| **Tools** | Arcade `ToolManager` (Gmail, Calendar) + **own-DB project management** (Neon/Postgres) + optional custom tools | arcade_1_basics, pa-agent; §8 |
| **Orchestration** | LangGraph: `agent → authorization (if needed) → tools → agent` | arcade_1_basics, pa-agent |
| **Auth** | Explicit **authorization node** + `manager.authorize()` → show URL → `manager.wait_for_auth()` | arcade_1_basics, AUTHORIZATION.md |
| **User identity** | **User profiles** (Neon `user_profiles`: name, role, company + onboarding fields); `thread_id` per Telegram chat; same `user_id` (e.g. `EMAIL`) for Arcade | jayla-pa user_profile.py, ONBOARDING_PLAN.md |
| **Token limits** | Truncate tool outputs (strip HTML, cap chars) before adding to conversation | arcade_1_basics |

### 1.1 Data stack: Postgres checkpointer + Qdrant + Neon

| Store | Use for | Pattern (source) |
|-------|--------|-------------------|
| **Neon (Postgres) — LangGraph checkpointer** | **Conversations**: messages, tool calls, tool outputs. **Required for production.** Without a persistent checkpointer (e.g. `AsyncPostgresSaver`), history is lost on every deploy/restart and the assistant cannot remember past engagements. Use `langgraph-checkpoint-postgres` with `DATABASE_URL`. | PERSONAL_ASSISTANT_PATTERNS.md §2.3; docs/WHERE_DATA_IS_STORED.md. |
| **Qdrant** | **Long-term memory** (user facts, preferences—“remember X”). Ava-style: when the user says “remember X”, extract the fact, embed, store via `put_memory`; before each turn, retrieve by similarity and inject as `memory_context`. **Both read and write are required**; if nothing writes, memory_context is always empty. | ava-whatsapp-agent-course (§6); memory.py get_memories + put_memory; MEMORY_ANALYSIS_PROMPT + memory extraction node or tool. |
| **Neon (Postgres)** | **User profiles** (thread_id, name, role, company, onboarding: key_dates, communication_preferences, current_work_context, onboarding_step). **Project management** (projects + tasks tables, §8). **RAG** (document chunks, metadata, optional pgvector). **Checkpointer tables** (when using AsyncPostgresSaver). | jayla-pa sql/3-user-profiles.sql, 4-onboarding-fields.sql, ONBOARDING_PLAN.md; §8; langchain-academy/module-6. |

**Summary**: **Conversations** (messages, tool calls/outputs) → **Postgres checkpointer** (Neon) so the assistant remembers past turns across restarts. **Long-term “remember X”** → **Qdrant** (read + write); implement memory extraction and `put_memory` in the graph. **Neon** also holds user profiles, onboarding, project management, RAG, and checkpointer state. See **docs/WHERE_DATA_IS_STORED.md** for what is stored where and what is still to implement.

### 1.2 LLM choice: Groq vs DeepSeek (speed vs reasoning, rate limits)

**DeepSeek** is a good option if you want **less strict rate limiting** (DeepSeek does not enforce fixed rate limits; they adjust dynamically and try to serve every request). Use **LangChain** via `langchain-deepseek` and `ChatDeepSeek` (OpenAI-compatible API).

| Model | Use case | Speed vs reasoning |
|-------|----------|--------------------|
| **deepseek-chat** | **Default for Jayla** — balanced speed and reasoning (non-thinking mode of DeepSeek-V3.2). Best for general PA: email, calendar, tasks, RAG answers. | Faster; strong general quality. |
| **deepseek-reasoner** | When you need multi-step reasoning (complex planning, math, code). Thinking mode, more tokens. | Slower; best reasoning. |

**Recommendation:** Use **deepseek-chat** for the main agent (balance of speed and reasoning). Switch to **deepseek-reasoner** only for flows that need heavy reasoning.

**Compatibility with our embedding model:** The **embedding model** (all-mpnet-base-v2, §8.5a) is **independent** of the LLM. You embed chunks with sentence-transformers and pass **plain text** (retrieved chunks + user message) to the LLM. So DeepSeek is **fully compatible** — no conflict. Same RAG pipeline: retrieve with all-mpnet-base-v2 → inject chunks into context → DeepSeek generates the reply.

**Setup:** `pip install langchain-deepseek`; set `DEEPSEEK_API_KEY`. Use `ChatDeepSeek(model="deepseek-chat", api_key=..., temperature=0)` in place of `ChatGroq` in the agent node. Tool calling is supported. See appendix C.4 (nodes) and C.13 (.env.example).

---

## 2. Core Patterns to Reuse

### 2.1 Authorization (must-have for OAuth tools)

- **Where**: Dedicated graph node `authorization` between `agent` and `tools`.
- **Flow**:  
  1. After `agent` returns tool calls, route to `authorization` if **any** tool `manager.requires_auth(tool_name)`.  
  2. In the node: for each such tool call, call `manager.authorize(tool_name, user_id)`.  
  3. If `auth_response.status != "completed"`: print the auth URL, then call `manager.wait_for_auth(auth_response.id)` and block until the user completes OAuth.  
  4. Then continue to `tools` and execute.
- **Config**: Always pass `user_id` in `config["configurable"]["user_id"]` (e.g. from `EMAIL` in `.env`).
- **Docs**: See `AUTHORIZATION.md` (invite users in Arcade Dashboard → Projects → Members).

```python
# From arcade_1_basics.py (pattern)
def authorize(state, config):
    user_id = config["configurable"].get("user_id")
    for tool_call in state["messages"][-1].tool_calls:
        if not manager.requires_auth(tool_call["name"]):
            continue
        auth_response = manager.authorize(tool_call["name"], user_id)
        if auth_response.status != "completed":
            print(auth_response.url)
            manager.wait_for_auth(auth_response.id)
    return {"messages": []}
```

### 2.2 Tool output truncation (avoid 413 / token limit)

- **Problem**: Large tool payloads (e.g. raw email HTML) blow up context and hit Groq limits.
- **Pattern**: Custom tool node that runs tools then truncates `ToolMessage.content` (strip HTML, normalize whitespace, cap length).

```python
# From arcade_1_basics.py
MAX_TOOL_OUTPUT_CHARS = 3500

def truncate_tool_content(content: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if not content or len(content) <= max_chars:
        return content
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[: max_chars - 20] + "\n\n...[truncated]" if len(text) > max_chars else text
```

Use this in a wrapper around `ToolNode` so every tool message is truncated before being added to state.

### 2.3 Graph structure (LangGraph)

- **Edges**: `START → agent`; from `agent` conditional: `authorization` | `tools` | `END`; `authorization → tools`; `tools → agent`.
- **State**: `MessagesState` (or equivalent with `messages`).
- **Checkpointer (required for production):** **An assistant that can’t remember past conversations is not acceptable.** Use `MemorySaver()` only for local/dev; for production **must** use a Postgres checkpointer (e.g. `AsyncPostgresSaver` from `langgraph-checkpoint-postgres`) with Neon `DATABASE_URL` so conversation history (messages, tool calls, tool outputs) persists across restarts and deploys. Without it, every restart wipes history and the assistant appears forgetful. See §1.1 and docs/WHERE_DATA_IS_STORED.md.

```python
# From arcade_1_basics.py / pa_agent/graph.py
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, ["authorization", "tools", END])
workflow.add_edge("authorization", "tools")
workflow.add_edge("tools", "agent")
```

### 2.4 Routing (should_continue)

- If the last message has tool calls and **any** of them require auth → `"authorization"`.
- Else if there are tool calls → `"tools"`.
- Else → `END`.

```python
def should_continue(state):
    if state["messages"][-1].tool_calls:
        for tool_call in state["messages"][-1].tool_calls:
            if manager.requires_auth(tool_call["name"]):
                return "authorization"
        return "tools"
    return END
```

### 2.5 Single-user config

- One `EMAIL` / `user_id` in env; one optional `TELEGRAM_CHAT_ID` for notifications.
- **jayla-pa**: User identity (name, role, company) and onboarding (key_dates, communication_preferences, current_work_context) come from **Neon `user_profiles`** per `thread_id` (Telegram `chat_id`). Webhook loads profile and passes it in `config["configurable"]`; agent injects it into the system prompt. See ONBOARDING_PLAN.md.

### 2.6 Minimal alternative (no LangGraph): inline auth in loop

- **pa-agent3** pattern: simple loop (Groq chat completion → if tool calls → execute via Arcade; if response contains `authorization_required` / `auth_url`, print URL, `input("Press Enter after you've authorized...")`, then re-call the same tool).
- Use when you want a single-file, minimal PA; trade-off is no graph, no checkpointer, no shared memory across interfaces.

---

## 3. Interface Patterns

| Interface | Pattern | Project |
|-----------|---------|---------|
| **CLI** | `input()` loop, append user/assistant messages, `graph.stream()` or `graph.ainvoke()`; pass `user_name`, `user_role`, `user_company` from env for context | jayla-pa pa_cli.py |
| **Streamlit** | Session state for messages, same graph + config; `thread_id` from session | pa-agent |
| **Telegram** | Webhook or long polling; one `chat_id` → one `thread_id`; load user profile from Neon, pass in config; send agent reply back via bot | jayla-pa telegram_bot/webhook.py |

For Telegram, keep auth handling on a flow that can show a link (e.g. “Open this link to connect Gmail” and optional “Reply when done” or wait via Arcade `wait_for_auth` in a CLI one-time setup).

---

## 4. What to Take from Each Project

| Project | Use for |
|---------|---------|
| **arcade-ai-agent** | Auth node + `wait_for_auth`, tool truncation, LangGraph + Groq + ToolManager wiring, AUTHORIZATION.md. |
| **pa-agent** | Full PA design (PA.md), graph layout, nodes/tools split, memory (Postgres), multi-interface (CLI/Streamlit/Telegram). |
| **pa-agent2** | TypeScript/Node stack: Grammy + Groq + Arcade, calendar-focused logic, disk-backed auth cache. |
| **pa-agent3** | Minimal "Groq + Arcade only" loop and inline auth prompt when you don't want LangGraph. |
| **jayla-pa** | **Implementation**: user_profiles + onboarding (Neon), dynamic user context and onboarding_context in system prompt, Telegram webhook with profile loading, ONBOARDING_PLAN.md. |
| **langchain-academy/module-6** | Task Maistro: Store-backed profile/todo/instructions, typed config, single agent + routed update nodes; deployment: langgraph.json, Docker (§9). |

---

## 5. Checklist for Your New PA Agent

1. **Env**: `ARCADE_API_KEY`, `EMAIL` (or `USER_ID`); either `GROQ_API_KEY` + `GROQ_MODEL` or `DEEPSEEK_API_KEY` + `LLM_MODEL` (e.g. `deepseek-chat`, §1.2); `QDRANT_URL`, `QDRANT_API_KEY` for Qdrant; `DATABASE_URL` (Neon) for user profiles, project management + RAG; optional `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TIMEZONE`, `USER_NAME`/`USER_ROLE`/`USER_COMPANY` for CLI. See §1.1, §1.2, ONBOARDING_PLAN.md.
2. **Arcade**: User invited in Dashboard → Projects → Members; Gmail (and Calendar if used) enabled for the project.
3. **Graph**: Agent → authorization (if any tool requires auth) → tools → agent; `user_id` and (for jayla-pa) user profile fields in config.
4. **Tools**: `ToolManager.init_tools(toolkits=["Gmail", "Google Calendar"])` + custom project/task tools backed by your DB (§8); optional custom tools for attachments/Telegram.
5. **Truncation**: Custom tool node that truncates tool message content (e.g. 3500 chars, HTML stripped).
6. **Memory (required so the assistant remembers):** (a) **Conversation persistence** — Postgres checkpointer (e.g. `AsyncPostgresSaver`) so messages and tool outputs persist across restarts; (b) **Long-term memory** — Qdrant for “remember X” facts: retrieve via `get_memories` (inject `memory_context`) and **write** via `put_memory` when the user says to remember something (memory extraction node or tool + MEMORY_ANALYSIS_PROMPT). Neon for user profiles + onboarding, project management (§8), RAG. See §1.1, §2.3, docs/WHERE_DATA_IS_STORED.md.
7. **Interfaces**: Start with CLI (like arcade_1_basics); add Streamlit or Telegram reusing same graph and config; for Telegram, load user profile and pass onboarding context into system prompt (jayla-pa).

Using these patterns gives you a single-user personal assistant agent with robust auth, token-safe tool use, user profiles and onboarding, and a clear path from minimal (pa-agent3-style) to full PA (jayla-pa + arcade_1_basics).

---

## 6. Gems from ava-whatsapp-agent-course (→ Telegram PA)

> The **ava-whatsapp-agent-course** is a WhatsApp agent (Ava) with LangGraph, Groq, long-term memory (Qdrant), STT/TTS, and image handling. Below are **reusable patterns** mapped to a **Telegram** personal assistant (not WhatsApp). Cross-reference **PA.md** for full PA scope (Gmail, Calendar, project/task management, proactive alerts).

### 6.1–6.8

*(Same as in arcade-ai-agent; see PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md for webhook shape, document/voice/photo handling, and §8.5a.)*

**jayla-pa specifics:** Webhook loads `user_profile` via `user_profile.load_user_profile(chat_id)` and passes `user_name`, `user_role`, `user_company`, `key_dates`, `communication_preferences`, `current_work_context`, `onboarding_step` in `config["configurable"]`. Agent builds `user_context` (known vs unknown) and `onboarding_context` and injects them into the system prompt. See prompts.py, agent.py, ONBOARDING_PLAN.md.

---

## 7. Jayla — Character Card and User Context

> **Jayla** is the persona for the single-user personal assistant. In **jayla-pa**, user identity is **dynamic** (from Neon `user_profiles` and onboarding), not hardcoded. Placeholders: `{user_context}`, `{memory_context}`, `{onboarding_context}`, `{current_activity}`, `{time_of_day}` — see prompts.py and agent.py.

### 7.0 User identity (dynamic in jayla-pa)

Jayla assists **one primary user per thread** (Telegram chat = one thread). Who they are comes from:

| Source | Content |
|--------|---------|
| **user_profiles** (Neon) | `name`, `role`, `company` — loaded by webhook/CLI and passed in config; agent injects into system prompt as `user_context` (known: “The user you assist is {name}, {role} at {company}”; unknown: “You do not yet know who you’re assisting… ask for name, role, company”). |
| **Onboarding** (same table) | `key_dates`, `communication_preferences`, `current_work_context` — injected as `onboarding_context` so Jayla follows preferred style and uses projects/deadlines/tasks/reminders. No VIP/important contacts; we use current work context only. See ONBOARDING_PLAN.md. |

**Implementation**: `user_profile.load_user_profile(thread_id)`; webhook passes profile into `config["configurable"]`; `agent.call_agent()` builds `user_context` (JAYLA_USER_CONTEXT_KNOWN / JAYLA_USER_CONTEXT_UNKNOWN) and `onboarding_context` (only non-empty key_dates, communication_preferences, current_work_context) and formats JAYLA_SYSTEM_PROMPT. Communication preference is **injected into the system prompt** as part of `onboarding_context` so Jayla replies in the user’s preferred style (brief vs detailed, boundaries).

### 7.1 Character card (system prompt)

Use the same structure as in arcade-ai-agent §7.1, but with **dynamic** “Who you assist” and **onboarding** block:

- **Who you assist**: Use `{user_context}` — filled by agent from config (known: name, role, company; unknown: ask for name, role, company).
- **User context**: `{memory_context}` (Qdrant memories) and `{onboarding_context}` (key dates, communication preferences, current work: projects, deadlines, tasks, reminders). If empty, omit.
- **Current activity**: `{current_activity}`; **Time of day**: `{time_of_day}` for greetings (morning/afternoon/evening).

See **prompts.py** (JAYLA_USER_CONTEXT_KNOWN, JAYLA_USER_CONTEXT_UNKNOWN, JAYLA_SYSTEM_PROMPT) and **agent.py** (building user_context, onboarding_context, _get_time_of_day()).

### 7.2 Usage

- **System prompt**: JAYLA_SYSTEM_PROMPT.format(user_context=..., time_of_day=..., memory_context=..., onboarding_context=..., current_activity=...).
- **user_context**: From config (user_name, user_role, user_company) — known vs unknown.
- **onboarding_context**: From config (key_dates, communication_preferences, current_work_context) — only non-empty lines.
- Use the same character card for CLI and Telegram; only the interface and config (and profile loading in webhook) change.

### 7.3 Short variant (minimal system prompt)

For a minimal setup (e.g. pa-agent3-style loop without memory), you can use a shorter system prompt; jayla-pa uses the full prompt with user_context and onboarding_context for Telegram and CLI.

---

## 8. Project management in our database (no Asana)

*(Same as arcade-ai-agent §8; jayla-pa uses sql/1-projects-tasks.sql, tools_custom/project_tasks.py. RAG and document add via Telegram: §8.5, §8.5a; jayla-pa has sql/2-rag-documents.sql with user_id, scope, expires_at, 768d. See ONBOARDING_PLAN.md for document upload and RAG phases.)*

---

## 9. Gems from LangChain Academy Module 6 (Task Maistro + Deployment)

*(Same as arcade-ai-agent §9; jayla-pa uses configuration.py for optional typed config; graph/node layout follows appendix.)*

---

## 10. Gems from Supervisor Pattern (7.7-SupervisorAgent)

Patterns from **7_Agent_Architecture/7.7-SupervisorAgent** that enhance jayla-pa: web search for “current” questions, concise tool summaries, step limit, research-aware email drafting, fallback hint, optional deps, and tests. **Full code for each gem** is in **PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md §D**.

| Gem | Purpose |
|-----|--------|
| **Brave web search** | For “latest”, “current”, “news” queries; use `search_web` when user asks for real-time info; use `search_my_documents` for the user’s uploaded docs. |
| **Prompt: concise tool results** | Ask the model to summarize tool results in 2–4 bullets when replying to the user; avoid pasting raw JSON or long lists. |
| **Max steps in graph** | Cap agent→tools→agent iterations (e.g. 15–20) to prevent infinite loops and control cost; then END and return last reply. |
| **Research-aware email draft** | When drafting email, pre-fill body from RAG/context (bullets); optional tool `suggest_email_body_from_context` returns suggested body text for the agent to pass to Gmail draft. |
| **Fallback hint** | If the user is just chatting or intent is unclear, answer briefly and optionally suggest: “I can also search your docs, check your calendar, or draft an email if you’d like.” |
| **Optional deps module** | Group env-derived deps (e.g. BRAVE_API_KEY, DATABASE_URL) into a small `deps` module and pass into config so tools stay testable. |
| **Pytest** | Add `tests/` with e.g. test_agent.py (call_agent with mocks), test_rag.py (retrieve), test_graph.py (invoke), test_webhook.py (document/voice/retention). |

**Quick wins (in order):** (1) Brave web search tool, (2) prompt tweak for tool summaries, (3) max steps in graph, (4) research-aware draft prompt/helper, (5) pytest.

---

# Appendix reference

**Full project structure, workflows, and reference code** (updated for jayla-pa): see **PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md** in this directory. **Gems implementation (full code)** for §10: Appendix **D** in PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md.
