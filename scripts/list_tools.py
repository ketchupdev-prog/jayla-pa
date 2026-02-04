#!/usr/bin/env python3
"""
Print all tool names available to Jayla (Arcade + custom).
Run from repo root with .env set: python scripts/list_tools.py
Reminders = calendar events only (GoogleCalendar_*); no create_reminder/list_reminders.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(PA_ROOT)
sys.path.insert(0, PA_ROOT)

_env_path = os.path.join(PA_ROOT, ".env")
if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

def main():
    if not os.environ.get("ARCADE_API_KEY"):
        print("ARCADE_API_KEY not set. Set it in .env to list Arcade tools.")
        sys.exit(1)
    try:
        from tools import get_tools
        tools = get_tools()
        names = sorted([t.name for t in tools])
        gmail = [n for n in names if "Gmail" in n or "gmail" in n.lower()]
        calendar = [n for n in names if "Calendar" in n or "calendar" in n.lower()]
        print(f"Total tools: {len(names)}\n")
        print("Gmail (Arcade):", gmail or "NONE")
        print("Google Calendar (Arcade, reminders=events):", calendar or "NONE")
        print("\nAll tool names:")
        for n in names:
            print(f"  {n}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
