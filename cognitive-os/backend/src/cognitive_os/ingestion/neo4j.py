from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import SecretStr

from cognitive_os.core.config import settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.ingestion.entities import ExtractedEntity


class Neo4jGraphReader:
    """Read-only Neo4j client using pre-defined safe Cypher queries."""

    def __init__(
        self,
        *,
        http_url: str,
        user: str,
        password: SecretStr,
        timeout: float | None = None,
    ) -> None:
        self._http_url = http_url.rstrip("/")
        self._user = user
        self._password = password
        self._timeout = timeout or settings.http_timeout_seconds

    def is_available(self) -> bool:
        try:
            response = httpx.get(
                f"{self._http_url}/db/neo4j/tx",
                auth=(self._user, self._password.get_secret_value()),
                timeout=3.0,
            )
            return response.status_code < 500
        except Exception:
            return False

    def find_entities(self, name_fragment: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._run(
            "MATCH (e:Entity) WHERE toLower(e.value) CONTAINS toLower($fragment) "
            "RETURN e.kind AS kind, e.value AS value LIMIT $limit",
            {"fragment": name_fragment, "limit": limit},
        )
        return [{"kind": r.get("kind"), "value": r.get("value")} for r in rows]

    def find_docs_for_entity(self, entity_value: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._run(
            "MATCH (d:Document)-[:MENTIONS]->(e:Entity {value: $value}) "
            "RETURN d.doc_id AS doc_id, d.source_path AS source_path LIMIT $limit",
            {"value": entity_value, "limit": limit},
        )
        return [{"doc_id": r.get("doc_id"), "source_path": r.get("source_path")} for r in rows]

    def find_related_entities(self, doc_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._run(
            "MATCH (d:Document {doc_id: $doc_id})-[:MENTIONS]->(e:Entity) "
            "RETURN e.kind AS kind, e.value AS value LIMIT $limit",
            {"doc_id": doc_id, "limit": limit},
        )
        return [{"kind": r.get("kind"), "value": r.get("value")} for r in rows]

    def _run(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = retry_transient_http(
            lambda: httpx.post(
                f"{self._http_url}/db/neo4j/tx/commit",
                auth=(self._user, self._password.get_secret_value()),
                json={"statements": [{"statement": cypher, "parameters": params}]},
                timeout=self._timeout,
            )
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            msg = f"Neo4j read failed: {payload['errors']}"
            raise RuntimeError(msg)
        results = payload.get("results", [{}])[0]
        columns = results.get("columns", [])
        rows = results.get("data", [])
        return [dict(zip(columns, row["row"], strict=False)) for row in rows]


def _build_default_neo4j_reader() -> Neo4jGraphReader | None:
    if settings.neo4j_password.get_secret_value() == "CHANGEME":
        return None
    return Neo4jGraphReader(
        http_url=f"http://localhost:{settings.neo4j_http_port}",
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )


class Neo4jEntityWriter:
    """Best-effort entity writer for Neo4j's transactional HTTP endpoint."""

    def __init__(
        self,
        *,
        http_url: str,
        user: str,
        password: SecretStr,
        timeout: float | None = None,
    ) -> None:
        self._http_url = http_url.rstrip("/")
        self._user = user
        self._password = password
        self._timeout = timeout or settings.http_timeout_seconds

    def write_entities(
        self,
        *,
        doc_id: str,
        source_path: str,
        entities: Sequence[ExtractedEntity],
    ) -> None:
        if not entities:
            return

        statements = [
            {
                "statement": """
                MERGE (d:Document {doc_id: $doc_id})
                SET d.source_path = $source_path
                WITH d
                UNWIND $entities AS entity
                MERGE (e:Entity {kind: entity.kind, value: entity.value})
                MERGE (d)-[:MENTIONS]->(e)
                """,
                "parameters": {
                    "doc_id": doc_id,
                    "source_path": source_path,
                    "entities": [
                        {"kind": entity.kind, "value": entity.value} for entity in entities
                    ],
                },
            }
        ]
        response = retry_transient_http(
            lambda: httpx.post(
                f"{self._http_url}/db/neo4j/tx/commit",
                auth=(self._user, self._password.get_secret_value()),
                json={"statements": statements},
                timeout=self._timeout,
            )
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            msg = f"Neo4j entity write failed: {payload['errors']}"
            raise RuntimeError(msg)
