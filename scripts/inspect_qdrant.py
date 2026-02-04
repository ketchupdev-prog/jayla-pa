# Inspect Qdrant: list collections, point count, and sample memories.
# Run from jayla-pa with QDRANT_URL and QDRANT_API_KEY set (e.g. from .env).
# Usage: python scripts/inspect_qdrant.py [--sample N]

import os
import sys

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

COLLECTION_NAME = "long_term_memory"


def main() -> None:
    url = os.getenv("QDRANT_URL", "").strip()
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
    if not url:
        print("QDRANT_URL not set. Set it in .env or environment.", file=sys.stderr)
        sys.exit(1)

    sample_n = 5
    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        sample_n = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import ScrollRequest
    except ImportError:
        print("qdrant-client not installed. Run: uv pip install qdrant-client", file=sys.stderr)
        sys.exit(1)

    client = QdrantClient(url=url, api_key=api_key)
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    print("Collections:", names)

    if COLLECTION_NAME not in names:
        print(f"Collection '{COLLECTION_NAME}' does not exist. Run: python scripts/init_qdrant.py")
        return

    info = client.get_collection(COLLECTION_NAME)
    count = info.points_count
    print(f"Collection '{COLLECTION_NAME}': {count} points (memories)")

    if count == 0:
        print("No memories stored yet. Memory writing (e.g. 'remember X') is not yet in the graph; memories are only read when the agent runs.")
        return

    # Scroll a few points to show namespace + data
    result, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=sample_n,
        with_payload=True,
        with_vectors=False,
    )
    print(f"\nSample (up to {len(result)} points):")
    for i, pt in enumerate(result, 1):
        payload = pt.payload or {}
        ns = payload.get("namespace", "")
        data = payload.get("data", "")[:120]
        if len(payload.get("data", "")) > 120:
            data += "..."
        print(f"  {i}. namespace={ns}")
        print(f"     data: {data}")


if __name__ == "__main__":
    main()
