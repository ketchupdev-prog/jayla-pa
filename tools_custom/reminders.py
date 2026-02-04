# Reminder tools (Neon): create, list, cancel. Delivery of due reminders in webhook. See README.

import os
from datetime import datetime, timezone
from langchain_core.tools import tool

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    _HAS_PG = True
except ImportError:
    _HAS_PG = False


def _get_user_id() -> str:
    return os.environ.get("USER_ID") or os.environ.get("EMAIL", "default-user")


def _get_conn():
    if not _HAS_PG:
        raise RuntimeError("Install psycopg2-binary for reminder tools")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; reminder tools need Neon (or PostgreSQL).")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


@tool
def create_reminder(message: str, due_at: str) -> str:
    """Create a reminder. Use when the user says 'remind me to X at Y' or 'remind me in Z minutes/hours to X'.
    message: Short reminder text (e.g. 'Call John').
    due_at: When to remind, in ISO 8601 format (e.g. 2025-02-05T15:00:00 or 2025-02-05T15:00:00Z). Use current timezone or UTC."""
    user_id = _get_user_id()
    message = (message or "").strip()
    if not message:
        return "Reminder message cannot be empty."
    due_at = (due_at or "").strip()
    if not due_at:
        return "due_at is required (ISO 8601, e.g. 2025-02-05T15:00:00Z)."
    try:
        # Parse to validate
        if "Z" in due_at or due_at.endswith("+00:00"):
            dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(due_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= datetime.now(timezone.utc):
            return "due_at must be in the future."
        due_at_iso = dt.isoformat()
    except (ValueError, TypeError) as e:
        return f"Invalid due_at (use ISO 8601, e.g. 2025-02-05T15:00:00Z): {e}"
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO reminders (user_id, message, due_at) VALUES (%s, %s, %s::timestamptz) RETURNING id, message, due_at",
                    (user_id, message, due_at_iso),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception as e:
        err = str(e)
        if "reminders" in err and ("does not exist" in err or "relation" in err.lower()):
            return "Reminders table missing. Run SQL migrations (scripts/run_sql_migrations.py) first."
        if "DATABASE_URL" in err:
            return "DATABASE_URL not set; reminders need a database."
        return f"Error creating reminder: {e}"
    return f"Reminder set: \"{row['message']}\" at {row['due_at']} (id: {row['id']})."


@tool
def list_reminders() -> str:
    """List upcoming and past reminders for the user. Use when asked 'what reminders do I have', 'list my reminders', 'show reminders'."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, message, due_at, sent_at FROM reminders
                       WHERE user_id = %s ORDER BY due_at DESC LIMIT 30""",
                    (user_id,),
                )
                rows = cur.fetchall()
    except Exception as e:
        err = str(e)
        if "reminders" in err and ("does not exist" in err or "relation" in err.lower()):
            return "Reminders table missing. Run SQL migrations first."
        if "DATABASE_URL" in err:
            return "DATABASE_URL not set."
        return f"Error listing reminders: {e}"
    if not rows:
        return "No reminders."
    lines = []
    for r in rows:
        status = "sent" if r.get("sent_at") else "upcoming"
        lines.append(f"- \"{r['message']}\" at {r['due_at']} [{status}] (id: {r['id']})")
    return "\n".join(lines)


@tool
def cancel_reminder(reminder_id: str) -> str:
    """Cancel a reminder by id. Use when the user says 'cancel reminder X' or 'delete reminder X'. reminder_id: UUID from list_reminders."""
    user_id = _get_user_id()
    reminder_id = (reminder_id or "").strip()
    if not reminder_id:
        return "reminder_id is required (UUID from list_reminders)."
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM reminders WHERE id = %s AND user_id = %s RETURNING id",
                    (reminder_id, user_id),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception as e:
        return f"Error cancelling reminder: {e}"
    if row:
        return f"Reminder {reminder_id} cancelled."
    return f"No reminder found with id {reminder_id}."


def get_reminder_tools():
    """Return list of LangChain tools for reminders."""
    return [create_reminder, list_reminders, cancel_reminder]


def get_due_reminders(user_id: str) -> list[tuple[str, str]]:
    """Return list of (id, message) for reminders that are due and not yet sent. Does not mark as sent. Used by webhook and cron."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, message FROM reminders
                       WHERE user_id = %s AND due_at <= NOW() AND sent_at IS NULL""",
                    (user_id,),
                )
                rows = cur.fetchall()
    except Exception:
        return []
    return [(str(r["id"]), r["message"]) for r in rows]


def mark_reminders_sent(ids: list[str]) -> None:
    """Mark the given reminder IDs as sent. Call after successfully sending each reminder (webhook or cron)."""
    if not ids:
        return
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                for rid in ids:
                    cur.execute("UPDATE reminders SET sent_at = NOW() WHERE id = %s", (rid,))
                conn.commit()
    except Exception:
        pass  # Logged by caller if needed
