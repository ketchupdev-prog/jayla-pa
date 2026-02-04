#!/usr/bin/env python3
"""
Test all tool calls: project/task tools (Neon) and Arcade tools load.
Run from repo root with .env set: python scripts/test_tool_calls.py
See PERSONAL_ASSISTANT_PATTERNS.md §8, C.5.
"""

import os
import sys

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


def test_project_tools():
    """Test Neon-backed project/task tools (list_projects, create_project, list_tasks, create_task_in_project, update_task, get_task)."""
    from tools_custom.project_tasks import (
        list_projects,
        create_project,
        list_tasks,
        create_task_in_project,
        update_task,
        get_task,
    )
    results = []
    # 1. list_projects (empty or existing)
    out = list_projects.invoke({})
    results.append(("list_projects", "OK" if out else "empty", str(out)[:80]))
    # 2. create_project
    out = create_project.invoke({"name": "Test Project from test_tool_calls"})
    if "Error" in out:
        results.append(("create_project", "FAIL", out[:80]))
        return results
    results.append(("create_project", "OK", out[:80]))
    # Extract project_id from output (id: <uuid>)
    import re
    match = re.search(r"id: ([a-f0-9-]{36})", out)
    project_id = match.group(1) if match else None
    if not project_id:
        results.append(("create_project id", "WARN", "could not parse project_id"))
        return results
    # 3. list_tasks (empty)
    out = list_tasks.invoke({})
    results.append(("list_tasks", "OK", (out or "No tasks")[:80]))
    # 4. create_task_in_project
    out = create_task_in_project.invoke({
        "project_id": project_id,
        "title": "Test task from script",
        "notes": None,
        "due_date": None,
    })
    if "Error" in out:
        results.append(("create_task_in_project", "FAIL", out[:80]))
        return results
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
    results.append(("update_task", "OK" if "Updated" in out or "done" in out else "FAIL", out[:80]))
    # 7. list_tasks again (should show the task)
    out = list_tasks.invoke({})
    results.append(("list_tasks (after create)", "OK", (out or "none")[:80]))
    return results


def test_arcade_tools_load():
    """Test that Arcade (Gmail, Calendar) tools load. Does not call Gmail/Calendar APIs."""
    try:
        from tools import get_tools
        tools = get_tools()
        names = [t.name for t in tools]
        return "OK", names
    except Exception as e:
        return "FAIL", str(e)


async def test_graph_invoke_list_projects():
    """Invoke graph with 'list my projects' and check we get a reply (and optionally tool use)."""
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
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="List my projects. Reply in one short sentence.")]},
            config=config,
        )
        messages = result.get("messages", [])
        last_ai = next((m for m in reversed(messages) if getattr(m, "type", None) == "ai"), None)
        if not last_ai or not getattr(last_ai, "content", None):
            return "WARN", "No AI reply in result"
        content = (last_ai.content or "").strip()[:200]
        return "OK", content
    except Exception as e:
        return "FAIL", str(e)


def main():
    print("=== Jayla PA: test all tool calls ===\n")
    # 1. Project/task tools (Neon)
    print("[1/3] Project/task tools (Neon)...")
    if not os.environ.get("DATABASE_URL"):
        print("  SKIP (DATABASE_URL not set)\n")
    else:
        try:
            for name, status, msg in test_project_tools():
                print(f"  {name}: {status}  {msg!r}")
        except Exception as e:
            print(f"  FAIL: {e}")
        print()
    # 2. Arcade tools load
    print("[2/3] Arcade tools (Gmail, Calendar) load...")
    try:
        status, data = test_arcade_tools_load()
        if status == "OK":
            print(f"  OK ({len(data)} tools): {', '.join(data[:8])}{'...' if len(data) > 8 else ''}")
        else:
            print(f"  FAIL: {data}")
    except Exception as e:
        print(f"  FAIL: {e}")
    print()
    # 3. Graph invoke (list my projects)
    print("[3/3] Graph invoke ('list my projects')...")
    try:
        import asyncio
        status, msg = asyncio.run(test_graph_invoke_list_projects())
        if status == "OK":
            print(f"  OK: {msg!r}")
        else:
            print(f"  {status}: {msg}")
    except Exception as e:
        print(f"  FAIL: {e}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
