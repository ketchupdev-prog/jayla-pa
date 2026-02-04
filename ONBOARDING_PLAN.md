# Jayla Onboarding Plan

Plan for **onboarding** (max 5 questions + document upload) so Jayla knows who she’s serving and can use company/legal/compliance docs in RAG.

**Principle: an assistant that can’t remember is not acceptable.** Before or alongside onboarding, ensure the assistant can retain past engagements and user-stated facts. See **§8. Retention and memory (assistant must remember)** and **PERSONAL_ASSISTANT_PATTERNS.md** §1.1, §2.3; **docs/WHERE_DATA_IS_STORED.md** for where data lives and what to implement.

---

## 1. Research: What a PA/EA Needs to Know

From EA/PA practice and “Working With Me”–style guides:

| Category | Why it matters for Jayla |
|----------|--------------------------|
| **Identity & role** | Name, role, company — already in place; used for addressing and context. |
| **Key dates** | Birthday, spouse/partner anniversary, company milestones — reminders, thoughtful replies, “don’t schedule on X.” Optional but high value. |
| **Communication preferences** | Brief vs detailed, channels, “never do” (e.g. no pop-ups 8–10am) — tone and behaviour of replies. |
| **Current work context** | Projects they’re on, deadlines, tasks for completion, reminders — so Jayla can help with priorities and follow-up. |
| **Documents** | Legal, compliance, contracts, company docs — RAG so answers are grounded in real policies and terms. |

**Conclusion:** Keep **identity** (name, role, company). Add up to **4 more** areas, so **max 5 “slots”** in total. Birthday/anniversary are optional; we treat them as one “key dates” question. **Do not use VIP/important contacts** — instead use **current work context**: what project they’re on, potential deadlines or tasks for completion, reminders, etc.

---

## 2. The 5 Onboarding Questions (Max)

| # | Question (Jayla asks) | What we store | Required? |
|---|------------------------|----------------|----------|
| 1 | **Name, role, company** — “What’s your name, your role, and your company?” | `user_profiles`: name, role, company | Yes (already implemented) |
| 2 | **Key dates** — “Any key dates you’d like me to remember? (e.g. birthday, anniversary, important deadlines)” | `user_profiles`: key_dates (TEXT) | No |
| 3 | **Communication preferences** — “How do you prefer I communicate? (e.g. brief bullet points vs detailed, and any ‘never do’ or focus-time boundaries)” | `user_profiles`: communication_preferences (TEXT) | No |
| 4 | **Current work context** — “What projects are you working on, any upcoming deadlines or tasks you want completed, or reminders I should help with?” | `user_profiles`: current_work_context (TEXT) | No |
| 5 | **Documents** — “You can send me important documents (contracts, compliance, legal, company docs) and I’ll use them to answer questions. Want to upload any now?” | Invitation only; actual content → RAG `documents` table | No |

- **1** is already in place (name, role, company).
- **2–5** are optional; user can answer “skip” or “none” and still finish onboarding.
- We ask **one at a time** in Telegram (conversational), and track “onboarding step” per thread so we don’t repeat.

---

## 2b. How Onboarding Data Is Used: System Prompt Injection

**All onboarding answers are injected into the system prompt** so Jayla’s behaviour and tone match what the user asked for.

- **Where:** In `agent.call_agent()`, after loading the user profile (name, role, company and any onboarding fields), we build a single **“User preferences and context”** block (`onboarding_context`) and pass it into the system prompt (see `prompts.JAYLA_SYSTEM_PROMPT` placeholder `{onboarding_context}`).
- **What gets injected:**
  - **Identity** — already in `user_context` (name, role, company).
  - **Key dates** — e.g. “Key dates to remember: {key_dates}” (birthday, anniversary, deadlines). If empty, omit.
  - **Communication preferences** — e.g. “Communication preferences: {communication_preferences}. Follow these when replying (e.g. brief vs detailed, boundaries).” If empty, omit.
  - **Current work context** — e.g. “Current work: projects, deadlines, tasks, reminders: {current_work_context}. Use this to prioritise and suggest follow-up.” If empty, omit. **No VIP/important contacts** — we use questions on projects, deadlines, tasks, reminders only.

**Is communication preference injected into the system prompt?** Yes. **Communication preference is not a separate subsystem** — it’s stored in `user_profiles.communication_preferences`, loaded with the profile, and **injected into the system prompt** as part of `onboarding_context`. The model then follows it when replying (brief bullet points vs detailed, “never do” rules, etc.).

**Concrete flow:**
1. Webhook loads full profile (including onboarding fields) and passes them in `config["configurable"]` (e.g. `user_name`, `user_role`, `user_company`, `communication_preferences`, `key_dates`, `current_work_context`).
2. Agent reads those from config and builds a string `onboarding_context` (only the non-empty parts).
3. System prompt includes a line like: “User preferences and context:\n{onboarding_context}”
4. So every reply is conditioned on identity + key dates + communication preferences + current work context.

