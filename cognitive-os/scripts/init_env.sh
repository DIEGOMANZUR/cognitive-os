#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Created .env from .env.example"
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 or python is required to initialize .env" >&2
  exit 1
fi

ENV_FILE="${ENV_FILE}" ENV_EXAMPLE="${ENV_EXAMPLE}" "${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import quote


env_path = Path(os.environ["ENV_FILE"])
example_path = Path(os.environ["ENV_EXAMPLE"])
lines = env_path.read_text(encoding="utf-8").splitlines()
example_lines = example_path.read_text(encoding="utf-8").splitlines()


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def parse_env(lines: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


values = parse_env(lines)
example_values = parse_env(example_lines)
for key, value in example_values.items():
    values.setdefault(key, value)
values.setdefault("WEAVIATE_HTTP_PORT", "8081")
values.setdefault("WEAVIATE_GRPC_PORT", "50052")
values.setdefault("NEO4J_HTTP_PORT", "7475")
values.setdefault("NEO4J_BOLT_PORT", "7688")
generated_keys: list[str] = []
for key in ("JWT_SECRET", "POSTGRES_PASSWORD", "NEO4J_PASSWORD", "WEAVIATE_API_KEY"):
    if values.get(key, "CHANGEME") == "CHANGEME":
        values[key] = generate_secret()
        generated_keys.append(key)

postgres_user = values.get("POSTGRES_USER", "cogos")
postgres_password = quote(values["POSTGRES_PASSWORD"], safe="")
postgres_host = values.get("POSTGRES_HOST", "localhost")
postgres_port = values.get("POSTGRES_PORT", "5432")
postgres_db = values.get("POSTGRES_DB", "cognitive_os")
values["DATABASE_URL"] = (
    f"postgresql+asyncpg://{postgres_user}:{postgres_password}"
    f"@{postgres_host}:{postgres_port}/{postgres_db}"
)
values.setdefault("CELERY_BROKER_URL", values.get("REDIS_URL", "redis://localhost:6379/0"))
values.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
values["WEAVIATE_URL"] = f"http://localhost:{values['WEAVIATE_HTTP_PORT']}"
values["NEO4J_URI"] = f"bolt://localhost:{values['NEO4J_BOLT_PORT']}"

seen_keys: set[str] = set()
updated_lines: list[str] = []
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        updated_lines.append(line)
        continue
    key, _value = line.split("=", 1)
    if key in values:
        updated_lines.append(f"{key}={values[key]}")
        seen_keys.add(key)
    else:
        updated_lines.append(line)

for key, value in values.items():
    if key not in seen_keys:
        updated_lines.append(f"{key}={value}")

env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

if generated_keys:
    print("Generated secrets for: " + ", ".join(generated_keys))
else:
    print("Secrets already initialized")
print("DATABASE_URL updated from POSTGRES_PASSWORD")
PY
