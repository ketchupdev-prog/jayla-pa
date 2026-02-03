# Long-term memory (Qdrant). See PERSONAL_ASSISTANT_PATTERNS.md C.6.

import os
import uuid
from langchain_core.runnables import RunnableConfig


def get_memory_namespace(config: RunnableConfig) -> tuple:
    user_id = (
        config.get("configurable", {}).get("user_id")
        or os.environ.get("EMAIL", "")
    ).strip()
    safe = user_id.replace(".", "") if user_id else "default"
    return ("memories", safe), user_id


def get_memories(store, namespace: tuple, query: str, limit: int = 5) -> list:
    if store is None:
        return []
    try:
        results = store.asearch(namespace, query=query, limit=limit)
        return [str(r.value.get("data", r.value)) for r in results if r.value]
    except Exception:
        return []


async def put_memory(store, namespace: tuple, data: str) -> None:
    if store is None:
        return
    try:
        await store.aput(namespace, str(uuid.uuid4()), {"data": data})
    except Exception:
        pass
