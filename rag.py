# RAG: Docling + all-mpnet-base-v2 + Neon. See PERSONAL_ASSISTANT_PATTERNS.md §8.5, §8.5a.
# Stub: implement load → split → embed → store (Neon) and retrieve for agent context.

import os
from typing import List

# Docling: pip install docling
# Embedder: sentence-transformers all-mpnet-base-v2 (768d)
# Neon: documents table with user_id, content, embedding vector(768), scope, expires_at


def ingest_document(
    file_path: str | None = None,
    bytes_content: bytes | None = None,
    user_id: str | None = None,
    scope: str = "long_term",
    expires_at=None,
) -> str:
    """Load document (Docling), split, embed (all-mpnet-base-v2), store in Neon. Returns status message."""
    user_id = user_id or os.environ.get("USER_ID") or os.environ.get("EMAIL", "default")
    # TODO: Docling load → RecursiveCharacterTextSplitter → SentenceTransformer.embed → Neon insert
    return f"RAG ingest not yet implemented (Docling + Neon). user_id={user_id}"


def retrieve(query: str, user_id: str | None = None, limit: int = 5) -> List[str]:
    """Embed query, similarity search in Neon documents (user_id, not expired), return chunk texts."""
    user_id = user_id or os.environ.get("USER_ID") or os.environ.get("EMAIL", "default")
    # TODO: embed query → Neon similarity search → return content list
    return []
