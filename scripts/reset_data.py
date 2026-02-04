#!/usr/bin/env python3
# Reset Neon (all tables: checkpointer, user_profiles, documents, projects, tasks) and Qdrant (long_term_memory).
# Destructive. Use for dev or to wipe all data. Requires --yes to run.
# After reset: run_sql_migrations recreates schema; webhook lifespan recreates checkpointer tables; init_qdrant recreates Qdrant collection.

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
SQL_DIR = os.path.join(PA_ROOT, "sql")
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


def reset_neon() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set; skipping Neon reset.", flush=True)
        return
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed; skipping Neon reset.", flush=True)
        return
    order = [
        "0-drop-all.sql",
        "0-extensions.sql",
        "1-projects-tasks.sql",
        "2-rag-documents.sql",
        "3-user-profiles.sql",
        "4-onboarding-fields.sql",
    ]
    for name in order:
        path = os.path.join(SQL_DIR, name)
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            sql = f.read()
        lines = sql.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("--"):
                lines[i] = ""
        sql_to_split = "\n".join(lines)
        conn = psycopg2.connect(url)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                for stmt in sql_to_split.split(";"):
                    stmt = stmt.strip()
                    stmt_lines = stmt.split("\n")
                    while stmt_lines and (not stmt_lines[0].strip() or stmt_lines[0].strip().startswith("--")):
                        stmt_lines.pop(0)
                    stmt = "\n".join(stmt_lines).strip()
                    if stmt:
                        cur.execute(stmt)
        finally:
            conn.close()
        print(f"  Neon: {name} OK", flush=True)
    print("Neon reset done (all tables dropped and recreated).", flush=True)


def reset_qdrant() -> None:
    url = (os.environ.get("QDRANT_URL") or "").strip()
    if not url:
        print("QDRANT_URL not set; skipping Qdrant reset.", flush=True)
        return
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("qdrant-client not installed; skipping Qdrant reset.", flush=True)
        return
    api_key = (os.environ.get("QDRANT_API_KEY") or "").strip() or None
    client = QdrantClient(url=url, api_key=api_key)
    coll = "long_term_memory"
    names = [c.name for c in client.get_collections().collections]
    if coll in names:
        client.delete_collection(coll)
        print(f"  Qdrant: deleted collection '{coll}'.", flush=True)
    else:
        print(f"  Qdrant: collection '{coll}' did not exist.", flush=True)
    print("Qdrant reset done. Run: python scripts/init_qdrant.py to recreate the collection.", flush=True)


def main() -> None:
    if "--yes" not in sys.argv and "-y" not in sys.argv:
        print("This will DELETE all data in Neon (checkpointer, user_profiles, documents, projects, tasks) and Qdrant (long_term_memory).", file=sys.stderr)
        print("Run with --yes to confirm.", file=sys.stderr)
        sys.exit(1)
    print("Resetting Neon and Qdrant...", flush=True)
    reset_neon()
    reset_qdrant()
    print("Reset complete.", flush=True)


if __name__ == "__main__":
    main()
