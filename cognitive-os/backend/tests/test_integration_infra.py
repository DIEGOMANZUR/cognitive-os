from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


def _load_env() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


@pytest.mark.asyncio
async def test_postgres_connection() -> None:
    env = _load_env()
    database_url = env.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    assert database_url

    parsed_database_url = urlparse(database_url)
    asyncpg_database_url = parsed_database_url._replace(scheme="postgresql").geturl()
    connection = await asyncpg.connect(asyncpg_database_url)
    try:
        value = await connection.fetchval("SELECT 1")
    finally:
        await connection.close()

    assert value == 1


def test_redis_connection() -> None:
    env = _load_env()
    redis_url = urlparse(
        env.get("REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    )
    host = redis_url.hostname or "localhost"
    port = redis_url.port or 6379

    with socket.create_connection((host, port), timeout=5) as client:
        client.sendall(b"*1\r\n$4\r\nPING\r\n")
        response = client.recv(128)

    assert response.startswith(b"+PONG")


def test_weaviate_connection() -> None:
    env = _load_env()
    base_url = env.get("WEAVIATE_URL", os.environ.get("WEAVIATE_URL", "http://localhost:8080"))
    api_key = env.get("WEAVIATE_API_KEY", os.environ.get("WEAVIATE_API_KEY", ""))

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = httpx.get(f"{base_url}/v1/.well-known/ready", headers=headers, timeout=5)

    assert response.status_code == 200


def test_neo4j_connection() -> None:
    env = _load_env()
    user = env.get("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    password = env.get("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", ""))
    http_port = env.get("NEO4J_HTTP_PORT", os.environ.get("NEO4J_HTTP_PORT", "7475"))

    response = httpx.post(
        f"http://localhost:{http_port}/db/neo4j/tx/commit",
        auth=(user, password),
        json={"statements": [{"statement": "RETURN 1 AS ok"}]},
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["errors"] == []
    assert payload["results"][0]["data"][0]["row"] == [1]
