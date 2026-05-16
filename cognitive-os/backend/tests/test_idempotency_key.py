"""Property tests for `ActionRequestService._idempotency_key`.

The key is the hinge of the entire dedup story: aplicación + UNIQUE index +
worker idempotency all depend on it being stable for the same payload and
distinct across different payloads. These properties verify the contract
without committing to a specific hash output.
"""

from __future__ import annotations

from cognitive_os.actions.service import _idempotency_key


def test_idempotency_key_is_stable_for_same_inputs() -> None:
    payload = {"alpha": 1, "beta": [2, 3], "gamma": {"nested": True}}
    assert _idempotency_key("computer_organize", payload) == _idempotency_key(
        "computer_organize", payload
    )


def test_idempotency_key_is_independent_of_key_ordering() -> None:
    a = {"alpha": 1, "beta": 2, "gamma": 3}
    b = {"gamma": 3, "alpha": 1, "beta": 2}
    assert _idempotency_key("computer_organize", a) == _idempotency_key("computer_organize", b)


def test_idempotency_key_changes_when_action_type_changes() -> None:
    payload = {"alpha": 1}
    assert _idempotency_key("computer_organize", payload) != _idempotency_key(
        "browser_preview", payload
    )


def test_idempotency_key_changes_when_payload_changes() -> None:
    a = {"alpha": 1}
    b = {"alpha": 2}
    assert _idempotency_key("computer_organize", a) != _idempotency_key("computer_organize", b)


def test_idempotency_key_handles_unicode_and_special_chars() -> None:
    a = {"texto": "café", "emoji": "🎯"}
    b = {"emoji": "🎯", "texto": "café"}
    assert _idempotency_key("doc", a) == _idempotency_key("doc", b)
    assert _idempotency_key("doc", a) != _idempotency_key("doc", {"texto": "cafe"})


def test_idempotency_key_distinguishes_nested_orderings() -> None:
    """Lists are ordered: [1,2] != [2,1] even though both have same elements."""
    a = {"items": [1, 2]}
    b = {"items": [2, 1]}
    assert _idempotency_key("doc", a) != _idempotency_key("doc", b)


def test_idempotency_key_is_hex_string_of_expected_length() -> None:
    key = _idempotency_key("foo", {"bar": 1})
    assert len(key) == 64  # sha256 hex digest
    assert all(ch in "0123456789abcdef" for ch in key)
