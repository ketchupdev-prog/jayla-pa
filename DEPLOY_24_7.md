# Host Jayla PA 24/7 (Without Your Computer)

Jayla needs a **long‑running HTTPS server** for the Telegram webhook. Use one of these so it runs without your machine.

---

## Option A: Railway (Recommended)

**Best for:** Easiest setup, auto HTTPS, custom domain support.  
**Cost:** Free tier (~$5 credit/month); paid after that.

### 1. Push code to GitHub

- If `jayla-pa` lives inside a monorepo (e.g. `ai-agent-mastery-main`), push that repo.
- If you have a **standalone** `jayla-pa` repo, push that.

### 2. Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in (GitHub).
2. **New Project** → **Deploy from GitHub repo**.
3. Select the repo that contains `jayla-pa`.
4. **Settings** → **General** → set **Root Directory** to `jayla-pa` (only if the repo is the monorepo; if the repo is just jayla-pa, leave this empty).

### 3. Use the Dockerfile

- Railway will detect `jayla-pa/Dockerfile` and use it (see `railway.toml`).
- No need to set a custom start command; the Dockerfile CMD is used.

### 4. Set environment variables

In Railway: your service → **Variables** → add every variable from your local `.env` (see `.env.example`).  
**Do not** set `RAILWAY_TOKEN` or `PORT` (Railway sets `PORT`).

**Required for Telegram + web search:**

- `BASE_URL` = your public URL (e.g. `https://your-app.up.railway.app` — you get this in step 5).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `DATABASE_URL` (Neon)
- `GROQ_API_KEY` (and optionally `GROQ_VISION_MODEL` for photos)
- `ARCADE_API_KEY`, `EMAIL` (for Gmail/Calendar)
- `BRAVE_API_KEY` (for web search in Telegram)
- `QDRANT_URL` (and `QDRANT_API_KEY` if needed)

**Optional:** With [Railway CLI](https://docs.railway.app/develop/cli) installed and linked (`railway login`, `railway link`), from `jayla-pa` run:

```bash
./scripts/set_railway_vars.sh
```

That copies variables from `.env` into Railway (skips `RAILWAY_TOKEN`).

### 5. Get a public URL

- **Settings** → **Networking** → **Generate Domain**.
- You’ll get something like `your-app.up.railway.app`.
- In **Variables**, set `BASE_URL=https://your-app.up.railway.app` (no trailing slash).

### 6. Deploy and set Telegram webhook

- Trigger a deploy (push a commit or **Redeploy** in Railway).
- After it’s healthy, on your machine (with the same `BASE_URL` in `.env`):

```bash
cd jayla-pa
# In .env: BASE_URL=https://your-app.up.railway.app
python scripts/set_telegram_webhook.py
```

- Check: `curl -s https://your-app.up.railway.app/` and `curl -s https://your-app.up.railway.app/health` should return `{"ok": true, ...}`.

### 7. (Optional) Custom domain (e.g. jayla.ketchup.cc)

- In Railway: **Settings** → **Networking** → **Custom Domain** → add `jayla.ketchup.cc`.
- In your DNS (e.g. Namecheap): add **CNAME** `jayla` → `your-app.up.railway.app`.
- Set `BASE_URL=https://jayla.ketchup.cc` in Railway variables and in local `.env`, then run `python scripts/set_telegram_webhook.py` again.

---

## Option B: Render (Free tier)

**Best for:** Free tier; app may spin down after inactivity (wake-up delay on first message).  
**Cost:** Free tier available.

### 1. Push code to GitHub

Same as Railway: push the repo that contains `jayla-pa` (monorepo or standalone).

### 2. Create a Web Service on Render

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New** → **Web Service**.
3. Connect the repo; select the branch.
4. **Root Directory:** set to `jayla-pa` if the repo is a monorepo; otherwise leave empty.

### 3. Build & start

- **Build Command:**  
  `pip install -r requirements-railway.txt -c constraints-railway.txt`  
  Or use **Docker** and leave Render to use `jayla-pa/Dockerfile` (set Docker path to `jayla-pa` if monorepo).
- **Start Command:**  
  `uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port $PORT`

### 4. Environment variables

In **Environment** add the same variables as in `.env` (see Option A step 4). Set `BASE_URL` after you get the Render URL (e.g. `https://jayla-pa.onrender.com`).

### 5. Deploy and webhook

- Deploy; copy the service URL.
- Set `BASE_URL` in Render env and locally, then run:

```bash
python scripts/set_telegram_webhook.py
```

**Note:** On free tier, the service may sleep; the first Telegram message after idle can be slow while it starts.

---

## After deployment (any platform)

1. **Migrations:** Run once (same `DATABASE_URL` as production):  
   `python scripts/run_sql_migrations.py`
2. **Qdrant:** Run once if you use memory:  
   `python scripts/init_qdrant.py`
3. **Webhook:** Always re-run after changing `BASE_URL`:  
   `python scripts/set_telegram_webhook.py`

---

## Quick comparison

|                | Railway              | Render (free)        |
|----------------|----------------------|----------------------|
| Always on      | Yes (on paid usage)  | Spins down when idle |
| HTTPS          | Yes                  | Yes                  |
| Custom domain  | Yes                  | Yes                  |
| Easiest config | Yes (Dockerfile)     | Yes                  |

For “runs without my computer” and no cold starts, **Railway** is the better fit. Use **Render** if you want minimal cost and can accept a short delay when the app was idle.

---

## Troubleshooting: "Something went wrong on the connection" (Telegram)

This message appears when the agent hits an SSL/connection-style error. Two common causes:

1. **Telegram's 60s webhook timeout** – If the app took too long to reply, Telegram closed the connection. The webhook now **returns 200 immediately** and runs the agent in the background, so this should stop. Redeploy the latest code.
2. **Real SSL/DB/API error** – In **Railway → Deployments → latest deploy → View logs**, look for `[webhook] ERROR type=... message=...` and the traceback above it. Fix the underlying issue (e.g. missing env var, Neon connection, Arcade/Groq timeout).
