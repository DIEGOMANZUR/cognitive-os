#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.messages import AIMessage

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend" / "src"))

from cognitive_os.agents.graph import build_graph, initial_state, postgres_checkpointer, resume_graph


def main() -> None:
    thread_id = input("thread_id: ").strip()
    if not thread_id:
        raise SystemExit("thread_id is required")

    with postgres_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        while True:
            user_text = input("you> ").strip()
            if user_text in {"exit", "quit"}:
                return
            if user_text.startswith("/resume "):
                _, action, *rest = user_text.split(" ", 2)
                result = resume_graph(
                    graph,
                    thread_id=thread_id,
                    action=action,
                    message=rest[0] if rest else None,
                )
            else:
                result = graph.invoke(
                    initial_state(user_text, thread_id=thread_id),
                    config={"configurable": {"thread_id": thread_id}},
                )
            if "__interrupt__" in result:
                print(f"interrupt> {result['__interrupt__']}")
                print("Use /resume approve, /resume reject, or /resume edit <message>")
                continue
            messages = result.get("messages", [])
            ai_messages = [message for message in messages if isinstance(message, AIMessage)]
            if ai_messages:
                print(f"assistant> {ai_messages[-1].content}")
            else:
                print(f"state> {result}")


if __name__ == "__main__":
    main()
