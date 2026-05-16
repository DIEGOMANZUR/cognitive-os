from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.actions.computer import ComputerActionService
from cognitive_os.actions.schemas import ComputerInventoryRequest
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def test_computer_inventory_scans_allowed_root_and_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "home"
    storage = tmp_path / "storage"
    root.mkdir()
    (root / "contract.pdf").write_text("pdf", encoding="utf-8")
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
    (root / ".env").write_text("SECRET=value", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "app.py").write_text("print('hi')", encoding="utf-8")

    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            local_storage_dir=str(storage),
        )
    )

    result = service.build_inventory(
        ComputerInventoryRequest(root_path=str(root), recursive=True, include_hidden=False)
    )

    assert result.status == "completed"
    assert result.file_count == 3
    assert result.by_category["PDFs"] == 1
    assert result.by_category["Documents"] == 1
    assert result.by_category["Code"] == 1
    paths = {entry.relative_path for entry in result.entries}
    assert paths == {"contract.pdf", "notes.txt", "nested/app.py"}
    assert any("skipped_sensitive_path:.env" in warning for warning in result.warnings)
    assert result.inventory_path is not None
    inventory = Path(result.inventory_path)
    assert inventory.exists()
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["file_count"] == 3


def test_computer_inventory_can_include_sha256(tmp_path: Path) -> None:
    root = tmp_path / "home"
    root.mkdir()
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            local_storage_dir=str(tmp_path / "storage"),
        )
    )

    result = service.build_inventory(
        ComputerInventoryRequest(
            root_path=str(root),
            include_sha256=True,
        )
    )

    assert result.status == "completed"
    assert result.entries[0].sha256 is not None
    assert len(result.entries[0].sha256 or "") == 64


def test_computer_inventory_truncates_at_limit(tmp_path: Path) -> None:
    root = tmp_path / "home"
    root.mkdir()
    for index in range(5):
        (root / f"file-{index}.txt").write_text(str(index), encoding="utf-8")
    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            local_storage_dir=str(tmp_path / "storage"),
        )
    )

    result = service.build_inventory(ComputerInventoryRequest(root_path=str(root), max_files=2))

    assert result.status == "completed"
    assert result.file_count == 2
    assert "inventory_truncated_at_2_files" in result.warnings


def test_computer_inventory_blocks_outside_allowed_roots(tmp_path: Path) -> None:
    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path / "allowed")],
        )
    )

    result = service.build_inventory(ComputerInventoryRequest(root_path=str(tmp_path)))

    assert result.status == "blocked"
    assert result.reason == "computer path is outside allowed roots."


@pytest.mark.asyncio
async def test_computer_inventory_endpoint_uses_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeComputerService:
        def build_inventory(self, request: ComputerInventoryRequest):
            assert request.root_path == "/tmp/example"
            from cognitive_os.actions.schemas import ComputerInventoryResult

            return ComputerInventoryResult(
                status="completed",
                root_path=request.root_path,
                file_count=0,
            )

    monkeypatch.setattr(api_app, "ComputerActionService", lambda: _FakeComputerService())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/computer/inventory",
            json={"root_path": "/tmp/example"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_computer_inventory_endpoint_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/computer/inventory",
            json={"root_path": "/tmp/example"},
        )

    assert response.status_code in (401, 403)
