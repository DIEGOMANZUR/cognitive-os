"""Live smoke: GoDaddy credentials authenticate against a read-only endpoint.

Read-only: a single `GET /v1/domains`. Never touches DNS records — DNS changes
remain gated by preview + dry-run + approval. This only proves the sso-key pair
is valid so the operator is not surprised mid-task.
"""

from __future__ import annotations

import httpx
import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def test_live_godaddy_lists_domains_readonly() -> None:
    if not settings.godaddy_enabled:
        pytest.skip("GODADDY_ENABLED is false")
    api_key = settings.godaddy_api_key.get_secret_value()
    api_secret = settings.godaddy_api_secret.get_secret_value()
    if api_key in {"", "CHANGEME"} or api_secret in {"", "CHANGEME"}:
        pytest.skip("GoDaddy API key/secret not configured")

    url = f"{settings.godaddy_base_url.rstrip('/')}/v1/domains"
    headers = {
        "Authorization": f"sso-key {api_key}:{api_secret}",
        "Accept": "application/json",
    }
    response = httpx.get(
        url,
        headers=headers,
        params={"limit": 1},
        timeout=settings.http_timeout_seconds,
    )

    # 200 = creds valid. Any other code: fail with the status only (never echo
    # the Authorization header or response body, which may carry account data).
    assert response.status_code == 200, (
        f"GoDaddy /v1/domains returned HTTP {response.status_code} "
        "(credentials invalid or API unreachable)"
    )
    assert isinstance(response.json(), list)
