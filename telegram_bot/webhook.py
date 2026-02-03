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
from langchain_core.messages import HumanMessage
from graph import build_graph
from telegram_bot.client import send_message, send_typing

graph = build_graph()

app = FastAPI()


@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if os.environ.get("TELEGRAM_WEBHOOK_SECRET") and x_telegram_bot_api_secret_token != os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
        return {"ok": False}
    body = await request.json()
    message = body.get("message", {})
    chat_id = str(message.get("chat", {}).get("id"))
    # If message.document: download → RAG ingest (§8.5a) → send "Added …" and return
    # If message.voice: STT → use transcript as text. If message.photo: VLM → "[Image: …]"
    text = message.get("text", "").strip()
    if not text:
        return {"ok": True}
    if os.environ.get("TELEGRAM_CHAT_ID") and chat_id != os.environ["TELEGRAM_CHAT_ID"]:
        return {"ok": True}
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
    return {"ok": True}
