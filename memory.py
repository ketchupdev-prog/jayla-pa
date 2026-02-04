# Long-term memory (Qdrant). See PERSONAL_ASSISTANT_PATTERNS.md C.6.
# The agent receives a store via config["configurable"]["store"]. If present, get_memories()
# searches it and injects memory_context into the system prompt. Run init_qdrant.py once.

import os
import uuid
from langchain_core.runnables import RunnableConfig

COLLECTION_NAME = "long_term_memory"
VECTOR_SIZE = 768  # all-mpnet-base-v2 (match scripts/init_qdrant.py)


def get_memory_namespace(config: RunnableConfig) -> tuple:
    user_id = (
        config.get("configurable", {}).get("user_id")
        or os.environ.get("EMAIL", "")
    ).strip()
    safe = user_id.replace(".", "") if user_id else "default"
    return ("memories", safe), user_id


def get_memories(store, namespace: tuple, query: str, limit: int = 5) -> list:
    """Return list of memory strings for the given namespace and query. Sync; used by agent."""
    if store is None:
        return []
    try:
        # Prefer sync search (QdrantMemoryStore); fallback for LangGraph Store would need async
        if hasattr(store, "search_sync"):
            return store.search_sync(namespace, query, limit)
        return []
    except Exception:
        return []


async def put_memory(store, namespace: tuple, data: str) -> None:
    if store is None:
        return
    try:
        if hasattr(store, "put_sync"):
            store.put_sync(namespace, str(uuid.uuid4()), {"data": data})
        elif hasattr(store, "aput"):
            await store.aput(namespace, str(uuid.uuid4()), {"data": data})
    except Exception:
        pass


class QdrantMemoryStore:
    """Sync Qdrant-backed store for agent memory. Use get_memory_store() to obtain an instance."""

    def __init__(self, url: str, api_key: str | None, collection: str = COLLECTION_NAME):
        from qdrant_client import QdrantClient
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._embed_fn = None  # lazy init

    def _embed(self, text: str) -> list[float]:
        if self._embed_fn is None:
            from sentence_transformers import SentenceTransformer
            # Must match init_qdrant.py VECTOR_SIZE (768)
            self._embed_fn = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        emb = self._embed_fn.encode(text or " ", convert_to_numpy=True)
        return emb.tolist()

    def search_sync(self, namespace: tuple, query: str, limit: int = 5) -> list[str]:
        try:
            vector = self._embed(query or "")
            ns_str = "|".join(str(x) for x in namespace)
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = self._client.search(
                collection_name=self._collection,
                query_vector=vector,
                query_filter=Filter(must=[FieldCondition(key="namespace", match=MatchValue(value=ns_str))]),
                limit=limit,
            )
            return [hit.payload.get("data", "") for hit in results if hit.payload and hit.payload.get("data")]
        except Exception:
            return []

    def put_sync(self, namespace: tuple, key: str, value: dict) -> None:
        try:
            data = value.get("data", str(value))
            vector = self._embed(data)
            ns_str = "|".join(str(x) for x in namespace)
            from qdrant_client.models import PointStruct
            point_id = abs(hash((ns_str, key))) % (2**63)
            self._client.upsert(
                collection_name=self._collection,
                points=[PointStruct(id=point_id, vector=vector, payload={"namespace": ns_str, "key": key, "data": data})],
            )
        except Exception:
            pass


_memory_store: QdrantMemoryStore | None = None


def get_memory_store() -> QdrantMemoryStore | None:
    """Return a Qdrant-backed memory store if QDRANT_URL is set, else None. Cached per process."""
    global _memory_store
    url = (os.environ.get("QDRANT_URL") or "").strip()
    if not url:
        return None
    if _memory_store is None:
        try:
            _memory_store = QdrantMemoryStore(url, os.environ.get("QDRANT_API_KEY"))
        except Exception:
            return None
    return _memory_store
