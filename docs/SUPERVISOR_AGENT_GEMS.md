# Gems from 7.7-SupervisorAgent for Jayla PA

Summary of files in `7_Agent_Architecture/7.7-SupervisorAgent` and patterns that could enhance the Jayla personal assistant.

---

## File list (7.7-SupervisorAgent)

| Path | Purpose |
|------|--------|
| **README.md** | Architecture, env vars, usage (API, Streamlit), supervisor decision logic |
| **CLAUDE.md** | Project rules: &lt;500 lines/file, prompts in prompts.py, pytest, docstrings |
| **.env.example** | LLM, Supabase, Brave, Asana, Gmail, Langfuse |
| **agents/__init__.py** | Package |
| **agents/deps.py** | Dependency dataclasses (Guardrail, Research, EmailDraft) + factory functions |
| **agents/prompts.py** | Centralized prompts: SUPERVISOR, WEB_RESEARCH, TASK_MANAGEMENT, EMAIL_DRAFT, FALLBACK; `get_current_date()` |
| **agents/supervisor_agent.py** | Pydantic AI Agent with SupervisorDecision (messages, delegate_to, reasoning, final_response); streaming |
| **agents/web_research_agent.py** | Brave-backed agent; tools: search_web, conduct_comprehensive_search, analyze_search_results, search_with_context |
| **agents/task_management_agent.py** | Asana-backed agent; tools: get_workspace_info, create/list/get project, create/update/list tasks |
| **agents/email_draft_agent.py** | Gmail-backed agent; tools: create_gmail_draft, list_gmail_drafts, draft_research_based_email |
| **agents/fallback_agent.py** | General conversation when request doesn’t fit research/task/email |
| **graph/state.py** | SupervisorAgentState: query, session_id, iteration_count, shared_state, delegate_to, final_response, workflow_complete, message_history |
| **graph/workflow.py** | LangGraph: supervisor_node → route_supervisor_decision → web_research_node \| task_management_node \| email_draft_node → back to supervisor; 20-iteration limit; create_api_initial_state, extract_api_response_data |
| **api/endpoints.py** | FastAPI: JWT (Supabase), conversation history, rate limit, streaming; POST /api/langgraph-supervisor-agent |
| **api/streaming.py** | StreamBridge (Queue + write/stream_http/complete), ErrorStreamBridge, stream_workflow_response |
| **api/db_utils.py** | Supabase: fetch_conversation_history, store_message, rate limit, etc. |
| **api/models.py** | Pydantic request/response models |
| **tools/brave_tools.py** | search_web_tool (Brave Search API), rate limiting, error handling |
| **tools/asana_tools.py** | create/list/get project, create/update/list tasks, get_workspace_info |
| **tools/gmail_tools.py** | create_email_draft_tool, list_email_drafts_tool |
| **clients.py** | get_model(), get_agent_clients(), get_langfuse_client() |
| **streamlit_app.py** | Streamlit UI for testing the workflow |
| **PRPs/supervisor-pattern-langgraph-workflow.md** | PRP: shared state, intelligent orchestration, 20-iteration cap |
| **tests/** | test_supervisor_agent, test_supervisor_workflow, test_web_research_agent, test_task_management_agent, test_email_draft_agent, test_fallback_agent |

---

## Gems to enhance Jayla PA

### 1. **Web search (Brave) for “current” questions**

- **What:** `tools/brave_tools.py` + `agents/web_research_agent.py`: Brave Search API, tools like `search_web`, `conduct_comprehensive_search`, `analyze_search_results`, `search_with_context`.
- **Gem:** When the user asks for “latest news”, “current trends”, “what’s happening with X”, Jayla could call a **web search tool** (Brave or similar) instead of only RAG/calendar/email.
- **For Jayla:** Add optional `BRAVE_API_KEY`; implement `tools_custom/brave_tools.py` with a single `search_web(query, max_results=5)` and register it in `tools.get_tools_for_model()`. Prompt: “Use search_web for current events, recent news, or real-time information; use search_my_documents for the user’s uploaded docs.”

---

### 2. **Shared state + concise sub-agent summaries**

- **What:** `graph/state.py`: `shared_state: List[str]` append-only; each sub-agent appends one short summary (e.g. “Web Research: …”, “Task Management: …”).
- **Gem:** Sub-agents don’t dump full output into the next step; they write **concise bullet summaries** (see prompts: “CONCISE”, “under 500 words”, “bullet points”). Supervisor then synthesizes from shared state.
- **For Jayla:** You already have one agent + tools. To avoid context overflow when chaining many tools: (a) in the system prompt, ask the model to **summarize tool results in 2–3 bullets** when reporting back to the user; (b) if you ever add a “research” sub-graph, have it append a short summary to state instead of raw search results.

---

### 3. **Streaming final response only**

- **What:** `graph/workflow.py` – supervisor uses `run_stream()` and streams only the `messages` field when `final_response=True`; sub-agents use `run()` (no streaming) and only update state.
- **Gem:** User sees typing/streaming only for the **final** answer, not for every internal step.
- **For Jayla:** Telegram: if you support streaming (e.g. edit message repeatedly or send chunks), stream only the **last** assistant message (the one the user sees). Don’t stream intermediate tool calls.

---

### 4. **Iteration / step limit**

- **What:** `graph/workflow.py`: `route_supervisor_decision` checks `iteration_count >= 20` and sends to END; state carries `iteration_count`.
- **Gem:** Prevents infinite delegation loops and caps cost/latency.
- **For Jayla:** In `graph.py` / LangGraph, add a **max step count** (e.g. 15–20). After that, force END and return whatever the agent has so far (with a short “I’ve hit the step limit; here’s what I have” if you want).

---

### 5. **Centralized prompts + date and output rules**

- **What:** `agents/prompts.py`: one file for all agent prompts; `get_current_date()`; each sub-agent prompt states “CRITICAL: Your output will be shared with other agents … CONCISE … bullet points … under 500 words”.
- **Gem:** Single place for prompt edits; explicit “output format” rules reduce noise and token use.
- **For Jayla:** You already have `prompts.py` and datetime context. Add one short block: “When reporting tool results to the user, use 2–4 bullet points; avoid pasting raw JSON or long lists.”

---

### 6. **Research-aware email drafting**

- **What:** `agents/email_draft_agent.py`: `draft_research_based_email(recipient_email, subject, purpose, research_context=None, key_findings=None, tone=…)` builds body from research + findings.
- **Gem:** Email body is **pre-structured** from context (research + key findings + tone), not only free-form LLM output.
- **For Jayla:** When the user says “draft an email to X about Y” and you have RAG chunks or previous context: (a) call your existing Gmail/Arcade draft tool with a **body** that you build from `document_context` + `key_findings` (e.g. 2–3 bullets); or (b) add a simple helper that formats “Purpose: …; Key points: …; Tone: …” and pass that into the draft tool. Makes drafts more consistent and grounded.

---

### 7. **Fallback / general conversation**

- **What:** `agents/fallback_agent.py` + `FALLBACK_SYSTEM_PROMPT`: handles “normal” conversation, suggests rephrasing for research/task/email when appropriate.
- **Gem:** One agent dedicated to “this doesn’t need tools” and gentle routing hints.
- **For Jayla:** Your single agent already does this (answer or use tools). You could add a **fallback** system line: “If the user is just chatting or the request is unclear, answer briefly and optionally suggest: ‘I can also search your docs, check your calendar, or draft an email if you’d like.’ ”

---

### 8. **Dependency injection per “agent”**

- **What:** `agents/deps.py` + each agent: dataclasses (e.g. `WebResearchAgentDependencies(brave_api_key, session_id)`) and factory functions (`create_research_deps(session_id)`).
- **Gem:** Credentials and session are passed explicitly; no global API keys inside agents.
- **For Jayla:** You already pass `config["configurable"]` (user_id, profile, etc.). Optional: group env-derived deps (e.g. BRAVE_API_KEY, DATABASE_URL) into a small `deps` module and pass a single object into the graph so tools stay testable and explicit.

---

### 9. **HTTP streaming bridge**

- **What:** `api/streaming.py`: `StreamBridge` with `write()` (called by LangGraph), `stream_http()` (async iterator for FastAPI), `complete()`.
- **Gem:** Clean separation between “workflow writes chunks” and “HTTP streams chunks”.
- **For Jayla:** If you add an **HTTP API** (e.g. for a web client) and want streaming: use a similar bridge (queue + async iterator) so the graph’s writer and the HTTP response stay decoupled.

---

### 10. **API: auth, rate limit, conversation history**

- **What:** `api/endpoints.py`: JWT (Supabase), rate limit, conversation history, request_id, session_id; `db_utils` for fetch/store.
- **Gem:** Production-ready API pattern for authenticated, traceable, multi-turn use.
- **For Jayla:** Telegram is primary; if you add a **REST API** later, reuse: auth middleware, rate limit per user, store messages by session_id, return request_id and session_id in responses.

---

### 11. **Structured supervisor decision**

- **What:** `SupervisorDecision`: `messages`, `delegate_to`, `reasoning`, `final_response`; supervisor returns this so the graph can route.
- **Gem:** Routing is **explicit** and inspectable (reasoning, which agent next).
- **For Jayla:** You use “agent returns tool_calls or message”. If you ever introduce a **supervisor** (e.g. “research vs calendar vs email” coordinator), give it a small structured output (e.g. `delegate_to: "research" | "calendar" | "email" | "reply"`, `reasoning: str`) and route in the graph on that.

---

### 12. **Testing**

- **What:** `tests/`: per-agent and workflow tests (e.g. test_supervisor_agent, test_supervisor_workflow, test_web_research_agent).
- **Gem:** Each component has unit tests; workflow has integration tests.
- **For Jayla:** Add `tests/` with e.g. `test_agent.py` (call_agent with mock tools), `test_rag.py` (retrieve), `test_graph.py` (invoke with mock state), and optionally `test_webhook.py` (document/voice/retention flows).

---

## Quick wins for Jayla (in priority order)

1. **Brave (or similar) web search tool** – for “current”, “latest”, “news” queries.
2. **Prompt tweak** – “Summarize tool results in 2–4 bullets for the user.”
3. **Max steps in graph** – e.g. 15–20, then END.
4. **Research-aware draft** – when drafting email, pre-fill body from RAG/context (bullets).
5. **Optional pytest** – agent, RAG, graph, webhook.

---

*Source: `7_Agent_Architecture/7.7-SupervisorAgent/` (README, CLAUDE.md, agents/, graph/, api/, tools/, PRPs/, tests/).*
