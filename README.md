# Jayla PA

Personal assistant (PA) for **Jero** — MD of Ketchup Software Solutions. Jayla helps with Gmail, Google Calendar, projects/tasks (Neon), and optional Telegram. Built with LangGraph, Arcade, Groq/DeepSeek, Qdrant, and Neon.

See **arcade-ai-agent/PERSONAL_ASSISTANT_PATTERNS.md** for full design, patterns, and appendix.

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
- **User:** `USER_ID` (or `EMAIL`)
- **Neon:** `DATABASE_URL` (project management + RAG)
- **Qdrant:** `QDRANT_URL`, `QDRANT_API_KEY` (long-term memory)
- **Telegram (optional):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `BASE_URL`

### 3. Run SQL migrations (Neon)

With `DATABASE_URL` set in `.env` (and venv active):

```bash
python scripts/run_sql_migrations.py
```

**Note:** Migrations run `0-drop-all.sql` first (drops `public` schema CASCADE), then `0-extensions.sql`, `1-projects-tasks.sql`, `2-rag-documents.sql`. All data in `public` is wiped on each run.

### 3b. Run Qdrant init (optional, for long-term memory)

With `QDRANT_URL` and `QDRANT_API_KEY` set, create the memory collection once (idempotent):

```bash
python scripts/init_qdrant.py
```

### 4. Test connections (curl)

```bash
./scripts/test_env_connections.sh
```

---

## Running

### HTTP endpoints (webhook server)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info: `{"ok": true, "service": "jayla-pa", "webhook": "/webhook"}` |
| GET | `/health` | Health check: `{"ok": true, "status": "healthy"}` |
| POST | `/webhook` | Telegram webhook (JSON body from Telegram) |

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
├── requirements.txt  # Full deps (local dev, RAG)
├── requirements-railway.txt  # Slim deps for deploy (no torch/docling)
├── langgraph.json
├── configuration.py
├── graph.py
├── nodes.py
├── agent.py
├── tools.py
├── memory.py
├── rag.py
├── prompts.py
├── pa_cli.py
├── sql/
│   ├── 0-drop-all.sql      # Drops public schema CASCADE (run first)
│   ├── 0-extensions.sql
│   ├── 1-projects-tasks.sql
│   └── 2-rag-documents.sql
├── telegram_bot/
│   ├── client.py
│   └── webhook.py
├── tools_custom/
│   ├── project_tasks.py
│   └── gmail_attachment.py
└── scripts/
    ├── run_sql_migrations.py
    ├── init_qdrant.py      # Create Qdrant collection (idempotent)
    ├── set_telegram_webhook.py
    ├── set_railway_vars.sh # Sync .env to Railway (skips RAILWAY_TOKEN)
    ├── curl_deployed.sh   # Curl GET /, GET /health, POST /webhook (set BASE_URL)
    └── test_env_connections.sh
```

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

1. **Railway** – [railway.app](https://railway.app): New Project → Deploy from GitHub (connect `ketchupdev-prog/jayla-pa`) → Add env vars (see below). The repo includes **`railway.toml`** and a **`Dockerfile`** (Railway uses it when present). The Dockerfile installs **`requirements-railway.txt`** (slim deps: no torch/docling/sentence-transformers) for a fast build; the app starts with only FastAPI so **GET /** and **GET /health** work at once (graph loads on first webhook). Generate a domain in Settings → Networking, then in Namecheap add **CNAME** Host `jayla`, Value `yourapp.up.railway.app`. In Railway, add custom domain **`jayla.ketchup.cc`** so HTTPS works.  
   - **Sync env from local .env:** With [Railway CLI](https://docs.railway.app/develop/cli) installed and linked (`railway login`, `railway link`), run `./scripts/set_railway_vars.sh` from `jayla-pa` to set all variables from `.env` (skips `RAILWAY_TOKEN`). Then redeploy (`railway up` or push a commit).  
   - **CLI (optional):** Put `RAILWAY_TOKEN=...` in local `.env` (not committed) for `railway up`. View deploy/runtime logs: `railway logs` (from jayla-pa with project linked).
2. **Render** – [render.com](https://render.com): New → Web Service → Connect repo (jayla-pa) → Build: `pip install -r requirements.txt` (or use Dockerfile) → Start: `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` → Add env vars. Render gives you `https://yourapp.onrender.com`. In Namecheap, **CNAME** Host `jayla`, Value `yourapp.onrender.com`. Set `BASE_URL=https://jayla.ketchup.cc` and add `jayla.ketchup.cc` as custom domain in Render.

**Requirements for any host**

- **Start command:** `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` (use `$PORT` or the platform’s env).
- **Env vars:** Copy from `.env` (see `.env.example` for keys). Never commit `.env`; set them in the platform’s dashboard or use `./scripts/set_railway_vars.sh` for Railway.
- After deploy, run migrations and Qdrant init once (locally with same `DATABASE_URL` and `QDRANT_*`, or via a one-off job). Then run `python scripts/set_telegram_webhook.py` locally with `BASE_URL=https://jayla.ketchup.cc` so Telegram uses the deployed URL.

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
- **Arcade:** Invite the user in Arcade Dashboard → Projects → Members; enable Gmail (and Calendar) for the project.
- **Memory:** The graph does not pass a store into the agent by default; add a LangGraph Store or Qdrant for `memory_context`.
- **RAG:** `rag.py` is a stub; implement Docling + all-mpnet-base-v2 + Neon for document ingest and retrieval.