---

## 3. Where to Store Onboarding Data

- **Existing:** `user_profiles` (thread_id, name, role, company).
- **New fields:** Extend `user_profiles` so one place holds “who they are” and “onboarding answers.” Add:

- `key_dates` (TEXT) — free text, e.g. “Birthday 3 March; anniversary 15 June; board meeting 2nd Tuesday.”
- `communication_preferences` (TEXT) — free text; **injected into system prompt** so Jayla replies in the preferred style (brief vs detailed, “never do” rules).
- `current_work_context` (TEXT) — free text: projects, deadlines, tasks for completion, reminders (replaces VIPs/contacts).
- `onboarding_step` (INT, default 0) — 0 = not started, 1–5 = current step, 6 = done.
- `onboarding_completed_at` (TIMESTAMPTZ, nullable) — when they finished onboarding.

Migration: `4-onboarding-fields.sql` (ALTER TABLE user_profiles ADD COLUMN …).

---

## 4. Conversational Flow (Telegram)

1. **First message** (e.g. “Hi”): Jayla greets, asks Q1 (name, role, company) if not already in profile.
2. **After Q1 saved:** Ask Q2 (key dates). User can answer or “skip”.
3. **After Q2:** Q3 (communication preferences). Skip allowed.
4. **After Q3:** Q4 (current work context: projects, deadlines, tasks, reminders). Skip allowed.
5. **After Q4:** Q5 (documents intro + “upload any now?”). User can upload a file or say “later”.
6. **After Q5 (and optional upload):** Set `onboarding_step = 6`, `onboarding_completed_at = NOW()`. Jayla says “You’re all set. I’ll remember this and use your docs when you ask. What can I do for you?”

**Implementation:**  
- `user_profile.load_user_profile()` returns onboarding_step and the new fields.  
- Webhook or a small “onboarding” helper decides: if step &lt; 6 and last message was from Jayla asking a question, parse reply and save; then send next question or complete.  
- Alternatively, **let the agent drive:** system prompt says “You are in onboarding. Current step: X. Ask question X; when the user answers, say you’ve noted it and ask question X+1. Store answers in your reply so we can parse.” Parsing could be via a small LLM call (extract key_dates, etc.) or a tool the agent calls, e.g. `save_onboarding_answer(step, answer)`.

**Recommendation:** Agent-driven with a **tool** `save_onboarding_answer(step, answer)` that writes to `user_profiles`. Agent prompt: “If onboarding_step &lt; 6, ask onboarding question for that step; when user replies, call save_onboarding_answer(step, user_message) then ask next question or finish.”

---

## 5. Document Upload and RAG

**Document types we care about:**

- **Legal** — contracts, terms, NDAs.  
- **Compliance** — policies, regulatory, internal rules.  
- **Company** — org structure, key processes, “how we work.”  
- **Other** — anything the user labels as important.

**Flow:**

1. **Upload:** User sends a **document** in Telegram (e.g. PDF, DOCX).  
2. **Download:** Webhook gets file via Telegram Bot API, saves to temp or in-memory bytes.  
3. **Parse:** Use **Docling** (or fallback) to extract text from PDF/DOCX.  
4. **Chunk:** Split with RecursiveCharacterTextSplitter (or similar); chunk size ~500–1000, overlap ~100.  
5. **Embed:** sentence-transformers `all-mpnet-base-v2` (768d) — already in `documents` schema.  
6. **Store:** Insert into `documents` (user_id, content, metadata, embedding, scope, expires_at).  
   - `user_id` = same as profile (e.g. email or thread_id).  
   - `metadata` = { "source": "telegram", "filename": "...", "doc_type": "contract" | "compliance" | "company" | "other" }.  
   - **Retention:** After ingest, Jayla asks: keep **permanently** or **auto-remove after 7 days**. User replies **keep** (or **permanent**) or **week**; webhook calls `rag.update_documents_retention(inserted_ids, expires_at)` (NULL = permanent, or now+7d for auto-offload). Retrieve excludes rows where `expires_at` is past.  
7. **Retrieve:** On each user message (or when agent needs context), run `retrieve(query, user_id, limit=5)` and inject the top chunks into the system prompt or a “Document context” block.

**RAG in agent:**  
- In `agent.call_agent()`, before building the system message: get `user_id` from config, call `rag.retrieve(last_user_message_or_query, user_id, limit=5)`.  
- Append “Document context (use to ground answers):” + retrieved chunks to the system prompt.  
- So Jayla’s answers can cite contracts, compliance, company docs when relevant.

