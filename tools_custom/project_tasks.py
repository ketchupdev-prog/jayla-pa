# Project/task CRUD tools (Neon). See PERSONAL_ASSISTANT_PATTERNS.md §8, C.5.

import os
from langchain_core.tools import tool

# Optional: use psycopg2 for Neon; add psycopg2-binary to requirements if using this path
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
        raise RuntimeError("Install psycopg2-binary for project/task tools")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; project/task tools need a Neon (or PostgreSQL) connection.")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


@tool
def list_projects() -> str:
    """List the user's projects. Call this when the user asks: what projects do I have, list my projects, show projects, list projects."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, created_at FROM projects WHERE user_id = %s ORDER BY name",
                    (user_id,),
                )
                rows = cur.fetchall()
    except Exception as e:
        err = str(e).strip()
        if "DATABASE_URL" in err or "not set" in err:
            return "Projects are not available: DATABASE_URL is not configured. Set it in the environment to use project/task tools."
        if "does not exist" in err or "relation" in err.lower():
            return "Projects table is missing. Run SQL migrations (e.g. scripts/run_sql_migrations.py) against the database first."
        return f"Error listing projects: {e}"
    if not rows:
        return "No projects yet."
    return "\n".join(f"- {r['name']} (id: {r['id']})" for r in rows)


@tool
def create_project(name: str) -> str:
    """Create a new project. Use when asked to 'add a project called X'."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO projects (user_id, name) VALUES (%s, %s) RETURNING id, name",
                    (user_id, name.strip()),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception as e:
        return f"Error creating project: {e}"
    return f"Created project '{row['name']}' (id: {row['id']})."


@tool
def list_tasks(project_id: str | None = None, status: str | None = None) -> str:
    """List tasks, optionally for one project or by status (todo, in_progress, done). Use for 'what do I have due?', 'tasks in project X'."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                if project_id:
                    cur.execute(
                        """SELECT t.id, t.title, t.status, t.due_date, p.name as project_name
                           FROM tasks t JOIN projects p ON t.project_id = p.id
                           WHERE t.user_id = %s AND t.project_id = %s
                           ORDER BY t.due_date NULLS LAST, t.created_at""",
                        (user_id, project_id),
                    )
                else:
                    cur.execute(
                        """SELECT t.id, t.title, t.status, t.due_date, p.name as project_name
                           FROM tasks t JOIN projects p ON t.project_id = p.id
                           WHERE t.user_id = %s
                           ORDER BY t.due_date NULLS LAST, t.created_at""",
                        (user_id,),
                    )
                rows = cur.fetchall()
                if status:
                    rows = [r for r in rows if r["status"] == status]
    except Exception as e:
        return f"Error listing tasks: {e}"
    if not rows:
        return "No tasks found."
    out = []
    for r in rows[:30]:
        due = f" due {r['due_date']}" if r.get("due_date") else ""
        out.append(f"- {r['title']} ({r['status']}{due}) [id: {r['id']}]")
    if len(rows) > 30:
        out.append(f"... and {len(rows) - 30} more.")
    return "\n".join(out)


@tool
def create_task_in_project(project_id: str, title: str, notes: str | None = None, due_date: str | None = None) -> str:
    """Create a task in a project. project_id is required (UUID). due_date format: YYYY-MM-DD."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO tasks (project_id, user_id, title, notes, due_date)
                       VALUES (%s, %s, %s, %s, %s::date) RETURNING id, title, status""",
                    (project_id, user_id, title.strip(), notes, due_date),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception as e:
        return f"Error creating task: {e}"
    return f"Created task '{row['title']}' (id: {row['id']}, status: {row['status']})."


@tool
def update_task(task_id: str, status: str | None = None, title: str | None = None, due_date: str | None = None, notes: str | None = None) -> str:
    """Update a task by id. status: todo, in_progress, or done. due_date: YYYY-MM-DD."""
    user_id = _get_user_id()
    updates = []
    args = []
    if status is not None:
        updates.append("status = %s")
        args.append(status)
    if title is not None:
        updates.append("title = %s")
        args.append(title)
    if due_date is not None:
        updates.append("due_date = %s::date")
        args.append(due_date)
    if notes is not None:
        updates.append("notes = %s")
        args.append(notes)
    if not updates:
        return "No updates provided."
    updates.append("updated_at = NOW()")
    args.append(task_id)
    args.append(user_id)
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id, title, status",
                    args,
                )
                row = cur.fetchone()
                conn.commit()
    except Exception as e:
        return f"Error updating task: {e}"
    if not row:
        return "Task not found or not yours."
    return f"Updated task '{row['title']}' (id: {row['id']}, status: {row['status']})."


@tool
def get_task(task_id: str) -> str:
    """Get one task by id (UUID). Use when you need full details for a task."""
    user_id = _get_user_id()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT t.id, t.title, t.notes, t.status, t.due_date, t.created_at, p.name as project_name
                       FROM tasks t JOIN projects p ON t.project_id = p.id
                       WHERE t.id = %s AND t.user_id = %s""",
                    (task_id, user_id),
                )
                row = cur.fetchone()
    except Exception as e:
        return f"Error getting task: {e}"
    if not row:
        return "Task not found."
    due = f", due {row['due_date']}" if row.get("due_date") else ""
    return f"Task: {row['title']} (status: {row['status']}{due}, project: {row['project_name']}). Notes: {row['notes'] or 'none'}"


def get_project_tools():
    """Return list of LangChain tools for project/task CRUD."""
    return [list_projects, create_project, list_tasks, create_task_in_project, update_task, get_task]
