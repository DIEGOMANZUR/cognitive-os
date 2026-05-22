from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


def test_next_config_sets_security_headers() -> None:
    config = (FRONTEND_ROOT / "next.config.mjs").read_text(encoding="utf-8")

    assert "poweredByHeader: false" in config
    assert "NEXT_DIST_DIR" in config
    assert "distDir" in config
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Cross-Origin-Opener-Policy",
        "Permissions-Policy",
    ):
        assert header in config


def test_service_worker_keeps_api_like_routes_network_only() -> None:
    service_worker = (FRONTEND_ROOT / "public" / "sw.js").read_text(encoding="utf-8")

    assert re.search(r'CACHE_VERSION = "cogos-v\d{4}-\d{2}-\d{2}[-\w]*"', service_worker)
    assert "COGOS_SKIP_WAITING" in service_worker
    for prefix in ("/actions", "/api", "/health", "/mail", "/research", "/threads"):
        assert f'"{prefix}"' in service_worker

    network_guard = service_worker.index("NETWORK_ONLY_PREFIXES.some")
    asset_guard = service_worker.index("ASSET_PATTERN.test")
    navigation_guard = service_worker.index('request.mode === "navigate"')
    assert network_guard < asset_guard < navigation_guard


def test_pwa_component_exposes_offline_and_update_states() -> None:
    pwa = (FRONTEND_ROOT / "app" / "components" / "PWA.tsx").read_text(encoding="utf-8")

    assert "updateReady" in pwa
    assert "navigator.onLine" in pwa
    assert "controllerchange" in pwa
    assert "Sin conexión" in pwa
    assert "Actualización disponible" in pwa


def test_mail_view_uses_worker_dispatch_for_manual_sync() -> None:
    mail_view = (FRONTEND_ROOT / "app" / "views" / "MailInboxView.tsx").read_text(encoding="utf-8")

    assert '"/mail/sync/dispatch"' in mail_view
    assert 'client.post<MailSyncResult>("/mail/sync"' not in mail_view
    assert "MailSyncDispatchResponse" in mail_view


def test_full_qa_builds_next_in_isolated_dist_dir() -> None:
    full_qa = (PROJECT_ROOT / "scripts" / "full-qa.sh").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert 'QA_NEXT_DIST=".next-qa"' in full_qa
    assert 'NEXT_DIST_DIR="$QA_NEXT_DIST" npm run build' in full_qa
    assert "frontend/.next-qa/" in gitignore
