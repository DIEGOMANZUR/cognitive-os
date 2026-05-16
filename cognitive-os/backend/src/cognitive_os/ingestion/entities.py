from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedEntity:
    kind: str
    value: str
    start: int
    end: int


ENTITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("date", re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")),
    ("rut", re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b")),
    ("rit", re.compile(r"\b(?:RIT|RUC)\s*[:#-]?\s*[A-Z]?\s*\d{1,7}[-/]\d{4}\b", re.IGNORECASE)),
    ("amount", re.compile(r"\b(?:CLP\s*)?\$\s?[\d.]+(?:,\d+)?\b|\bCLP\s+[\d.]+(?:,\d+)?\b")),
    ("article", re.compile(r"\b(?:articulo|artículo|art\.)\s+\d+[A-Za-z]?\b", re.IGNORECASE)),
)


def extract_entities(text: str) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, int, int]] = set()
    for kind, pattern in ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            key = (kind, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                ExtractedEntity(
                    kind=kind,
                    value=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )
    return sorted(entities, key=lambda entity: (entity.start, entity.end, entity.kind))
