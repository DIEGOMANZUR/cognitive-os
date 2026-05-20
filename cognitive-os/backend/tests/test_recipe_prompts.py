from __future__ import annotations

import json

import pytest

from cognitive_os.deepagents.recipe_prompts import (
    RecipeParseError,
    build_recipe_messages,
    parse_recipe_response,
    serialize_trajectory,
)


def test_parse_recipe_response_accepts_skip_signal() -> None:
    parsed = parse_recipe_response('{"skip": true, "reason": "trivial"}')

    assert parsed["skip"] is True
    assert parsed["reason"] == "trivial"


def test_parse_recipe_response_validates_required_keys() -> None:
    with pytest.raises(RecipeParseError, match="required keys"):
        parse_recipe_response('{"title": "ok", "summary": "ok"}')  # no steps


def test_parse_recipe_response_requires_non_empty_steps() -> None:
    payload = {"title": "ok", "summary": "ok", "steps": []}
    with pytest.raises(RecipeParseError, match="steps"):
        parse_recipe_response(json.dumps(payload))


def test_parse_recipe_response_rejects_invalid_json() -> None:
    with pytest.raises(RecipeParseError, match="not valid JSON"):
        parse_recipe_response("not a json {")


def test_parse_recipe_response_rejects_empty_input() -> None:
    with pytest.raises(RecipeParseError, match="Empty"):
        parse_recipe_response("")


def test_parse_recipe_response_tolerates_markdown_fences() -> None:
    fenced = (
        "```json\n"
        + json.dumps(
            {
                "title": "Hacer X",
                "summary": "Resumen.",
                "steps": [{"step": 1, "tool": "t", "purpose": "p"}],
            }
        )
        + "\n```"
    )

    parsed = parse_recipe_response(fenced)

    assert parsed["title"] == "Hacer X"


def test_parse_recipe_response_truncates_long_title() -> None:
    long = "x" * 500
    parsed = parse_recipe_response(
        json.dumps(
            {
                "title": long,
                "summary": "ok",
                "steps": [{"step": 1, "tool": "t", "purpose": "p"}],
            }
        )
    )

    assert len(parsed["title"]) == 200


def test_build_recipe_messages_starts_with_system() -> None:
    msgs = build_recipe_messages("Trayectoria de prueba")

    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "Trayectoria de prueba" in msgs[-1]["content"]


def test_serialize_trajectory_includes_tool_metadata() -> None:
    text = serialize_trajectory(
        job_type="deepagent_research",
        agent_name="research",
        duration_seconds=85.0,
        events=[
            {
                "event_type": "tool_invoked",
                "message": "hello world",
                "metadata": {"tool": "search_local_docs"},
            },
            {
                "event_type": "agent_finished",
                "message": "done",
                "metadata": {},
            },
        ],
    )

    assert "agent=research" in text
    assert "job_type=deepagent_research" in text
    assert "duration=85s" in text
    assert "tool=search_local_docs" in text
