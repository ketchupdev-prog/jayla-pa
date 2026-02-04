# Set Telegram webhook URL. See PERSONAL_ASSISTANT_PATTERNS.md A (scripts).

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
_env_path = os.path.join(PA_ROOT, ".env")
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


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    url = os.environ.get("BASE_URL", "").rstrip("/")
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set.", file=sys.stderr)
        sys.exit(1)
    if not url:
        print("BASE_URL not set (e.g. https://your-domain.com).", file=sys.stderr)
        sys.exit(1)
    webhook_url = f"{url}/webhook"
    import re
    import urllib.request
    import urllib.error
    import json
    # Telegram allows only [a-zA-Z0-9_-] in secret_token (no URL, colons, slashes)
    secret_ok = secret and re.match(r"^[A-Za-z0-9_-]{1,256}$", secret)
    payload = {"url": webhook_url}
    if secret_ok:
        payload["secret_token"] = secret
        print("Using TELEGRAM_WEBHOOK_SECRET (Telegram will send it in X-Telegram-Bot-Api-Secret-Token)")
    elif secret:
        print("Warning: TELEGRAM_WEBHOOK_SECRET contains disallowed characters (use only letters, numbers, hyphen, underscore). Webhook set without secret.", file=sys.stderr)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            out = json.loads(resp.read().decode())
            print(out)
            if out.get("ok"):
                print("Webhook set:", webhook_url)
            else:
                print("Failed:", out.get("description"), file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
    sys.exit(0)
