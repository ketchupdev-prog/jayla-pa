# Telegram webhook handler. See PERSONAL_ASSISTANT_PATTERNS.md C.8, §6.6, §8.5a.

import os

# Load .env from project root so ARCADE_API_KEY etc. are set before graph/tools import
_webhook_dir = os.path.dirname(os.path.abspath(__file__))
_pa_root = os.path.dirname(_webhook_dir)
_env_path = os.path.join(_pa_root, ".env")
if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)

from fastapi import FastAPI, Request, Header

app = FastAPI()

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from graph import build_graph
        _graph = build_graph()
    return _graph


@app.get("/")
async def root():
    return {"ok": True, "service": "jayla-pa", "webhook": "/webhook"}


@app.get("/health")
async def health():
    return {"ok": True, "status": "healthy"}


@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")):
    # Reject only if we set a secret AND Telegram sent a different one (allow missing header for backward compat)
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if secret and x_telegram_bot_api_secret_token is not None and x_telegram_bot_api_secret_token != secret:
        return {"ok": False}
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    # Support message or edited_message
    message = body.get("message") or body.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    # If message.document: download → RAG ingest (§8.5a) → send "Added …" and return
    # If message.voice: STT → use transcript as text. If message.photo: VLM → "[Image: …]"
    text = (message.get("text") or "").strip()
    if not text:
        return {"ok": True}
    allowed_chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if allowed_chat and chat_id != allowed_chat:
        print(f"[webhook] Skipping: chat_id {chat_id} != TELEGRAM_CHAT_ID {allowed_chat}", flush=True)
        return {"ok": True}
    print(f"[webhook] Processing from chat_id={chat_id} text={text[:50]!r}...", flush=True)
    try:
        from langchain_core.messages import HumanMessage
        from telegram_bot.client import send_message, send_typing
        graph = _get_graph()
        config = {"configurable": {"thread_id": chat_id, "user_id": os.environ.get("EMAIL", "")}}
        inputs = {"messages": [HumanMessage(content=text)]}
        await send_typing(chat_id=chat_id)
        result = await graph.ainvoke(inputs, config=config)
        messages = result.get("messages", [])
        reply = ""
        for m in reversed(messages):
            if hasattr(m, "content") and m.content and getattr(m, "type", None) == "ai":
                reply = m.content if isinstance(m.content, str) else str(m.content)
                break
        if reply:
            await send_message(reply, chat_id=chat_id)
            print(f"[webhook] Sent reply to chat_id={chat_id}", flush=True)
        else:
            print(f"[webhook] No AI reply in result for chat_id={chat_id}", flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            from telegram_bot.client import send_message
            await send_message(f"Sorry, something went wrong: {str(e)[:200]}", chat_id=chat_id)
            print(f"[webhook] Sent error message to chat_id={chat_id}", flush=True)
        except Exception as e2:
            print(f"[webhook] Failed to send error to user: {e2}", flush=True)
    return {"ok": True}
