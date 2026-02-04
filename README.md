# Jayla PA

Personal assistant (PA) that helps with Gmail, Google Calendar, projects/tasks (Neon), and optional Telegram. User identity and preferences (name, role, company, key dates, communication preferences, current work context) are stored per thread and injected into the system prompt. Built with LangGraph, Arcade, Groq/DeepSeek, Qdrant, and Neon.

**Docs in this repo:** **PERSONAL_ASSISTANT_PATTERNS.md** and **PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md** (architecture, workflows, reference code). **ONBOARDING_PLAN.md** — onboarding flow (max 5 questions + document upload for RAG).

---

## Setup

**Requires [uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`).

### 1. Virtual environment

Use **one** venv: uv’s default `.venv` (so `uv sync` and `uv run` work without warnings).

```bash
cd jayla-pa
uv venv
source .venv/bin/activate   # macOS/Linux; Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Your prompt may show `(jayla-pa)` — that’s the project name, not a separate venv. To leave the venv: `deactivate`.

Without activating: `uv run python scripts/run_sql_migrations.py`. Run all commands with this venv active (or via `uv run`).

### 2. Environment variables

Copy `.env.example` to `.env` and fill in:

- **Arcade:** `ARCADE_API_KEY`, `EMAIL`
- **LLM:** `GROQ_API_KEY` + `GROQ_MODEL` or `DEEPSEEK_API_KEY` + `LLM_MODEL`
- **User:** `USER_ID` (or `EMAIL`). Optional for CLI: `USER_NAME`, `USER_ROLE`, `USER_COMPANY`, `TIMEZONE`; in Telegram Jayla asks for name/role/company if not set and stores them (and onboarding: key dates, communication preferences, current work context) per chat in Neon.
- **Neon:** `DATABASE_URL` (project management + RAG)
- **Qdrant:** `QDRANT_URL`, `QDRANT_API_KEY` (long-term memory)
- **Brave Search (optional):** `BRAVE_API_KEY` — web search for "latest", "current", "news". Set on Railway for webhook.
- **Telegram (optional):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `BASE_URL`

### 3. Run SQL migrations (Neon)

With `DATABASE_URL` set in `.env` (and venv active):

```bash
python scripts/run_sql_migrations.py
```

**Note:** Migrations run `0-drop-all.sql` first (drops `public` schema CASCADE), then `0-extensions.sql`, `1-projects-tasks.sql`, `2-rag-documents.sql`, `3-user-profiles.sql`, `4-onboarding-fields.sql`. `5-reminders.sql` exists but is **not** run (reminders are Google Calendar only). All data in `public` is wiped on each run. The `user_profiles` table stores name, role, company, and onboarding fields (key_dates, communication_preferences, current_work_context, onboarding_step) per thread.

### 3b. Run Qdrant init (optional, for long-term memory)

With `QDRANT_URL` and `QDRANT_API_KEY` set, create the memory collection once (idempotent):

```bash
python scripts/init_qdrant.py
```

### 4. Test connections (curl)

```bash
./scripts/test_env_connections.sh
```

### 5. Test tool calls (Neon + Arcade load + graph invoke)

With `DATABASE_URL` and `EMAIL` (or `USER_ID`) set, and optionally `GROQ_API_KEY` or `DEEPSEEK_API_KEY` and `ARCADE_API_KEY`:

```bash
python scripts/test_tool_calls.py
```

Runs **[1/7]** project/task tools (Neon CRUD + cleanup), **[2/7]** Arcade tools load, **[3/7]** graph invoke ("list my projects"), **[4/7]** greeting with memory, **[5/7]** calendar auth, **[6/7]** full flow (projects + calendar + reminder + email), **[7/7]** each tool exercised (7 prompts: list_projects, list_tasks, ListCalendars, ListEvents, ListThreads, ListDraftEmails, ListLabels). Progress shows (1/7)…(7/7).

### 6. Test STT (voice → text, Groq Whisper)

With `GROQ_API_KEY` set and an audio file (wav, ogg, mp3, m4a, etc.):

```bash
python scripts/test_stt.py path/to/audio.wav
```

In Telegram, sending a **voice message** is supported: the webhook downloads the file, transcribes it with Groq Whisper (`whisper-large-v3-turbo`), and uses the transcript as the user message. See `speech_to_text.py` and `docs/STT_TTS_GROQ.md`.

---

## Running

### HTTP endpoints (webhook server)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info: `{"ok": true, "service": "jayla-pa", "webhook": "/webhook"}` |
| GET | `/health` | Health check: `{"ok": true, "status": "healthy"}` |
| POST | `/webhook` | Telegram webhook (JSON body from Telegram) |
| GET | `/cron/send-reminders` | **Deprecated.** Returns 410 Gone. Reminders are calendar-only (Google Calendar via Arcade). |

### CLI

```bash
python pa_cli.py
```

First use of Gmail or Calendar will prompt for Arcade OAuth in the terminal.

### Telegram webhook server

```bash
uvicorn telegram_bot.webhook:app --reload --host 0.0.0.0 --port 8000
```

The app starts with only FastAPI loaded; the graph and Telegram client are loaded on the first `POST /webhook` request, so **GET /** and **GET /health** respond immediately (useful for health checks and avoiding 502 on Railway).

Then set the webhook. **BASE_URL** in `.env` must be the public URL where the webhook is reachable (no trailing slash):

- **Local dev:** Use a tunnel (e.g. [ngrok](https://ngrok.com)): `ngrok http 8000` → copy the HTTPS URL (e.g. `https://abc123.ngrok.io`) into `.env` as `BASE_URL=https://abc123.ngrok.io`.
- **Deployed:** Use your domain, e.g. `BASE_URL=https://jayla.yourdomain.com`.

```bash
python scripts/set_telegram_webhook.py
```

Optional: set `TELEGRAM_WEBHOOK_SECRET` in `.env` and the script will send it so Telegram includes it in webhook requests (for verification).

### Namecheap DNS: subdomain jayla.ketchup.cc

To use **jayla.ketchup.cc** as `BASE_URL` for the Telegram webhook:

1. Log in at [Namecheap](https://www.namecheap.com) → **Domain List** → select **ketchup.cc** → **Manage**.
2. Open the **Advanced DNS** tab.
3. Add a record for the subdomain **jayla**:

   **Option A — Server has a static IP (VPS, home server):**

   | Type | Host | Value | TTL |
   |------|------|--------|-----|
   | A Record | `jayla` | `YOUR_SERVER_IP` | Automatic (or 300) |

   Replace `YOUR_SERVER_IP` with the public IP of the machine where uvicorn runs (or where nginx/reverse proxy forwards to uvicorn).

   **Option B — Using a tunnel (e.g. ngrok) or another hostname:**

   | Type | Host | Value | TTL |
   |------|------|--------|-----|
   | CNAME Record | `jayla` | `your-tunnel-host.ngrok.io` (or target hostname) | Automatic (or 300) |

   Use the hostname your tunnel or proxy gives you (no `https://`, no path).

4. Save. DNS can take a few minutes to propagate.
5. In **jayla-pa/.env** set:
   ```bash
   BASE_URL=https://jayla.ketchup.cc
   ```
6. Ensure **HTTPS** is available on jayla.ketchup.cc (Telegram requires it). Options:
   - **Reverse proxy** on the server (nginx/Caddy) with a certificate (e.g. Let’s Encrypt/Certbot), proxying to `http://127.0.0.1:8000`.
   - **Cloudflare** in front: add the domain in Cloudflare, set nameservers at Namecheap to Cloudflare’s, then use Cloudflare SSL (e.g. Full or Full (strict)) and optionally proxy to your server.
7. Run `python scripts/set_telegram_webhook.py` so the webhook URL is `https://jayla.ketchup.cc/webhook`.

---

## Project structure

```
jayla-pa/
├── .env
├── .env.example
├── README.md
├── pyproject.toml
├── railway.toml       # Railway start command (Config as Code)
├── Dockerfile        # Railway: pip install requirements-railway.txt (slim build)
├── .dockerignore     # Exclude .env, venvs, .git from image
├── requirements.txt  # Full deps (local dev, RAG: docling + sentence-transformers)
├── requirements-railway.txt  # Slim deps for deploy (<4GB image; no torch/docling/sentence-transformers)
├── langgraph.json
├── configuration.py
├── graph.py
├── nodes.py
├── agent.py
├── tools.py
├── memory.py
├── rag.py                  # Ingest: bytes→text (Docling or PyPDF2/docx2txt) → split → embed (when available) → Neon; retrieve
├── prompts.py
├── pa_cli.py
├── speech_to_text.py       # STT (Groq Whisper) for voice messages
├── user_profile.py         # Load/save profile + onboarding per thread (Neon)
├── docs/
│   └── STT_TTS_GROQ.md
├── ONBOARDING_PLAN.md      # Onboarding flow (5 questions + doc upload)
├── PERSONAL_ASSISTANT_PATTERNS.md
├── PERSONAL_ASSISTANT_PATTERNS_APPENDIX.md
├── sql/
│   ├── 0-drop-all.sql      # Drops public schema CASCADE (run first)
│   ├── 0-extensions.sql
│   ├── 1-projects-tasks.sql
│   ├── 2-rag-documents.sql
│   ├── 3-user-profiles.sql # user_profiles(thread_id, name, role, company)
│   ├── 4-onboarding-fields.sql  # key_dates, communication_preferences, current_work_context, onboarding_step
│   └── 5-reminders.sql     # Optional; reminders are calendar-only (Arcade), not run by migrations
├── telegram_bot/
│   ├── client.py
│   └── webhook.py
├── tools_custom/
│   ├── project_tasks.py
│   ├── rag_tools.py       # search_my_documents, suggest_email_body_from_context (RAG)
│   ├── brave_tools.py     # search_web (Brave API; optional BRAVE_API_KEY)
│   └── gmail_attachment.py
└── scripts/
    ├── run_sql_migrations.py
    ├── init_qdrant.py      # Create Qdrant collection (idempotent)
    ├── set_telegram_webhook.py
    ├── set_railway_vars.sh # Sync .env to Railway (skips RAILWAY_TOKEN)
    ├── curl_deployed.sh   # Curl GET /, GET /health, POST /webhook (set BASE_URL)
    ├── ensure_cron_secret.sh  # Optional; cron deprecated (reminders = calendar only)
    ├── list_tools.py      # List agent tools (Arcade + project + RAG)
    ├── test_env_connections.sh
    ├── test_stt.py        # Test Groq Whisper STT (voice → text)
    ├── test_tool_calls.py # Test project/task tools, Arcade load (reminders=calendar), graph invoke
    └── test_webhook_local.py # POST simulated Telegram update to local /webhook (TELEGRAM_CHAT_ID in .env; reminders=calendar)
```

---

## Tools and imports verification

**Tool list (what the agent can call)**

| Source | Tools |
|--------|--------|
| **Arcade** (Gmail, Google Calendar) | All Gmail and Calendar tools from Arcade (list/send/delete emails, list/create/update events, etc.). Require `ARCADE_API_KEY` and user auth. |
| **Custom** (`tools_custom/project_tasks.py`) | `list_projects`, `create_project`, `delete_project`, `list_tasks`, `create_task_in_project`, `update_task`, `get_task`, `delete_task`. Require `DATABASE_URL` (Neon/Postgres) and migrations run. |
| **RAG** (`tools_custom/rag_tools.py`) | `search_my_documents(query)` — explicit search over uploaded documents. RAG retrieval also runs each turn and injects "Document context" into the system prompt. |
| **Reminders** | Calendar only. "Remind me to X at Y" → Google Calendar event (GoogleCalendar_CreateEvent). No separate reminder DB. |

**Imports and packages (webhook / Railway)**

- `graph.py` → `agent`, `nodes`, `langgraph` (MemorySaver, StateGraph, etc.), `langgraph.prebuilt` (ToolNode)
- `agent.py` → `tools.get_tools_for_model`, `memory`, `prompts`, `langchain_core`, `langchain_groq`, optional `langchain_deepseek`
- `nodes.py` → `tools.get_manager`, `langchain_core`, `langgraph.graph`
- `tools.py` → `langchain_arcade.ToolManager`, `langgraph.prebuilt.ToolNode`, `tools_custom.project_tasks.get_project_tools`, `tools_custom.rag_tools.get_rag_tools`
- `tools_custom/project_tasks.py` → `langchain_core.tools.tool`, optional `psycopg2`
- `tools_custom/rag_tools.py` → `rag.retrieve`, `langchain_core.tools.tool`

**requirements-railway.txt** keeps the image under 4GB: no docling, no sentence-transformers (no torch). Document parse on Railway uses PyPDF2 + docx2txt only; ingest returns a friendly message that embedding isn't available (add docs via CLI or local). Includes: `langgraph`, `langchain-core`, `langchain-groq`, `langchain-deepseek`, `langchain-arcade==1.3.1`, `langchain-community`, `qdrant-client`, `python-dotenv`, `fastapi`, `uvicorn`, `python-telegram-bot`, `httpx`, `psycopg2-binary`, `langchain-text-splitters`, `PyPDF2`, `docx2txt`. See `constraints-railway.txt` (pins `langchain-arcade==1.3.1`).

**Quick import check** (from repo root with venv active):

```bash
cd jayla-pa && python3 -c "
from tools_custom.project_tasks import get_project_tools
print('Project tools:', [t.name for t in get_project_tools()])
from graph import build_graph
print('Graph build: ok')
"
```

### Tests

Unit tests run with mocks (no DB/LLM required). Integration tests use the real DB when `DATABASE_URL` is set:

```bash
cd jayla-pa
pytest tests/ -v
```

- **Without `DATABASE_URL`:** All unit tests run; `test_retrieve_with_real_db` is skipped.
- **With `DATABASE_URL`:** Same plus integration test `test_retrieve_with_real_db` runs against Neon/Postgres (returns list; may be empty if no documents).

---

## Deployment

For the **Telegram webhook** you need a long-running HTTPS endpoint. Recommended options:

| Option | Best for | HTTPS | Custom domain (jayla.ketchup.cc) |
|--------|----------|--------|-----------------------------------|
| **Railway** | Easiest: connect repo, set env, deploy | Yes (auto) | CNAME `jayla` → `yourapp.up.railway.app` |
| **Render** | Free tier, Python web service | Yes (auto) | CNAME `jayla` → `yourapp.onrender.com` |
| **Fly.io** | Global, Docker or Dockerfile | Yes (auto) | CNAME or A record (see fly.io docs) |
| **VPS** (e.g. DigitalOcean, Linode) | Full control, same box as other ketchup services | nginx/Caddy + Let’s Encrypt | A record `jayla` → server IP |

**Recommended: Railway or Render**

1. **Railway** – [railway.app](https://railway.app): New Project → Deploy from GitHub (connect `ketchupdev-prog/jayla-pa`) → Add env vars (see below). The repo includes **`railway.toml`** and a **`Dockerfile`** (Railway uses it when present). The Dockerfile installs **`requirements-railway.txt`** (slim deps: no torch/docling/sentence-transformers) so the image stays **under 4GB** (Railway limit). Document upload in Telegram works (parse via PyPDF2/docx2txt) but ingest returns a message that embedding isn't available on this server—add documents via CLI or local run for full RAG. The app starts with only FastAPI so **GET /** and **GET /health** work at once (graph loads on first webhook). Generate a domain in Settings → Networking, then in Namecheap add **CNAME** Host `jayla`, Value `yourapp.up.railway.app`. In Railway, add custom domain **`jayla.ketchup.cc`** so HTTPS works.  
   - **Set BRAVE_API_KEY on Railway:** For web search in Telegram ("find out about X on the internet"), you **must** set **`BRAVE_API_KEY`** in Railway. Railway dashboard → your service → **Variables** → Add variable: `BRAVE_API_KEY` = your key from [brave.com/search/api](https://brave.com/search/api). If you use `./scripts/set_railway_vars.sh`, add `BRAVE_API_KEY=...` to your local `.env` first so the script syncs it. Without `BRAVE_API_KEY`, the agent will say it doesn't have web search.  
   - **Sync env from local .env:** With [Railway CLI](https://docs.railway.app/develop/cli) installed and linked (`railway login`, `railway link`), run `./scripts/set_railway_vars.sh` from `jayla-pa` to set all variables from `.env` (skips `RAILWAY_TOKEN`). Then redeploy (`railway up` or push a commit).  
   - **CLI (optional):** Put `RAILWAY_TOKEN=...` in local `.env` (not committed) for `railway up`. View deploy/runtime logs: `railway logs` (from jayla-pa with project linked).
2. **Render** – [render.com](https://render.com): New → Web Service → Connect repo (jayla-pa) → Build: `pip install -r requirements.txt` (or use Dockerfile) → Start: `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` → Add env vars. Render gives you `https://yourapp.onrender.com`. In Namecheap, **CNAME** Host `jayla`, Value `yourapp.onrender.com`. Set `BASE_URL=https://jayla.ketchup.cc` and add `jayla.ketchup.cc` as custom domain in Render.

**Requirements for any host**

- **Start command:** `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` (use `$PORT` or the platform’s env).
- **Env vars:** Copy from `.env` (see `.env.example` for keys). Never commit `.env`; set them in the platform’s dashboard or use `./scripts/set_railway_vars.sh` for Railway. **Web search in Telegram:** You must set **`BRAVE_API_KEY`** on Railway (Variables in the dashboard, or in `.env` before running `set_railway_vars.sh`). Without it, the agent will not have the `search_web` tool and will say it doesn’t have web search—queries like “find out about X” or “search the internet” will not work until the key is set and the app is redeployed.
- After deploy, run migrations and Qdrant init once (locally with same `DATABASE_URL` and `QDRANT_*`, or via a one-off job). Then run `python scripts/set_telegram_webhook.py` locally with `BASE_URL=https://jayla.ketchup.cc` so Telegram uses the deployed URL.

**Reminders** – Reminders are Google Calendar events only. Jayla uses GoogleCalendar_CreateEvent for "remind me to X at Y"; no separate reminder DB or cron.

**Verify deployed app**

- **GET /** and **GET /health** return `{"ok": true, ...}` when the app is up.
- From the repo: `BASE_URL=https://jayla.ketchup.cc ./scripts/curl_deployed.sh` (or use your Railway-generated URL). Or run: `curl -s https://jayla.ketchup.cc/` and `curl -s https://jayla.ketchup.cc/health`.

**Troubleshooting 502 "Application failed to respond" (Railway)**

Railway returns 502 when its edge proxy cannot reach your app. Per [Railway’s docs](https://docs.railway.com/reference/errors/application-failed-to-respond):

1. **App must listen on `0.0.0.0` and the `PORT` env var** – The Dockerfile already uses `uvicorn ... --host 0.0.0.0 --port ${PORT:-8000}`. Do not set a custom `PORT` in Railway variables unless you need a fixed port; leave it unset so Railway injects it.
2. **Target port** – In Railway → your service → **Settings** → **Networking** → **Public Networking**, ensure the domain’s **target port** matches the port your app listens on (or leave it unset so Railway auto-detects).
3. **Check deployment logs** – Railway → **Deployments** → latest deployment → **View logs**. Look for Python tracebacks, `ModuleNotFoundError`, or `KeyError` (e.g. missing env var). The app defers loading the graph and Telegram until the first `/webhook`, so **GET /** and **GET /health** should work as soon as the process is up; if you still see 502, the process is likely crashing before binding (logs will show why).
4. **Remove conflicting config** – If you use the repo’s Dockerfile, do **not** set `startCommand` in `railway.toml` (or the dashboard). Railway runs that command without a shell, so `$PORT` is not expanded and uvicorn gets the literal `$PORT` → "Invalid value for '--port'". The repo’s `railway.toml` leaves `startCommand` unset so the Dockerfile CMD runs (it uses `sh -c` and expands `$PORT`). Remove any Procfile or `railway.json` start command that might override the Dockerfile CMD.

**Deploy failed (build or runtime)**

1. **Paste the exact error** – In Railway: **Deployments** → failed deployment → **Build** tab (for build failures) or **Deploy** tab (for runtime). Copy the last 30–50 lines and share them so we can target the fix.
2. **Build failing** – Check that the log says it’s using the **Dockerfile** (e.g. “Building with Dockerfile” or “DOCKERFILE builder”). If it says Nixpacks or Railpack, set **Settings** → **Build** → Builder to **Dockerfile**, or ensure `railway.toml` has `[build]` and `builder = "DOCKERFILE"`. If `pip install` fails, the log will show the failing package (e.g. missing system lib or network).
3. **Runtime failing** – Deploy logs may show `ModuleNotFoundError`, `ImportError`, or `KeyError` (missing env). Set all required env vars in Railway (see `.env.example`). The app does not read `.env` in the image; Railway injects variables at runtime.
4. **Root Directory** – If the GitHub repo is the **whole monorepo** (e.g. `ai-agent-mastery-main`), set Railway **Settings** → **General** → **Root Directory** to `jayla-pa` so the Dockerfile at `jayla-pa/Dockerfile` is used. If the repo is **only** `jayla-pa`, leave Root Directory empty.

---

## Quick start

```bash
cd jayla-pa
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
# copy .env.example to .env and set DATABASE_URL, ARCADE_API_KEY, QDRANT_URL, etc.
python scripts/run_sql_migrations.py
python scripts/init_qdrant.py   # optional: Qdrant memory collection
python pa_cli.py
```

---

## Notes

- **Startup:** The webhook app loads only FastAPI at startup; the graph and Telegram client are loaded on the first `POST /webhook`. This keeps **GET /** and **GET /health** working even if env vars for Arcade/LLM/Telegram are missing or misconfigured (only the first webhook request would fail).
- **User profiles & onboarding:** Profile (name, role, company) and onboarding (key_dates, communication_preferences, current_work_context) are loaded per thread and **injected into the system prompt** so Jayla replies in the user’s preferred style and uses projects/deadlines/tasks/reminders. See ONBOARDING_PLAN.md.
- **Custom tools (project/task):** Arcade’s manager only knows Gmail/Calendar tools; `nodes.should_continue` and `authorize` skip auth for custom tools (e.g. list_projects) so the graph runs them via the prebuilt ToolNode.
- **Arcade (Gmail / Calendar):** Google Calendar authorization is the same as Gmail: **authorize first, then continue.** Both use Arcade’s `manager.authorize(tool_name, user_id)`; one flow for all Arcade tools. User must open the auth link (Google OAuth), complete it, then ask again. Invite the user in Arcade Dashboard → Projects → Members; enable Gmail and Calendar for the project. For Telegram (and other webhooks), set `PA_AUTH_NONBLOCK=1` so the bot sends the auth link in the reply instead of blocking; user authorizes, then asks again and tools run.
- **Memory:** When `QDRANT_URL` (and optionally `QDRANT_API_KEY`) is set, the webhook and CLI pass a Qdrant-backed memory store in `config["configurable"]["store"]`. The agent searches it by the last user message and injects `memory_context` into the system prompt so Jayla can use stored facts. Run `python scripts/init_qdrant.py` once. Memory writing (e.g. when the user says "remember X") is not yet in the graph—add memories via script or implement MEMORY_ANALYSIS_PROMPT + put_memory in the flow.
- **RAG:** Document ingest and retrieval are implemented (ONBOARDING_PLAN.md Phase 2–3). **Local/CLI (full deps):** Send a PDF/DOCX as a Telegram document → webhook downloads and calls `rag.ingest_document()` (bytes→text via Docling or PyPDF2/docx2txt → RecursiveCharacterTextSplitter → sentence-transformers all-mpnet-base-v2 → Neon `documents`). **Railway (slim image, under 4GB):** Parse uses PyPDF2/docx2txt only; embedding is not available, so ingest returns a friendly message—add documents via CLI or local for full RAG. After ingest (when embedding is available), Jayla asks whether to **keep the document permanently** or **auto-remove after 7 days**; reply **keep** (or **permanent**) for permanent, **week** for auto-offload. `rag.update_documents_retention(ids, expires_at)` sets `expires_at` (NULL = permanent). On each turn, `rag.retrieve()` runs over the last user message and the top-k chunks are injected as "Document context" in the system prompt. Tool `search_my_documents(query)` in `tools_custom/rag_tools.py` lets the user explicitly search uploaded docs.
- **Date/time:** The agent receives full datetime context (weekday, month, year, today, tomorrow, current time in `TIMEZONE`) in the system prompt so "today", "tomorrow", and "now" are never guessed (e.g. no January 1). Set `TIMEZONE` in `.env` (e.g. `Africa/Windhoek`) for correct calendar/reminder times.
