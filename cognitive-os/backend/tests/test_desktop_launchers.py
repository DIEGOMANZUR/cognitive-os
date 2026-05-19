from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_desktop_launchers.sh"


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    _make_executable(path)


def _write_launchers(desktop: Path, repo_root: Path, *, omit: str | None = None) -> Path:
    master = desktop / "cognitive-os.sh"
    opener = desktop / "cognitive-os-open-terminal.sh"
    _write_executable(
        master,
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -uo pipefail",
                'case "${1:-}" in start|restart|stop|status) exit 0;; *) exit 2;; esac',
                "",
            ]
        ),
    )
    _write_executable(
        opener,
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -uo pipefail",
                'title="$1"',
                'script="$2"',
                "shift 2",
                'exec bash "$script" "$@"',
                "",
            ]
        ),
    )

    mapping = {
        "Levantar Cognitive OS": "start",
        "Reiniciar Cognitive OS": "restart",
        "Detener Cognitive OS": "stop",
        "Estado Cognitive OS": "status",
    }
    for label, mode in mapping.items():
        if label == omit:
            continue
        wrapper = desktop / f"{label}.sh"
        _write_executable(
            wrapper,
            f'#!/usr/bin/env bash\nset -uo pipefail\nMASTER="{master}"\n"${{MASTER}}" {mode}\n',
        )
        desktop_file = desktop / f"{label}.desktop"
        desktop_file.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={label}",
                    f'Exec={opener} "{label}" "{wrapper}"',
                    "Terminal=false",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        _make_executable(desktop_file)

    return master


def test_verify_desktop_launchers_accepts_valid_overridden_desktop(tmp_path: Path) -> None:
    desktop = tmp_path / "desktop"
    repo_root = tmp_path / "repo"
    (repo_root / "infra").mkdir(parents=True)
    (repo_root / "backend").mkdir()
    (repo_root / "frontend").mkdir()
    (repo_root / "infra" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (repo_root / "backend" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo_root / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    desktop.mkdir()
    master = _write_launchers(desktop, repo_root)

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT)],
        check=False,
        env={
            **os.environ,
            "COGOS_DESKTOP_DIR": str(desktop),
            "COGOS_MASTER": str(master),
            "COGOS_REPO_ROOT": str(repo_root),
            "COGOS_OPEN_TERMINAL": str(desktop / "cognitive-os-open-terminal.sh"),
        },
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Desktop launchers OK" in result.stdout


def test_verify_desktop_launchers_fails_when_wrapper_missing(tmp_path: Path) -> None:
    desktop = tmp_path / "desktop"
    repo_root = tmp_path / "repo"
    (repo_root / "infra").mkdir(parents=True)
    (repo_root / "backend").mkdir()
    (repo_root / "frontend").mkdir()
    (repo_root / "infra" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (repo_root / "backend" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo_root / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    desktop.mkdir()
    master = _write_launchers(desktop, repo_root, omit="Estado Cognitive OS")

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT)],
        check=False,
        env={
            **os.environ,
            "COGOS_DESKTOP_DIR": str(desktop),
            "COGOS_MASTER": str(master),
            "COGOS_REPO_ROOT": str(repo_root),
            "COGOS_OPEN_TERMINAL": str(desktop / "cognitive-os-open-terminal.sh"),
        },
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Estado Cognitive OS.sh" in result.stderr
