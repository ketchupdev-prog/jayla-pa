# RAG: Docling + all-mpnet-base-v2 + Neon. See PERSONAL_ASSISTANT_PATTERNS.md §8.5, §8.5a, ONBOARDING_PLAN.md §5.
# Flow: load (Docling) → split (RecursiveCharacterTextSplitter) → embed (sentence-transformers) → store/retrieve (Neon documents).

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any

# Chunk size ~500–1000, overlap ~100 (ONBOARDING_PLAN.md §5)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Embedding dim for all-mpnet-base-v2; must match sql/2-rag-documents.sql
EMBEDDING_DIM = 768


def _get_embedder():
    """Lazy-load SentenceTransformer (heavy)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-mpnet-base-v2")


def _get_conn():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; RAG needs Neon (or PostgreSQL) with pgvector.")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def _bytes_to_text(bytes_content: bytes, filename: str = "") -> str:
    """Parse PDF/DOCX bytes to plain text. Uses Docling; fallback PyPDF2/docx2txt if needed."""
    suffix = (filename or "").lower()
    if suffix.endswith(".pdf"):
        ext = ".pdf"
    elif suffix.endswith(".docx") or suffix.endswith(".doc"):
        ext = ".docx"
    else:
        ext = ".pdf"  # try PDF first for unknown
    try:
        from docling.document_converter import DocumentConverter
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(bytes_content)
            tmp_path = tmp.name
        try:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            text = result.document.export_to_markdown() or ""
            return text.strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as docling_err:
        # Optional lightweight fallback when Docling fails (e.g. some PDFs); requires pypdf2 / docx2txt
        if ext == ".pdf":
            try:
                import PyPDF2
                import io
                reader = PyPDF2.PdfReader(io.BytesIO(bytes_content))
                return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
            except ImportError:
                raise docling_err
            except Exception:
                raise docling_err
        if ext == ".docx" or ".doc" in suffix:
            try:
                import docx2txt
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(bytes_content)
                    tmp_path = tmp.name
                try:
                    return (docx2txt.process(tmp_path) or "").strip()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except ImportError:
                raise docling_err
            except Exception:
                raise docling_err
        raise docling_err


def ingest_document(
    file_path: str | None = None,
    bytes_content: bytes | None = None,
    user_id: str | None = None,
    scope: str = "long_term",
    expires_at: Any = None,
    metadata: dict | None = None,
) -> tuple[str, list[int]]:
    """Load document (Docling or fallback), split, embed (all-mpnet-base-v2), store in Neon.
    Returns (status_message, list of inserted document row ids)."""
    user_id = user_id or os.environ.get("USER_ID") or os.environ.get("EMAIL", "default")
    metadata = metadata or {}
    filename = metadata.get("filename", "") or (os.path.basename(file_path) if file_path else "")

    if file_path and os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            raw = f.read()
    elif bytes_content:
        raw = bytes_content
    else:
        return ("No file path or bytes_content provided.", [])

    try:
        text = _bytes_to_text(raw, filename)
    except Exception as e:
        return (f"Could not parse document: {e}", [])

    if not text.strip():
        return ("Document contained no extractable text.", [])

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = splitter.split_text(text)

    model = _get_embedder()
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    meta_json = json.dumps({
        "source": metadata.get("source", "upload"),
        "filename": filename,
        "doc_type": metadata.get("doc_type", "other"),
        **{k: v for k, v in metadata.items() if k not in ("source", "filename", "doc_type")},
    })

    inserted_ids: list[int] = []
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                for content, emb in zip(chunks, embeddings):
                    vec_str = "[" + ",".join(str(x) for x in emb) + "]"
                    cur.execute(
                        """INSERT INTO documents (user_id, content, metadata, embedding, scope, expires_at)
                           VALUES (%s, %s, %s, %s::vector, %s, %s) RETURNING id""",
                        (user_id, content, meta_json, vec_str, scope, expires_at),
                    )
                    row = cur.fetchone()
                    if row:
                        inserted_ids.append(row["id"])
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        err = str(e)
        if "relation \"documents\" does not exist" in err or "does not exist" in err.lower():
            return ("RAG documents table is missing. Run SQL migrations (e.g. scripts/run_sql_migrations.py) with 2-rag-documents.sql first.", [])
        if "extension" in err.lower() and "vector" in err.lower():
            return ("pgvector extension is required. Run 0-extensions.sql (CREATE EXTENSION IF NOT EXISTS vector) then 2-rag-documents.sql.", [])
        return (f"Error storing document: {e}", [])

    return (f"Added {len(chunks)} chunk(s) from {filename or 'document'} to your documents.", inserted_ids)


def update_documents_retention(document_ids: list[int], expires_at: datetime | None) -> None:
    """Set expires_at for the given document row ids (e.g. None = permanent, or now+7d for auto-offload)."""
    if not document_ids:
        return
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET expires_at = %s WHERE id = ANY(%s)",
                    (expires_at, document_ids),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[rag] update_documents_retention failed: {e}", flush=True)


def retrieve(query: str, user_id: str | None = None, limit: int = 5) -> list[str]:
    """Embed query, similarity search in Neon documents (user_id, not expired), return chunk texts."""
    user_id = user_id or os.environ.get("USER_ID") or os.environ.get("EMAIL", "default")
    if not query.strip():
        return []

    try:
        model = _get_embedder()
        query_emb = model.encode([query.strip()], show_progress_bar=False).tolist()[0]
    except Exception as e:
        print(f"[rag] Embedding failed: {e}", flush=True)
        return []

    vec_str = "[" + ",".join(str(x) for x in query_emb) + "]"
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                # Cosine distance <=>; lower = more similar. Exclude expired.
                cur.execute(
                    """SELECT content FROM documents
                       WHERE user_id = %s AND (expires_at IS NULL OR expires_at > NOW())
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s""",
                    (user_id, vec_str, limit),
                )
                rows = cur.fetchall()
            return [r["content"] for r in rows] if rows else []
        finally:
            conn.close()
    except Exception as e:
        print(f"[rag] Retrieve failed: {e}", flush=True)
        return []
