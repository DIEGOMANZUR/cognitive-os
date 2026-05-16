from __future__ import annotations

import pytest


def test_openshell_worker_integration_skips_without_worker() -> None:
    pytest.skip("Requires a running Celery worker and OpenShell gateway.")
