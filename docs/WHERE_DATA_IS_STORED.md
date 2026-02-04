# Where jayla-pa stores data (and why the agent can seem forgetful)

This doc explains **where** conversations, onboarding, tool outputs, and long-term memory live—and **why** the agent doesn’t retain past engagements across restarts.

---

## 1. Conversations (messages, tool calls, tool outputs)

| What | Where | Persisted? |
|------|--------|------------|
| **Messages** (user + assistant) | LangGraph **checkpointer** | **No** (in-memory only) |
| **Tool calls and tool outputs** | Same checkpointer (part of graph state) | **No** |

**How it works today**

- In `graph.py` the graph is compiled with `MemorySaver()` (in-memory checkpointer).
- The webhook passes `thread_id: chat_id`, so **within one process** the graph keeps conversation history per Telegram chat.
- **On deploy or process restart** (e.g. on Railway), that process memory is wiped, so **all prior messages and tool outputs are lost**. The next request starts with an empty conversation.

**Why the agent feels forgetful**

- After every deploy/restart there is **no** past conversation or tool output.
- There is **no** shared history across multiple server instances.

**Production (implemented)**

- When **`DATABASE_URL`** is set, the webhook uses **`AsyncPostgresSaver`** from `langgraph-checkpoint-postgres` so conversation history (messages + tool calls/outputs) is stored in Neon and survives restarts. The webhook lifespan runs `checkpointer.setup()` on startup (idempotent). Optional: run `python scripts/setup_checkpointer.py` once before first deploy.

---

## 2. Onboarding / user profile (name, role, company, preferences)

| What | Where | Persisted? |
|------|--------|------------|
| **Name, role, company** | Neon table **`user_profiles`** | **Yes** |
| **key_dates, communication_preferences, current_work_context, onboarding_step** | Same table (see `sql/4-onboarding-fields.sql`) | **Yes** |

**How it works**

- `user_profile.load_user_profile(thread_id)` reads from Neon on every webhook; `save_user_profile(...)` writes.
- Profile is keyed by **thread_id** (= Telegram `chat_id`).
- The webhook injects profile into `config["configurable"]` (user_name, user_role, user_company, etc.), and the agent uses it in the system prompt.

So **onboarding and user context are retained** as long as they’ve been saved (e.g. after the user says “I’m George, MD at Ketchup” and we run `extract_profile_from_message` + `save_user_profile`). If the user never said something that triggered a save, those fields stay empty and the agent won’t “know” them.

---

## 3. Long-term memory (“remember X” facts)

| What | Where | Persisted? |
|------|--------|------------|
| **Semantic “remember” facts** | Qdrant collection **`long_term_memory`** | **Read: yes. Write: not wired yet** |

**How it works**

- **Read:** The agent gets a memory store from `config["configurable"]["store"]`. `get_memories(store, namespace, last_user_message)` runs and injects `memory_context` into the system prompt. So **retrieval** from Qdrant works when the store is set.
- **Write:** `put_memory()` exists in `memory.py` but **is not called anywhere** in the graph (no node that detects “remember X” and writes to the store). So no facts are stored yet; the collection stays empty and the agent can’t “remember” things across sessions via Qdrant.

---

## 4. RAG (uploaded documents)

| What | Where | Persisted? |
|------|--------|------------|
| **Document chunks and embeddings** | Neon table **`documents`** (and schema in `sql/2-rag-documents.sql`) | **Yes** (when embedding is available; on Railway slim image, ingest returns a message that embedding isn’t available) |

---

## Summary: why the agent doesn’t retain “past engagements”

1. **Conversations and tool output** → Only in **MemorySaver**. Lost on every restart/deploy. **Fix:** Add Postgres checkpointer (e.g. `AsyncPostgresSaver`) so conversation history persists.
2. **Onboarding / user info** → Already in **Neon** `user_profiles`; loaded every request. If the user never triggered a profile save, those fields are empty.
3. **“Remember X” facts** → **Qdrant** is only read from; nothing writes. **Fix:** Add a graph step (or tool) that calls `put_memory(store, namespace, data)` when the user says to remember something.

---

## Quick reference

| Data | Storage | Key | Persisted? |
|------|---------|-----|------------|
| Messages, tool calls/outputs | LangGraph checkpointer: Postgres when DATABASE_URL set, else MemorySaver | thread_id (= chat_id) | Yes (Postgres) / No (MemorySaver) |
| User profile / onboarding | Neon `user_profiles` | thread_id | Yes |
| Long-term “remember” facts | Qdrant `long_term_memory` | namespace (e.g. memories\|user_id) | Read only; write not in graph |
| RAG documents | Neon `documents` | user_id, metadata | Yes (when embedding available) |
