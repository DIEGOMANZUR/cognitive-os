from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

from cognitive_os.deepagents.research_deepagent import create_workspace
from cognitive_os.deepagents.schemas import DeepAgentTask
from cognitive_os.deepagents.service import run_deepagent_task


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: uv run python ../scripts/test_deepagent_research.py \"consulta\"")
        return 2
    task = DeepAgentTask(
        task_id=str(uuid4()),
        thread_id="manual-test",
        user_id="manual",
        task_type="research",
        query=sys.argv[1],
        web_allowed="--web" in sys.argv[2:],
    )
    result = run_deepagent_task(task)
    workspace = create_workspace(task)
    (workspace.root_dir / "result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("ANSWER")
    print(result.answer)
    print("\nFINDINGS")
    for finding in result.findings:
        print(f"- {finding}")
    print("\nCITATIONS")
    for citation in result.citations:
        print(f"- {citation.model_dump()}")
    print(f"\nresult.json: {Path('storage/workspaces') / task.thread_id / task.task_id / 'result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
