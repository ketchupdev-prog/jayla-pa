# Telegram webhook handler. See PERSONAL_ASSISTANT_PATTERNS.md C.8, §6.6, §8.5a.
# Production: Postgres checkpointer (DATABASE_URL) so conversation history persists across restarts.

import os
import tempfile
from contextlib import asynccontextmanager

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

# chat_id -> list of document row ids awaiting retention choice (keep permanent vs auto-offload after 1 week)
_pending_retention: dict[str, list[int]] = {}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Production: use Postgres checkpointer when DATABASE_URL is set so conversation history persists."""
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if db_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
                await checkpointer.setup()
                from graph import build_graph
                app.state.graph = build_graph(checkpointer)
                print("[webhook] Using Postgres checkpointer (conversation history persists).", flush=True)
                yield
        except Exception as e:
            print(f"[webhook] Postgres checkpointer failed, using MemorySaver: {e}", flush=True)
            from graph import build_graph
            app.state.graph = build_graph()
            yield
    else:
        from graph import build_graph
        app.state.graph = build_graph()
        print("[webhook] DATABASE_URL not set; using MemorySaver (conversation history in-memory only).", flush=True)
        yield


app = FastAPI(lifespan=_lifespan)


def _get_graph():
    return getattr(app.state, "graph", None) or _build_graph_fallback()


def _build_graph_fallback():
    from graph import build_graph
    return build_graph()


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
    """Reminders are calendar-only (Google Calendar via Arcade). This endpoint is deprecated.
    Return 410 Gone so cron jobs can be updated. Use GoogleCalendar_ListEvents for due events."""
    return JSONResponse(
        {
            "ok": False,
            "error": "Reminders are calendar-only. Use Google Calendar (Arcade); this cron endpoint is deprecated.",
        },
        status_code=410,
    )


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
    doc = message.get("document") or {}
    if doc.get("file_id"):
        try:
            from telegram_bot.client import get_bot, send_message
            bot = get_bot()
            tg_file = await bot.get_file(doc["file_id"])
            with tempfile.NamedTemporaryFile(suffix="", delete=False) as tmp:
                tmp.close()
                await tg_file.download_to_drive(tmp.name)
                with open(tmp.name, "rb") as f:
                    doc_bytes = f.read()
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
            filename = doc.get("file_name") or "document"
            user_id = os.environ.get("EMAIL", "") or chat_id
            from rag import ingest_document
            status, inserted_ids = ingest_document(
                bytes_content=doc_bytes,
                user_id=user_id,
                metadata={"source": "telegram", "filename": filename, "doc_type": "other"},
            )
            if inserted_ids:
                _pending_retention[chat_id] = inserted_ids
                await send_message(
                    f"✓ {status}\n\nKeep this document permanently or auto-remove after a week? Reply **keep** for permanent, **week** for auto-remove after 7 days.",
                    chat_id=chat_id,
                )
            else:
                await send_message(f"✓ {status}" if status.startswith("Added") else status, chat_id=chat_id)
            print(f"[webhook] RAG ingest for chat_id={chat_id} file={filename}: {status}", flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                from telegram_bot.client import send_message
                await send_message(f"I couldn't add that document: {str(e)[:200]}", chat_id=chat_id)
            except Exception:
                pass
        return {"ok": True}
    # If message.voice / message.audio: download → STT → use transcript as text
    text = (message.get("text") or "").strip()
    if not text and (message.get("voice") or message.get("audio")):
        voice = message.get("voice") or message.get("audio") or {}
        file_id = voice.get("file_id")
        if file_id:
            try:
                from telegram_bot.client import get_bot
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
    # Handle retention choice after document upload (keep permanent vs auto-offload after 1 week)
    if chat_id in _pending_retention:
        raw_lower = text.strip().lower()
        if raw_lower in ("keep", "permanent", "p", "permanently"):
            from rag import update_documents_retention
            from telegram_bot.client import send_message
            update_documents_retention(_pending_retention[chat_id], None)
            del _pending_retention[chat_id]
            await send_message("Done. Document kept permanently.", chat_id=chat_id)
            return {"ok": True}
        if raw_lower in ("week", "w", "1 week", "7 days", "auto", "offload"):
            from datetime import datetime, timedelta, timezone
            from rag import update_documents_retention
            from telegram_bot.client import send_message
            expires = datetime.now(timezone.utc) + timedelta(days=7)
            update_documents_retention(_pending_retention[chat_id], expires)
            del _pending_retention[chat_id]
            await send_message("Done. Document will auto-remove after 7 days.", chat_id=chat_id)
            return {"ok": True}
    print(f"[webhook] Processing from chat_id={chat_id} text={text[:50]!r}...", flush=True)
    try:
        from langchain_core.messages import HumanMessage
        from telegram_bot.client import send_message, send_typing
        from user_profile import load_user_profile, save_user_profile, extract_profile_from_message
        from memory import get_memory_store
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
                "store": get_memory_store(),
            }
        }
        graph = _get_graph()
        inputs = {"messages": [HumanMessage(content=text)], "step_count": 0}
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
