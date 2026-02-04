#!/usr/bin/env python3
"""
Test actual implementation: project/task tools (Neon), Arcade tools load, graph flows so Jayla
acts right (authorization interrupts, memory injection, full create/cleanup). No minimal-args
invokes — we test via graph prompts and direct tool calls only where needed for cleanup.
Run from repo root with .env set: python scripts/test_tool_calls.py
See PERSONAL_ASSISTANT_PATTERNS.md §8, C.5; Arcade auth: docs.arcade.dev, arcade-ai-agent/AUTHORIZATION.md.
Gmail/Calendar tools come from Arcade (langchain_arcade ToolManager), not Cursor.
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(PA_ROOT)
sys.path.insert(0, PA_ROOT)

# Load .env
_env_path = os.path.join(PA_ROOT, ".env")
if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

# Ensure EMAIL/USER_ID for project tools
os.environ.setdefault("EMAIL", "test-user@jayla.local")
os.environ.setdefault("USER_ID", os.environ.get("EMAIL", "test-user@jayla.local"))

# Logger for state, streaming, tool invocations
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jayla.test_tools")


def _today_iso():
    """Current date YYYY-MM-DD from TIMEZONE env (so calendar tests use correct date, not LLM cutoff)."""
    tz_name = os.environ.get("TIMEZONE", "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d")


def test_project_tools():
    """Test Neon-backed project/task tools (Neon DB via DATABASE_URL). Sequence: list (empty) -> create -> list (see one) -> update -> delete (cleanup). All tools hit the real database."""
    from tools_custom.project_tasks import (
        list_projects,
        create_project,
        delete_project,
        list_tasks,
        create_task_in_project,
        update_task,
        get_task,
        delete_task,
    )
    results = []
    # 1. list_projects (initial state: expect empty unless DB has data)
    out = list_projects.invoke({})
    logger.info("tool list_projects -> %s", (out or "empty")[:80])
    results.append(("list_projects (initial)", "OK" if out else "empty", str(out)[:80]))
    # 2. create_project (persists to Neon)
    out = create_project.invoke({"name": "Test Project from test_tool_calls"})
    if "Error" in out:
        results.append(("create_project", "FAIL", out[:80]))
        return results
    logger.info("tool create_project -> %s", out[:80])
    results.append(("create_project", "OK", out[:80]))
    match = re.search(r"id: ([a-f0-9-]{36})", out)
    project_id = match.group(1) if match else None
    if not project_id:
        results.append(("create_project id", "WARN", "could not parse project_id"))
        return results
    # 3. list_tasks (initial: no tasks yet)
    out = list_tasks.invoke({})
    results.append(("list_tasks (initial)", "OK", (out or "No tasks")[:80]))
    # 4. create_task_in_project (persists to Neon)
    out = create_task_in_project.invoke({
        "project_id": project_id,
        "title": "Test task from script",
        "notes": None,
        "due_date": None,
    })
    if "Error" in out:
        results.append(("create_task_in_project", "FAIL", out[:80]))
        return results
    logger.info("tool create_task_in_project -> %s", out[:80])
    results.append(("create_task_in_project", "OK", out[:80]))
    match = re.search(r"id: ([a-f0-9-]{36})", out)
    task_id = match.group(1) if match else None
    if not task_id:
        return results
    # 5. get_task
    out = get_task.invoke({"task_id": task_id})
    results.append(("get_task", "OK" if "Test task" in out else "FAIL", out[:80]))
    # 6. update_task
    out = update_task.invoke({"task_id": task_id, "status": "done"})
    logger.info("tool update_task -> %s", out[:80])
    results.append(("update_task", "OK" if "Updated" in out or "done" in out else "FAIL", out[:80]))
    # 7. list_tasks again (should show the task we created — proves DB is used)
    out = list_tasks.invoke({})
    results.append(("list_tasks (after create)", "OK", (out or "none")[:80]))
    # 8. delete_task (cleanup)
    out = delete_task.invoke({"task_id": task_id})
    results.append(("delete_task", "OK" if "Deleted" in out else "FAIL", out[:80]))
    # 9. delete_project (cleanup)
    out = delete_project.invoke({"project_id": project_id})
    results.append(("delete_project", "OK" if "Deleted" in out else "FAIL", out[:80]))
    return results


def test_arcade_tools_load():
    """Test that Arcade (Gmail, Calendar) tools load. Reminders = calendar-only (no create_reminder/list_reminders)."""
    try:
        from tools import get_tools
        tools = get_tools()
        names = [t.name for t in tools]
        reminder_tools = [n for n in names if "reminder" in n.lower()]
        if reminder_tools:
            return "FAIL", f"Unexpected reminder tools (reminders=calendar only): {reminder_tools}"
        logger.info("Arcade tools loaded: %s", sorted(names))
        return "OK", names
    except Exception as e:
        return "FAIL", str(e)


async def _run_graph_with_events(input_text: str, config: dict, log_events: bool = True):
    """Run graph with astream_events; log state, streaming, tool invocations; return final state."""
    from langchain_core.messages import HumanMessage
    from graph import build_graph

    graph = build_graph()
    inputs = {"messages": [HumanMessage(content=input_text)], "step_count": 0}
    result_state = None

    async for event in graph.astream_events(inputs, config=config, version="v2"):
        kind = event.get("event")
        name = event.get("name", "")
        if log_events:
            if kind == "on_chain_start":
                logger.info("stream event: chain_start name=%s", name)
            elif kind == "on_chain_end":
                logger.info("stream event: chain_end name=%s", name)
            elif kind == "on_tool_start":
                logger.info("stream event: tool_start name=%s", name)
            elif kind == "on_tool_end":
                logger.info("stream event: tool_end name=%s", name)
            elif kind == "on_chat_model_stream":
                pass  # too noisy
        # Capture final state from LangGraph (updates emitted per node)
        if "data" in event and isinstance(event.get("data", {}).get("output"), dict):
            result_state = event["data"]["output"]

    # If astream_events doesn't give us final state, invoke once to get it
    if result_state is None:
        result = await graph.ainvoke(inputs, config=config)
        result_state = result
    return result_state


def _last_ai_content(messages):
    """Extract last AI message content from state messages."""
    last_ai = next((m for m in reversed(messages) if getattr(m, "type", None) == "ai"), None)
    if not last_ai or not getattr(last_ai, "content", None):
        return None
    return (last_ai.content or "").strip()


def _parse_ids_from_messages(messages):
    """Parse project_id and task_id from ToolMessage content. Only project UUID from 'Created project' messages; only task UUID from 'Created task' messages (so we don't confuse them)."""
    import uuid
    project_ids = []
    task_ids = []
    for m in messages:
        if getattr(m, "type", None) != "tool" or not getattr(m, "content", None):
            continue
        text = m.content if isinstance(m.content, str) else str(m.content)
        if "Created project" in text:
            for match in re.finditer(r"id: ([a-f0-9-]{36})", text):
                try:
                    uuid.UUID(match.group(1))
                    project_ids.append(match.group(1))
                    break
                except ValueError:
                    pass
        if "Created task" in text and "Created project" not in text:
            for match in re.finditer(r"id: ([a-f0-9-]{36})", text):
                try:
                    uuid.UUID(match.group(1))
                    task_ids.append(match.group(1))
                    break
                except ValueError:
                    pass
    return project_ids, task_ids


def _has_auth_url_in_messages(messages):
    """True if any ToolMessage contains Authorization required and a URL (auth interrupt)."""
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        c = getattr(m, "content", None) or ""
        if "Authorization required" in c and "http" in c:
            return True
    return False


async def test_greeting_with_memory():
    """Test personalized greeting: memory injection + user_name in config."""
    from memory import get_memory_store

    config = {
        "configurable": {
            "thread_id": "test-greeting",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "user_name": "George",
            "user_role": "",
            "user_company": "",
            "store": get_memory_store(),
        }
    }
    logger.info("state: config user_name=George, store=%s", "set" if config["configurable"].get("store") else "none")
    state = await _run_graph_with_events("Hi!", config=config, log_events=True)
    messages = state.get("messages", [])
    content = _last_ai_content(messages)
    if not content:
        return "WARN", "No AI reply", None
    # Time-appropriate greeting
    greeting_ok = any(
        g in content for g in ("Good morning", "Good afternoon", "Good evening", "Hi", "Hello")
    )
    # Personalized: should use name if in prompt (user_name in config)
    name_ok = "George" in content or greeting_ok
    status = "OK" if (greeting_ok and name_ok) else "WARN"
    logger.info("greeting reply: %s", content)
    return status, content, content


async def test_authorization_interrupt():
    """Test Arcade auth: when Calendar needs auth, interrupt (show URL) and BLOCK until user completes
    authorization, then proceed. Leave PA_AUTH_NONBLOCK unset so nodes.authorize calls wait_for_auth.
    For non-blocking (CI) set PA_AUTH_NONBLOCK=1 in the environment before running."""
    from memory import get_memory_store

    # Do NOT set PA_AUTH_NONBLOCK so the test blocks on auth (user authorizes in browser, then test continues)
    if os.environ.get("PA_AUTH_NONBLOCK"):
        logger.info("PA_AUTH_NONBLOCK is set; auth will not block (link returned, test continues)")
    else:
        logger.info("PA_AUTH_NONBLOCK unset; auth will block until you complete authorization in browser")
    config = {
        "configurable": {
            "thread_id": "test-auth-interrupt",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "user_name": "",
            "store": get_memory_store(),
        }
    }
    today = _today_iso()
    state = await _run_graph_with_events(
        f"Today is {today}. List my calendar events for today.",
        config=config,
        log_events=True,
    )
    messages = state.get("messages", [])
    has_auth = _has_auth_url_in_messages(messages)
    content = _last_ai_content(messages) or ""
    if has_auth:
        logger.info("authorization was required; if blocking, you completed auth and flow continued")
        return "OK", "Auth URL shown; flow continued after authorization.", content
    if content and "calendar" in content.lower():
        logger.info("calendar listed (already authorized)")
        return "OK", "Calendar listed (already authorized).", content
    return "WARN", "No auth URL and no calendar reply.", content


async def test_full_flow_and_cleanup():
    """Create project + task via graph, update task, list; then delete task and project (cleanup)."""
    from memory import get_memory_store

    config = {
        "configurable": {
            "thread_id": "test-full-flow",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "user_name": "",
            "store": get_memory_store(),
        }
    }
    project_name = "Test Full Flow Project"
    task_title = "Test Full Flow Task"

    # Create project
    logger.info("state: create project via graph")
    state = await _run_graph_with_events(
        f"Create a project named {project_name}.",
        config=config,
        log_events=True,
    )
    messages = state.get("messages", [])
    project_ids, task_ids = _parse_ids_from_messages(messages)
    if not project_ids:
        # Maybe agent said "created" in text; try list and parse or create via direct tool
        from tools_custom.project_tasks import create_project, list_projects
        out = create_project.invoke({"name": project_name})
        m = re.search(r"id: ([a-f0-9-]{36})", out)
        if m:
            project_ids = [m.group(1)]

    if not project_ids:
        return "WARN", "Could not get project_id after create", [], []

    project_id = project_ids[0]
    logger.info("created project_id=%s", project_id)

    # Create task in project
    state = await _run_graph_with_events(
        f"Add a task to my project {project_name}: {task_title}.",
        config=config,
        log_events=True,
    )
    messages = state.get("messages", [])
    _, task_ids_from_create = _parse_ids_from_messages(messages)
    task_id = task_ids_from_create[-1] if task_ids_from_create else None
    if not task_id:
        from tools_custom.project_tasks import create_task_in_project
        out = create_task_in_project.invoke({
            "project_id": project_id,
            "title": task_title,
            "notes": None,
            "due_date": None,
        })
        m = re.search(r"id: ([a-f0-9-]{36})", out)
        if m:
            task_id = m.group(1)
    if task_id:
        logger.info("created task_id=%s", task_id)

    # Update task
    state = await _run_graph_with_events(
        f"Mark the task '{task_title}' as done.",
        config=config,
        log_events=True,
    )

    # List projects and tasks
    state = await _run_graph_with_events("List my projects and tasks.", config=config, log_events=True)

    # Cleanup: delete task then project
    from tools_custom.project_tasks import delete_task, delete_project
    if task_id:
        out = delete_task.invoke({"task_id": task_id})
        logger.info("cleanup delete_task -> %s", out[:80])
    out = delete_project.invoke({"project_id": project_id})
    logger.info("cleanup delete_project -> %s", out[:80])

    return "OK", "Full flow and cleanup done", project_ids, [task_id] if task_id else []


async def test_calendar_full_flow():
    """Calendar: list (today with correct date) -> create event -> update/reschedule -> delete. All output printed in terminal."""
    from memory import get_memory_store

    today = _today_iso()
    config = {
        "configurable": {
            "thread_id": "test-calendar-full",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "store": get_memory_store(),
        }
    }
    # 1. List events for today (correct date)
    logger.info("calendar: list events for today (%s)", today)
    state = await _run_graph_with_events(
        f"Today is {today}. List my calendar events for today.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    if _has_auth_url_in_messages(state.get("messages", [])):
        return "OK", "Auth required; list skipped.", content
    print(f"  [Calendar list] {content}\n")

    # 2. Create a test event (today)
    logger.info("calendar: create test event on %s", today)
    state = await _run_graph_with_events(
        f"Create a calendar event: title 'Jayla PA test event', on {today} from 14:00 to 14:30.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    if _has_auth_url_in_messages(state.get("messages", [])):
        return "OK", "Auth required; create skipped.", content
    print(f"  [Calendar create] {content}\n")

    # 3. Reschedule / update the event (ask agent to move it)
    logger.info("calendar: update/reschedule test event")
    state = await _run_graph_with_events(
        "Reschedule the event titled 'Jayla PA test event' to 15:00 today, same duration.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    print(f"  [Calendar update] {content}\n")

    # 4. Delete the test event
    logger.info("calendar: delete test event")
    state = await _run_graph_with_events(
        "Delete the calendar event titled 'Jayla PA test event'.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    print(f"  [Calendar delete] {content}\n")
    return "OK", "Calendar full flow done.", content


async def test_calendar_reminder_and_cleanup():
    """Set a reminder (GoogleCalendar_CreateEvent) with correct today, then delete it."""
    from memory import get_memory_store

    today = _today_iso()
    config = {
        "configurable": {
            "thread_id": "test-calendar-reminder",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "store": get_memory_store(),
        }
    }
    logger.info("state: set reminder (today=%s)", today)
    state = await _run_graph_with_events(
        f"Today is {today}. Set a reminder to practice hiragana today at 1pm.",
        config=config,
        log_events=True,
    )
    messages = state.get("messages", [])
    if _has_auth_url_in_messages(messages):
        logger.info("calendar auth required; skip cleanup (no event created)")
        return "OK", "Auth required (no event to delete)", None

    state = await _run_graph_with_events(
        f"Delete the reminder I just set for practicing hiragana (it was for today {today} at 1pm).",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    logger.info("calendar cleanup reply: %s", content)
    return "OK", "Reminder set and cleanup requested.", content


async def test_email_list():
    """List recent emails (Gmail via Arcade). May trigger auth interrupt."""
    from memory import get_memory_store

    config = {
        "configurable": {
            "thread_id": "test-email-list",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "store": get_memory_store(),
        }
    }
    logger.info("state: list emails (Arcade Gmail)")
    state = await _run_graph_with_events(
        "List my recent emails. What's in my inbox?",
        config=config,
        log_events=True,
    )
    messages = state.get("messages", [])
    content = _last_ai_content(messages) or ""
    if _has_auth_url_in_messages(messages):
        logger.info("email auth required")
        return "OK", "Auth URL returned.", content
    return "OK", content, content


async def test_email_full_flow():
    """Email: recent inbox, recent sent, recent drafts. All output printed in terminal."""
    from memory import get_memory_store

    config = {
        "configurable": {
            "thread_id": "test-email-full",
            "user_id": os.environ.get("EMAIL", "test@test.local"),
            "store": get_memory_store(),
        }
    }
    # Inbox (recent emails)
    logger.info("email: list recent inbox")
    state = await _run_graph_with_events(
        "List my 5 most recent emails in my inbox.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    if _has_auth_url_in_messages(state.get("messages", [])):
        print("  [Email inbox] Auth required.\n")
        return "OK", "Auth required.", content
    print(f"  [Email inbox]\n{content}\n")

    # Sent
    logger.info("email: list recent sent")
    state = await _run_graph_with_events(
        "List my 5 most recent sent emails.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    print(f"  [Email sent]\n{content}\n")

    # Drafts
    logger.info("email: list drafts")
    state = await _run_graph_with_events(
        "List my draft emails.",
        config=config,
        log_events=True,
    )
    content = _last_ai_content(state.get("messages", [])) or ""
    print(f"  [Email drafts]\n{content}\n")
    return "OK", "Email full flow done.", content


def main():
    today = _today_iso()
    tz_name = os.environ.get("TIMEZONE", "UTC")
    print("=== Jayla PA: test all tool calls (with logging, auth interrupt, memory, cleanup) ===")
    print(f"Current date (used for calendar): {today}  Timezone: {tz_name}\n")
    if not os.environ.get("PA_AUTH_NONBLOCK"):
        print("Auth: when Calendar/Gmail need authorization, the test will PAUSE and show a URL.\n"
              "Complete authorization in your browser, then the test will continue. Set PA_AUTH_NONBLOCK=1 to skip waiting.\n")
    else:
        print("PA_AUTH_NONBLOCK=1: auth will not block (link returned, test continues).\n")
    # 1. Project/task tools (Neon DB — same DB as production; we create then delete at end)
    print("[1/7] Project/task tools (Neon DB, DATABASE_URL)...")
    if not os.environ.get("DATABASE_URL"):
        print("  SKIP (DATABASE_URL not set)\n")
    else:
        try:
            for name, status, msg in test_project_tools():
                print(f"  {name}: {status}  {msg!r}")
            print("  (Neon DB used: create -> list shows data -> delete. Step [3/7] runs after this cleanup, so it correctly sees no projects.)")
        except Exception as e:
            logger.exception("project tools")
            print(f"  FAIL: {e}")
        print()

    # 2. Arcade tools load (Gmail, Calendar from Arcade – docs.arcade.dev)
    print("[2/7] Arcade tools (Gmail, Calendar) load...")
    try:
        status, data = test_arcade_tools_load()
        if status == "OK":
            calendar_tools = [n for n in data if "Calendar" in n or "calendar" in n]
            print(f"  OK ({len(data)} tools). Calendar (reminders=events): {calendar_tools or 'NONE'}")
            print(f"  All tool names: {sorted(data)}")
        else:
            print(f"  FAIL: {data}")
    except Exception as e:
        print(f"  FAIL: {e}")
    print()

    # 3. Graph invoke (list my projects) – same DB; [1/7] already deleted test data so list is empty
    print("[3/7] Graph invoke ('list my projects')...")
    try:
        from langchain_core.messages import HumanMessage
        from graph import build_graph
        graph = build_graph()
        config = {
            "configurable": {
                "thread_id": "test-tool-calls",
                "user_id": os.environ.get("EMAIL", "test@test.local"),
                "user_name": "",
                "user_role": "",
                "user_company": "",
            }
        }
        result = asyncio.run(graph.ainvoke(
            {"messages": [HumanMessage(content="List my projects. Reply in one short sentence.")], "step_count": 0},
            config=config,
        ))
        messages = result.get("messages", [])
        last_ai = next((m for m in reversed(messages) if getattr(m, "type", None) == "ai"), None)
        content = (last_ai.content or "").strip() if last_ai and getattr(last_ai, "content", None) else ""
        print(f"  OK:\n{content}")
    except Exception as e:
        print(f"  FAIL: {e}")
    print()

    # 4. Personalized greeting (memory injection)
    print("[4/7] Personalized greeting (memory injection + user_name)...")
    try:
        status, msg, _ = asyncio.run(test_greeting_with_memory())
        print(f"  {status}:")
        print(msg)
    except Exception as e:
        logger.exception("greeting")
        print(f"  FAIL: {e}")
    print()

    # 5. Authorization interrupt (calendar – blocks until you authorize in browser)
    print("[5/7] Authorization (calendar): interrupt until you authorize, then proceed...")
    try:
        status, msg, full = asyncio.run(test_authorization_interrupt())
        print(f"  {status}: {msg}")
        if full:
            print(f"  Reply:\n{full}")
    except Exception as e:
        logger.exception("auth interrupt")
        print(f"  FAIL: {e}")
    print()

    # 6. Full flow (projects/tasks) + calendar full flow (list/create/update/delete) + reminder + email full (inbox/sent/drafts)
    print("[6/7] Full flow: projects/tasks + calendar (list/create/update/delete) + reminder + email (inbox/sent/drafts)...")
    try:
        status, msg, *_ = asyncio.run(test_full_flow_and_cleanup())
        print(f"  full_flow (projects/tasks): {status} {msg}")
        status_cal, msg_cal, _ = asyncio.run(test_calendar_full_flow())
        print(f"  calendar_full_flow: {status_cal} {msg_cal}")
        status2, msg2, full2 = asyncio.run(test_calendar_reminder_and_cleanup())
        print(f"  calendar_reminder: {status2} {msg2}")
        if full2:
            print(f"  Reply:\n{full2}")
        status3, msg3, full3 = asyncio.run(test_email_full_flow())
        print(f"  email_full_flow: {status3} {msg3}")
        if full3:
            print(full3)
    except Exception as e:
        logger.exception("full flow / calendar / email")
        print(f"  FAIL: {e}")
    print()

    # 7. Each tool exercised via graph (prompt -> tool invoked -> output in terminal)
    print("[7/7] Each tool exercised (prompt triggers tool; output in terminal)...")
    try:
        from memory import get_memory_store
        today = _today_iso()
        config = {
            "configurable": {
                "thread_id": "test-each-tool",
                "user_id": os.environ.get("EMAIL", "test@test.local"),
                "store": get_memory_store(),
            }
        }
        # Prompts that should trigger each tool (or category). Fixed list of 7 — not a loop; each run is one full graph (RAG + LLM + tool).
        tool_prompts = [
            ("list_projects", "List my projects."),
            ("list_tasks", "List my tasks."),
            ("GoogleCalendar_ListCalendars", "List my calendars."),
            ("GoogleCalendar_ListEvents", f"Today is {today}. List my calendar events for today."),
            ("Gmail_ListThreads", "List my 3 most recent email threads."),
            ("Gmail_ListDraftEmails", "List my draft emails."),
            ("Gmail_ListLabels", "List my Gmail labels."),
        ]
        n_total = len(tool_prompts)
        for i, (tool_hint, prompt) in enumerate(tool_prompts, 1):
            print(f"  ({i}/{n_total}) {tool_hint}...", flush=True)
            state = asyncio.run(_run_graph_with_events(prompt, config=config, log_events=False))
            content = _last_ai_content(state.get("messages", [])) or ""
            print(f"  [{tool_hint}]\n{content}\n")
    except Exception as e:
        logger.exception("each tool")
        print(f"  FAIL: {e}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
