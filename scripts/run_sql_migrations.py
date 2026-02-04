# Run sql/ migrations against Neon. See PERSONAL_ASSISTANT_PATTERNS.md A (scripts).

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
SQL_DIR = os.path.join(PA_ROOT, "sql")

# Load .env from project root (works with or without python-dotenv)
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
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set.", file=sys.stderr)
        sys.exit(1)
    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2-binary: pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)
    order = ["0-drop-all.sql", "0-extensions.sql", "1-projects-tasks.sql", "2-rag-documents.sql", "3-user-profiles.sql", "4-onboarding-fields.sql", "5-reminders.sql"]
    for name in order:
        path = os.path.join(SQL_DIR, name)
        if not os.path.isfile(path):
            continue
        print(f"Running {name}...")
        with open(path) as f:
            sql = f.read()
        # Mask semicolons inside comment-only lines so they don't split statements
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
                    # Drop leading comment-only lines so "CREATE TABLE" isn't skipped
                    lines = stmt.split("\n")
                    while lines and (not lines[0].strip() or lines[0].strip().startswith("--")):
                        lines.pop(0)
                    stmt = "\n".join(lines).strip()
                    if stmt:
                        cur.execute(stmt)
        finally:
            conn.close()
        print(f"  OK: {name}")
    print("Migrations done.")


if __name__ == "__main__":
    main()
    sys.exit(0)
