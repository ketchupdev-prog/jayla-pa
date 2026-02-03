# Jayla PA

Personal assistant (PA) for **Jero** — MD of Ketchup Software Solutions. Jayla helps with Gmail, Google Calendar, projects/tasks (Neon), and optional Telegram. Built with LangGraph, Arcade, Groq/DeepSeek, Qdrant, and Neon.

See **arcade-ai-agent/PERSONAL_ASSISTANT_PATTERNS.md** for full design, patterns, and appendix.

---

## Setup

**Requires [uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`).

### 1. Virtual environment (jayla)

Create and use the **jayla** venv only (no `.venv`):

```bash
cd jayla-pa
uv venv jayla
source jayla/bin/activate   # macOS/Linux; Windows: jayla\Scripts\activate
uv pip install -r requirements.txt
```

Then run all commands with this venv active (e.g. `python scripts/run_sql_migrations.py`).

### 2. Environment variables

Copy `.env.example` to `.env` and fill in:

- **Arcade:** `ARCADE_API_KEY`, `EMAIL`
- **LLM:** `GROQ_API_KEY` + `GROQ_MODEL` or `DEEPSEEK_API_KEY` + `LLM_MODEL`
- **User:** `USER_ID` (or `EMAIL`)
- **Neon:** `DATABASE_URL` (project management + RAG)
- **Qdrant:** `QDRANT_URL`, `QDRANT_API_KEY` (long-term memory)
- **Telegram (optional):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `BASE_URL`

### 3. Run SQL migrations (Neon)

With `DATABASE_URL` set in `.env` (and **jayla** venv active):

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

### CLI

```bash
python pa_cli.py
```

First use of Gmail or Calendar will prompt for Arcade OAuth in the terminal.

### Telegram webhook server

```bash
uvicorn telegram_bot.webhook:app --reload --host 0.0.0.0 --port 8000
```

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
├── requirements.txt
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

1. **Railway** – [railway.app](https://railway.app): New Project → Deploy from GitHub (jayla-pa repo) → Add env vars (same as `.env`) → Settings → Generate domain (e.g. `jayla-pa-production.up.railway.app`) → In Namecheap, add **CNAME** Host `jayla`, Value `jayla-pa-production.up.railway.app` → In Railway, add custom domain `jayla.ketchup.cc` if supported, or use the Railway URL as `BASE_URL`. Start command: `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT`.
2. **Render** – [render.com](https://render.com): New → Web Service → Connect repo (jayla-pa) → Build: `pip install -r requirements.txt` (or use Dockerfile) → Start: `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` → Add env vars. Render gives you `https://yourapp.onrender.com`. In Namecheap, **CNAME** Host `jayla`, Value `yourapp.onrender.com`. Set `BASE_URL=https://jayla.ketchup.cc` and add `jayla.ketchup.cc` as custom domain in Render.

**Requirements for any host**

- **Start command:** `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT` (use `$PORT` or the platform’s env, e.g. Render uses `PORT`).
- **Env vars:** Copy from `.env` (e.g. `ARCADE_API_KEY`, `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `TELEGRAM_BOT_TOKEN`, `BASE_URL=https://jayla.ketchup.cc`, etc.). Never commit `.env`; set them in the platform’s dashboard.
- After deploy, run migrations and Qdrant init once (e.g. locally with same `DATABASE_URL` and `QDRANT_*`, or via a one-off job on the platform). Then run `python scripts/set_telegram_webhook.py` locally with `BASE_URL=https://jayla.ketchup.cc` so Telegram uses the deployed URL.

---

## Quick start

```bash
cd jayla-pa
uv venv jayla && source jayla/bin/activate
uv pip install -r requirements.txt
# copy .env.example to .env and set DATABASE_URL, ARCADE_API_KEY, QDRANT_URL, etc.
python scripts/run_sql_migrations.py
python scripts/init_qdrant.py   # optional: Qdrant memory collection
python pa_cli.py
```

---

## Notes

- **Arcade:** Invite the user in Arcade Dashboard → Projects → Members; enable Gmail (and Calendar) for the project.
- **Memory:** The graph does not pass a store into the agent by default; add a LangGraph Store or Qdrant for `memory_context`.
- **RAG:** `rag.py` is a stub; implement Docling + all-mpnet-base-v2 + Neon for document ingest and retrieval.
