#!/usr/bin/env python3
# Create Postgres checkpointer tables (conversation history). Run once after setting DATABASE_URL.
# Idempotent. The webhook also runs checkpointer.setup() on startup via lifespan.

import os
import sys
import asyncio

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
_ENV_PATH = os.path.join(PA_ROOT, ".env")
if os.path.isfile(_ENV_PATH):
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_PATH)
    except ImportError:
        with open(_ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)


async def main() -> None:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print("Error: DATABASE_URL not set. Set it in .env or environment.", file=sys.stderr)
        sys.exit(1)
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError:
        print("Error: langgraph-checkpoint-postgres not installed. Run: pip install langgraph-checkpoint-postgres", file=sys.stderr)
        sys.exit(1)
    async with AsyncPostgresSaver.from_conn_string(url) as checkpointer:
        await checkpointer.setup()
    print("Postgres checkpointer tables created. Conversation history will persist across restarts.")


if __name__ == "__main__":
    asyncio.run(main())
