# Telegram bot client. See PERSONAL_ASSISTANT_PATTERNS.md C.9.

import os
from telegram import Bot

_bot = None


def get_bot():
    global _bot
    if _bot is None:
        _bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    return _bot


async def send_message(text: str, parse_mode: str | None = None, chat_id: str | None = None):
    """Send a message. Uses TELEGRAM_CHAT_ID if chat_id not provided (single-user)."""
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not cid:
        raise ValueError("TELEGRAM_CHAT_ID not set and chat_id not provided")
    await get_bot().send_message(chat_id=cid, text=text, parse_mode=parse_mode)


async def send_typing(chat_id: str | None = None):
    """Send typing action. Uses TELEGRAM_CHAT_ID if chat_id not provided."""
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not cid:
        return
    await get_bot().send_chat_action(chat_id=cid, action="typing")
