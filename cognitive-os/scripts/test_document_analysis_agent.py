from __future__ import annotations

import argparse
import asyncio
from typing import cast
from uuid import uuid4

from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisMode,
    DocumentAnalysisTask,
)
from cognitive_os.deepagents.document_analysis.service import DocumentAnalysisService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cognitive OS document analysis agent.")
    parser.add_argument("--doc-id", action="append", required=True)
    parser.add_argument("--mode", action="append", default=[])
    parser.add_argument("--query", required=True)
    parser.add_argument("--thread-id", default="manual-test")
    args = parser.parse_args()

    modes = args.mode or ["full_report"]
    task = DocumentAnalysisTask(
        task_id=str(uuid4()),
        thread_id=args.thread_id,
        user_id="manual-cli",
        case_id=None,
        doc_ids=args.doc_id,
        query=args.query,
        modes=[cast(DocumentAnalysisMode, mode) for mode in modes],
        output_formats=["json", "markdown"],
    )
    result = asyncio.run(DocumentAnalysisService().run_analysis(task))
    print(result.executive_summary)
    print("status:", result.status)
    print("human_review_required:", result.human_review_required)
    print("generated_files:", ", ".join(result.generated_files) or "none")


if __name__ == "__main__":
    main()
