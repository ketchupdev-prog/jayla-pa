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
from fastapi.responses import JSONResponse

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


@app.get("/cron/send-reminders")
async def cron_send_reminders(
    secret: str | None = None,
    x_cron_secret: str | None = Header(None, alias="X-Cron-Secret"),
):
    """Proactive reminder delivery. Call periodically (e.g. every 1–5 min) from a cron job.
    Requires CRON_SECRET in query ?secret=... or header X-Cron-Secret."""
    cron_secret = (os.environ.get("CRON_SECRET") or "").strip()
    if not cron_secret:
        return JSONResponse({"ok": False, "error": "CRON_SECRET not configured"}, status_code=503)
    provided = (secret or "") or (x_cron_secret or "")
    if provided != cron_secret:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    user_id = (os.environ.get("EMAIL") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not user_id or not chat_id:
        return JSONResponse({"ok": False, "error": "EMAIL and TELEGRAM_CHAT_ID required"}, status_code=400)
    try:
        from tools_custom.reminders import get_due_reminders, mark_reminders_sent
        from telegram_bot.client import send_message
        due = get_due_reminders(user_id)
        sent_ids = []
        for _id, msg in due:
            await send_message(f"⏰ Reminder: {msg}", chat_id=chat_id)
            sent_ids.append(_id)
        if sent_ids:
            mark_reminders_sent(sent_ids)
        return {"ok": True, "sent": len(sent_ids)}
    except Exception as e:
        print(f"[cron] send-reminders error: {e}", flush=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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
    # If message.voice / message.audio: download → STT → use transcript as text
    text = (message.get("text") or "").strip()
    if not text and (message.get("voice") or message.get("audio")):
        voice = message.get("voice") or message.get("audio") or {}
        file_id = voice.get("file_id")
        if file_id:
            try:
                from telegram_bot.client import get_bot
                import tempfile
                bot = get_bot()
                tg_file = await bot.get_file(file_id)
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                    tmp.close()
                    await tg_file.download_to_drive(tmp.name)
                    with open(tmp.name, "rb") as f:
                        audio_bytes = f.read()
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass
                from speech_to_text import transcribe_async
                text = (await transcribe_async(audio_bytes)).strip()
                if text:
                    print(f"[webhook] STT transcript for chat_id={chat_id}: {text[:60]!r}...", flush=True)
            except Exception as stt_err:
                import traceback
                traceback.print_exc()
                print(f"[webhook] STT failed for chat_id={chat_id}: {stt_err}", flush=True)
                try:
                    from telegram_bot.client import send_message
                    await send_message("I couldn't transcribe that voice message. Please try again or send text.", chat_id=chat_id)
                except Exception:
                    pass
                return {"ok": True}
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
        from user_profile import load_user_profile, save_user_profile, extract_profile_from_message
        profile = load_user_profile(chat_id)
        config = {
            "configurable": {
                "thread_id": chat_id,
                "user_id": os.environ.get("EMAIL", ""),
                "user_name": profile.get("name", ""),
                "user_role": profile.get("role", ""),
                "user_company": profile.get("company", ""),
                "key_dates": profile.get("key_dates", ""),
                "communication_preferences": profile.get("communication_preferences", ""),
                "current_work_context": profile.get("current_work_context", ""),
                "onboarding_step": profile.get("onboarding_step", 0),
            }
        }
        graph = _get_graph()
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
        # If we had no profile and the user might have introduced themselves, try to extract and save
        if not (profile.get("name") or profile.get("role") or profile.get("company")):
            extracted = extract_profile_from_message(text)
            if extracted and (extracted.get("name") or extracted.get("role") or extracted.get("company")):
                save_user_profile(chat_id, **extracted)
                print(f"[webhook] Saved user profile for chat_id={chat_id}", flush=True)
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
