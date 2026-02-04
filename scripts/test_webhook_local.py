#!/usr/bin/env python3
"""
Send a simulated Telegram webhook POST to local webhook for testing.
Usage: python scripts/test_webhook_local.py "Your message here"
       python scripts/test_webhook_local.py   # uses default message
Reads TELEGRAM_CHAT_ID from .env so the webhook accepts the message; reply is sent to Telegram.
Run with uvicorn webhook already running (e.g. port 8000).
Reminders = calendar events only; e.g. "Remind me to X tomorrow at 3pm" uses Google Calendar.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(PA_ROOT)
sys.path.insert(0, PA_ROOT)

_env = os.path.join(PA_ROOT, ".env")
if os.path.isfile(_env):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        with open(_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def main():
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not chat_id:
        print("TELEGRAM_CHAT_ID not set in .env; webhook will skip the message. Set it to your Telegram chat id.")
    text = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else "Do I have any meetings this week?"
    payload = {
        "update_id": 999999,
        "message": {
            "message_id": 1,
            "from": {"id": 1, "first_name": "Test", "is_bot": False},
            "chat": {"id": int(chat_id) if chat_id.isdigit() else chat_id, "type": "private"},
            "date": 1700000000,
            "text": text,
        },
    }
    url = os.environ.get("WEBHOOK_TEST_URL", "http://127.0.0.1:8000/webhook")
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode()
            print(f"POST {url} -> {resp.status}")
            print(f"Body: {body}")
            print("Check Telegram for the bot reply.")
    except Exception as e:
        print(f"Request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
