from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cognitive_os.core.config import settings

_bearer = HTTPBearer(auto_error=False)
_bearer_dependency = Depends(_bearer)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    is_admin: bool
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def create_access_token(
    *,
    user_id: str,
    roles: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None = None,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    token_roles = _normalize_roles(roles if roles is not None else settings.auth_default_roles)
    payload = {
        "sub": user_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "roles": sorted(token_roles),
    }
    return encode_jwt(payload)


def encode_jwt(payload: dict[str, Any]) -> str:
    if settings.jwt_algorithm != "HS256":
        msg = "Only HS256 JWT is supported by local auth."
        raise ValueError(msg)
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_jwt(token: str, *, now: datetime | None = None) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature = token.split(".")
    except ValueError as exc:
        msg = "Malformed JWT."
        raise ValueError(msg) from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        msg = "Invalid JWT signature."
        raise ValueError(msg)

    header = _loads_b64_json(header_b64)
    if header.get("alg") != "HS256":
        msg = "Unsupported JWT algorithm."
        raise ValueError(msg)

    payload = _loads_b64_json(payload_b64)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int | float):
        msg = "JWT exp claim is required."
        raise ValueError(msg)
    active_now = now or datetime.now(UTC)
    if active_now.timestamp() >= expires_at:
        msg = "JWT has expired."
        raise ValueError(msg)
    if not payload.get("sub"):
        msg = "JWT sub claim is required."
        raise ValueError(msg)
    return payload


async def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
        )
    try:
        payload = decode_jwt(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc

    user_id = str(payload["sub"])
    roles = _roles_from_payload(payload)
    is_admin = _is_admin_user(user_id, roles)
    return AuthenticatedUser(user_id=user_id, is_admin=is_admin, roles=roles)


async def require_admin_user(
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def require_langsmith_api_access(
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
) -> AuthenticatedUser:
    """Optional extra gate for LangSmith read APIs (runs, projects, tracing status)."""
    if not settings.langsmith_endpoints_require_admin:
        return user
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for LangSmith API",
        )
    return user


def _is_admin_user(user_id: str, roles: frozenset[str]) -> bool:
    if roles.intersection(settings.auth_admin_roles):
        return True
    if not settings.admin_user_ids:
        return False
    try:
        numeric_user_id = int(user_id)
    except ValueError:
        return False
    return numeric_user_id in settings.admin_user_ids


def _roles_from_payload(payload: dict[str, Any]) -> frozenset[str]:
    return _normalize_roles(payload.get("roles") or payload.get("role") or [])


def _normalize_roles(raw_roles: object) -> frozenset[str]:
    if isinstance(raw_roles, str):
        items: object = [raw_roles]
    else:
        items = raw_roles
    if not isinstance(items, (list, tuple, set, frozenset)):
        return frozenset()
    roles = {role.strip().lower() for role in items if isinstance(role, str) and role.strip()}
    return frozenset(roles)


def _sign(signing_input: str) -> str:
    key = settings.jwt_secret.get_secret_value().encode()
    digest = hmac.new(key, signing_input.encode(), hashlib.sha256).digest()
    return _b64_bytes(digest)


def _b64_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return _b64_bytes(payload)


def _loads_b64_json(value: str) -> dict[str, Any]:
    decoded = base64.urlsafe_b64decode(_pad_b64(value)).decode()
    loaded = json.loads(decoded)
    if not isinstance(loaded, dict):
        msg = "JWT part must decode to an object."
        raise ValueError(msg)
    return loaded


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _pad_b64(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return padded.encode()
