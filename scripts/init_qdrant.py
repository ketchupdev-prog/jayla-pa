# Create Qdrant collection for long-term memory. Run once after setting QDRANT_URL and QDRANT_API_KEY.
# Idempotent: skips creation if collection already exists. Vector size 768 = all-mpnet-base-v2.

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
_ENV_PATH = os.path.join(PA_ROOT, ".env")

# Load .env from project root (works with or without python-dotenv)
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

COLLECTION_NAME = "long_term_memory"
VECTOR_SIZE = 768  # all-mpnet-base-v2 (same as RAG in PERSONAL_ASSISTANT_PATTERNS.md)


def main() -> None:
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not url:
        print("Error: QDRANT_URL not set.", file=sys.stderr)
        sys.exit(1)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
    except ImportError:
        print("Error: qdrant-client not installed. Run: uv pip install qdrant-client", file=sys.stderr)
        sys.exit(1)

    client = QdrantClient(url=url, api_key=api_key or None)
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if exists:
        print(f"Collection '{COLLECTION_NAME}' already exists. Skipping.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"Created Qdrant collection '{COLLECTION_NAME}' (vector_size={VECTOR_SIZE}, distance=COSINE).")


if __name__ == "__main__":
    main()