**Scope (implemented):**  
- **Phase 2 & 3 done.** `rag.ingest_document()` returns `(status, inserted_ids)`; bytes→text via Docling (when installed) or PyPDF2/docx2txt only → RecursiveCharacterTextSplitter → sentence-transformers all-mpnet-base-v2 (when installed) → Neon `documents`. Webhook handles `message.document` → download → ingest → asks "Keep permanently or auto-remove after 7 days?" (reply **keep** or **week**) → `rag.update_documents_retention(ids, expires_at)` sets retention.  
- `rag.retrieve()` runs each turn; top-k chunks (excluding expired) are injected as "Document context" in the system prompt. Optional tool `search_my_documents(query)` for explicit search.  
- **Railway (image under 4GB):** `requirements-railway.txt` omits docling and sentence-transformers. Document parse on Railway uses PyPDF2/docx2txt only; ingest returns a friendly message that embedding isn't available—add documents via CLI or local run for full RAG.

---

## 6. Implementation Phases

| Phase | What | Deliverables |
|-------|------|--------------|
| **Phase 1** | Onboarding schema + 5 questions | Migration `4-onboarding-fields.sql`; extend `user_profiles`; `user_profile.load/save` for new fields; prompts + agent logic (or tool `save_onboarding_answer`) so Jayla asks Q1–Q5 in order and marks complete. |
| **Phase 2** ✅ | Document upload + ingest | **Done.** Webhook: handle `message.document`; download file; call `rag.ingest_document(bytes_content, user_id, metadata)`. Local: Docling or PyPDF2/docx2txt → chunk → all-mpnet-base-v2 → Neon. Railway (slim): PyPDF2/docx2txt parse only; ingest returns message that embedding isn't available. |
| **Phase 3** ✅ | RAG retrieval in agent | **Done.** `rag.retrieve()` in `call_agent()`; top-k chunks as Document context in system prompt; tool `search_my_documents(query)` in `tools_custom/rag_tools.py`. |
| **Phase 4** (optional) | Onboarding UX polish | “Skip” / “Later” for each question; optional reminder to upload docs after onboarding; list of doc types (legal, compliance, company) in Q5. |

---

## 7. Summary

- **Max 5 “slots”:** (1) Name, role, company; (2) Key dates; (3) Communication preferences; (4) Current work context (projects, deadlines, tasks, reminders); (5) Documents intro + upload.  
- **System prompt injection:** All onboarding fields (communication preference, key dates, current work context) are loaded from profile, combined into an “User preferences and context” block, and **injected into the system prompt** so Jayla replies in the right style and with the right context.  
- **Storage:** Extend `user_profiles` with onboarding fields and step.  
- **Flow:** Conversational (one question at a time); agent-driven with optional tool `save_onboarding_answer`.  
- **Documents:** Upload in Telegram → parse (Docling when installed, else PyPDF2/docx2txt) → chunk → embed (when sentence-transformers available) → `documents` table; RAG retrieve in agent to power answers with legal/compliance/company content. Railway slim image: parse only; add docs via CLI/local for full RAG.  
- **Phases:** 1 = onboarding questions + schema + prompt injection; 2 = document ingest; 3 = RAG in agent; 4 = UX polish.
- **Retention and memory (§8):** Conversation persistence (Postgres checkpointer) and long-term memory writing (“remember X” → put_memory) are required so the assistant remembers past engagements and user-stated facts. See PERSONAL_ASSISTANT_PATTERNS.md and docs/WHERE_DATA_IS_STORED.md.

**Phases 2–3 (RAG):** Implemented. Next: **Postgres checkpointer + memory writing** (so the assistant remembers), then **Phase 1** (onboarding flow) or **Phase 4** (UX polish).

---

## 8. Retention and memory (assistant must remember)

An assistant that cannot remember past conversations or user-stated facts is not useful. **Retention and memory are prerequisites** for a useful PA, not optional.

| What | Where | Required for |
|------|--------|---------------|
| **Conversation persistence** | **Postgres checkpointer** (Neon) | Messages, tool calls, tool outputs persist across restarts and deploys. Without it, every restart wipes history and the assistant appears forgetful. Use `AsyncPostgresSaver` from `langgraph-checkpoint-postgres` with `DATABASE_URL`. |
| **Long-term memory writing** | **Qdrant** (read + write) | When the user says “remember X”, the graph must extract the fact and call `put_memory(store, namespace, data)` so Qdrant is populated. Currently only read (`get_memories`) is wired; without writing, `memory_context` is always empty. Implement a memory extraction node or tool (e.g. using MEMORY_ANALYSIS_PROMPT) that calls `put_memory`. |

**Implementation order:** (1) Add Postgres checkpointer so conversation history persists. (2) Add memory writing (“remember X” → extract → `put_memory`) so long-term facts are stored. See **PERSONAL_ASSISTANT_PATTERNS.md** §1.1, §2.3 and **docs/WHERE_DATA_IS_STORED.md**.
