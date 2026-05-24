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
    assert "sync_first: false" in mail_view


def test_full_qa_builds_next_in_isolated_dist_dir() -> None:
    full_qa = (PROJECT_ROOT / "scripts" / "full-qa.sh").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    eslint_config = (FRONTEND_ROOT / "eslint.config.mjs").read_text(encoding="utf-8")

    assert 'QA_NEXT_DIST=".next-qa"' in full_qa
    assert 'NEXT_DIST_DIR="$QA_NEXT_DIST" npm run build' in full_qa
    assert 'cleanup_qa_artifacts\ncd "$ROOT/backend"' in full_qa
    assert '".next-qa/**"' in eslint_config
    assert "frontend/.next-qa/" in gitignore


def test_full_qa_treats_alembic_check_as_hard_gate_when_db_is_configured() -> None:
    full_qa = (PROJECT_ROOT / "scripts" / "full-qa.sh").read_text(encoding="utf-8")

    assert "uv run alembic check" in full_qa
    assert "WARN: alembic check" not in full_qa
    assert "no pasó o no se pudo conectar" not in full_qa


def test_full_e2e_script_exists_for_playwright_gate() -> None:
    full_e2e = (PROJECT_ROOT / "scripts" / "full-e2e.sh").read_text(encoding="utf-8")
    global_setup = (FRONTEND_ROOT / "tests" / "e2e" / "_global-setup.ts").read_text(
        encoding="utf-8"
    )

    assert "npx playwright test" in full_e2e
    assert "curl -fsS" in full_e2e
    assert "Access-Control-Request-Method: GET" in full_e2e
    assert "API CORS does not allow frontend origin" in full_e2e
    assert "COGOS_E2E_NPM_CI:-0" in full_e2e
    assert "skip npm ci; server must stay alive" in full_e2e
    assert "POST /auth/local-token" in full_e2e
    assert "create_access_token" not in full_e2e
    assert "/auth/local-token" in global_setup
    assert full_e2e.index("COGOS_E2E_NPM_CI") < full_e2e.index('curl -fsS "$API_BASE/health"')


def test_full_qa_live_requires_external_opt_in() -> None:
    full_qa_live = (PROJECT_ROOT / "scripts" / "full-qa-live.sh").read_text(encoding="utf-8")

    assert "LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh" in full_qa_live
    assert 'if [[ "${LIVE_TESTS_ENABLED:-}" != "1" ]]' in full_qa_live
    assert "export LIVE_TESTS_ENABLED=1" not in full_qa_live
    assert "uv run pytest -m live_readonly tests/live -v" in full_qa_live


def test_full_testsprite_batches_and_redacts_secret_config() -> None:
    full_testsprite = (PROJECT_ROOT / "scripts" / "full-testsprite.sh").read_text(encoding="utf-8")
    canonical_plan = PROJECT_ROOT / "qa" / "testsprite" / "frontend_commercial_plan.json"

    assert "API_KEY or TESTSPRITE_API_KEY" in full_testsprite
    assert "TESTSPRITE_PACKAGE" in full_testsprite
    assert "@testsprite/testsprite-mcp@0.0.19" in full_testsprite
    assert "@testsprite/testsprite-mcp@latest" not in full_testsprite
    assert "TESTSPRITE_CANONICAL_PLAN" in full_testsprite
    assert canonical_plan.exists()
    assert "TESTSPRITE_BATCH_SIZE" in full_testsprite
    assert "batched_results.json" in full_testsprite
    assert 'envs["API_KEY"] = "<redacted>"' in full_testsprite
    assert "Target connect failed" in full_testsprite
    assert "TESTSPRITE_BATCH_IDLE_TIMEOUT_SECONDS" in full_testsprite
    assert "TESTSPRITE_BATCH_RETRIES" in full_testsprite
    assert "TESTSPRITE_TEST_IDS" in full_testsprite
    assert "TESTSPRITE_CLEAN_GENERATED" in full_testsprite
    assert "start_new_session=True" in full_testsprite
    assert "SPLIT after failure" in full_testsprite
    assert "mcp.log" in full_testsprite
    assert 'data["proxy"] = "<redacted>"' in full_testsprite
    assert "Do not create email drafts, send email" in full_testsprite


def test_commercial_qa_scripts_and_fixture_contract_are_versioned() -> None:
    commercial_qa = (PROJECT_ROOT / "scripts" / "full-commercial-qa.sh").read_text(encoding="utf-8")
    secret_scan = (PROJECT_ROOT / "scripts" / "scan-local-artifacts-for-secrets.sh").read_text(
        encoding="utf-8"
    )
    fixture_api = (
        PROJECT_ROOT / "backend" / "src" / "cognitive_os" / "api" / "test_fixtures.py"
    ).read_text(encoding="utf-8")
    critical_spec = (
        FRONTEND_ROOT / "tests" / "e2e" / "commercial-fixtures-critical.spec.ts"
    ).read_text(encoding="utf-8")

    assert "bash scripts/full-qa.sh" in commercial_qa
    assert "scripts/probe-qa-stack-health.py" in commercial_qa
    assert "scripts/scan-local-artifacts-for-secrets.sh" in commercial_qa
    assert "scripts/full-testsprite.sh" in commercial_qa
    assert "TESTSPRITE_API_KEY" in commercial_qa
    assert "NOT_RUN_NO_API_KEY" in commercial_qa
    assert "did not reuse stale ignored TestSprite results" in commercial_qa
    assert "testsprite_tests/tmp" in secret_scan
    assert "backend/storage/mail_digests" in secret_scan
    assert "node_modules" in secret_scan
    assert "5_000_000" not in secret_scan
    assert "for line_no, line in enumerate(handle" in secret_scan
    assert "url-credential" in secret_scan
    assert "sk-user-" in secret_scan
    assert "APP_ENV=test" in fixture_api
    assert "COGOS_TEST_FIXTURES_ENABLED" in fixture_api
    assert "mail_digest_read_only" in fixture_api
    for flow in (
        "health general",
        "jobs dashboard",
        "jobs lifecycle",
        "failed job UX",
        "approvals/action lifecycle",
        "mail read-only",
        "zero-friction dedicated local",
        "malformed API state",
        "mobile-friendly",
    ):
        assert flow in critical_spec


def test_user_guide_matches_dark_only_frontend_contract() -> None:
    user_guide = (PROJECT_ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    layout = (FRONTEND_ROOT / "app" / "layout.tsx").read_text(encoding="utf-8")
    settings = (FRONTEND_ROOT / "app" / "views" / "SettingsView.tsx").read_text(encoding="utf-8")

    assert 'data-theme="dark"' in layout
    assert "tema claro se retiró" in settings
    assert "tema claro/oscuro" not in user_guide
    assert "alterna tema" not in user_guide
