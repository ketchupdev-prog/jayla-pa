# CLI entry for Jayla PA. See PERSONAL_ASSISTANT_PATTERNS.md §3 (CLI).

import os
import sys

# Load .env when running CLI
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from langchain_core.messages import HumanMessage, AIMessage
from graph import build_graph


def main():
    user_id = os.environ.get("USER_ID") or os.environ.get("EMAIL", "default")
    thread_id = os.environ.get("THREAD_ID", "cli")
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
    graph = build_graph()
    print("Jayla PA (CLI). Say 'quit' or 'exit' to stop.\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            break
        inputs = {"messages": [HumanMessage(content=text)]}
        result = graph.invoke(inputs, config=config)
        messages = result.get("messages", [])
        for m in reversed(messages):
            if hasattr(m, "content") and m.content and getattr(m, "type", None) == "ai":
                print("Jayla:", m.content if isinstance(m.content, str) else str(m.content))
                break
        else:
            print("Jayla: (no reply)")
    print("Bye.")


if __name__ == "__main__":
    main()
    sys.exit(0)
