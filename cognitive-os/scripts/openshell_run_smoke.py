from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from cognitive_os.deepagents.openshell_adapter import OpenShellAdapter
from cognitive_os.deepagents.openshell_schemas import OpenShellTask


async def main() -> None:
    task = OpenShellTask(
        task_id=str(uuid4()),
        thread_id="openshell-smoke",
        user_id="manual",
        purpose="code_test",
        instruction=(
            "crea un archivo hello.txt dentro del sandbox output con el texto hello cognitive os"
        ),
        require_human_approval=True,
    )
    result = await OpenShellAdapter().run_task(task)
    output_dir = Path("storage/sandbox_outputs") / task.thread_id / task.task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
