from pathlib import Path

import pytest
from pydantic import ValidationError

from cognitive_os.core.config import Settings, parse_cors_origins, parse_int_csv, parse_str_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_loads_env_example() -> None:
    loaded_settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert loaded_settings.environment == "development"
    assert loaded_settings.primary_llm.provider == "openai_compatible"
    assert loaded_settings.primary_llm.api_key.get_secret_value() == "CHANGEME"
    assert loaded_settings.primary_llm_reasoning_effort == ""
    assert loaded_settings.primary_llm_thinking_enabled is False
    assert loaded_settings.perplexity_api_key.get_secret_value() == "CHANGEME"
    assert loaded_settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert loaded_settings.admin_user_ids == []
    assert loaded_settings.auth_default_roles == ["operator"]
    assert loaded_settings.auth_admin_roles == ["admin"]
    assert loaded_settings.langsmith_endpoints_require_admin is True
    assert loaded_settings.health_component_timeout_seconds == 3.0
    assert loaded_settings.cors_allow_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3101",
        "http://127.0.0.1:3101",
    ]
    assert loaded_settings.browser_automation_provider == "playwright"
    assert loaded_settings.browser_headless_default is True
    assert loaded_settings.enable_computer_actions is False
    assert loaded_settings.computer_allowed_roots == []
    assert loaded_settings.computer_organize_dry_run_only is True
    assert loaded_settings.computer_max_files_per_plan == 500
    assert loaded_settings.gmail_scopes == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert loaded_settings.microsoft_mail_scopes == ["Mail.ReadBasic", "offline_access"]
    assert loaded_settings.mail_imap_timeout_seconds == 30
    assert loaded_settings.mail_smtp_timeout_seconds == 30
    assert loaded_settings.mail_background_sync_enabled is False
    assert loaded_settings.mail_fetch_max_per_folder == 50
    assert loaded_settings.mail_gmail_monitor_labels == ["TODOS", "SPAM"]
    assert loaded_settings.mail_godaddy_monitor_folders == ["Spam"]
    assert loaded_settings.mail_digest_hours_local == ["10", "20"]
    assert loaded_settings.mail_digest_timezone == "America/Santiago"
    assert loaded_settings.mail_digest_max_messages == 50
    assert loaded_settings.mail_allow_explicit_send is False
    assert loaded_settings.mcp_call_timeout_seconds == 30
    assert loaded_settings.mcp_inventory_timeout_seconds == 30
    assert loaded_settings.research_persistence_backend == "memory"


def test_dedicated_local_full_autonomy_overrides_legacy_friction_flags() -> None:
    loaded_settings = Settings(
        _env_file=None,
        operator_profile="dedicated_local",
        require_human_approval_for_external_actions=True,
        approval_require_four_eyes=True,
        tools_readonly_mode=True,
        enable_kimi_webbridge=False,
        kimi_webbridge_allowed_domains=[],
        kimi_webbridge_allow_mutations=False,
        kimi_webbridge_require_approval=True,
        enable_computer_actions=False,
        computer_allowed_roots=[],
        computer_organize_dry_run_only=True,
        enable_browser_automation=False,
        browser_allowed_domains=[],
        browser_allow_headed=False,
        browser_allow_vision=False,
        enable_browser_ssrf_check=True,
        enable_email_send=False,
        mail_require_approval_for_send=True,
        enable_google_calendar=True,
        enable_google_drive=True,
        google_client_id="client-id",
        google_client_secret="client-secret",  # pragma: allowlist secret
    )

    assert loaded_settings.local_autonomy_mode == "full"
    assert loaded_settings.require_human_approval_for_external_actions is False
    assert loaded_settings.approval_require_four_eyes is False
    assert loaded_settings.tools_readonly_mode is False
    assert loaded_settings.enable_kimi_webbridge is True
    assert loaded_settings.kimi_webbridge_allowed_domains == ["*"]
    assert loaded_settings.kimi_webbridge_allow_mutations is True
    assert loaded_settings.kimi_webbridge_require_approval is False
    assert loaded_settings.enable_computer_actions is True
    assert loaded_settings.computer_allowed_roots
    assert loaded_settings.computer_organize_dry_run_only is False
    assert loaded_settings.enable_browser_automation is True
    assert loaded_settings.browser_allowed_domains == ["*"]
    assert loaded_settings.browser_allow_headed is True
    assert loaded_settings.browser_allow_vision is True
    assert loaded_settings.enable_browser_ssrf_check is False
    assert loaded_settings.enable_email_send is False
    assert loaded_settings.mail_require_approval_for_send is True
    assert loaded_settings.mail_allow_explicit_send is False
    assert loaded_settings.enable_google_calendar_write is True
    assert loaded_settings.enable_google_drive_write is True
    assert loaded_settings.research_persistence_backend == "postgres"


def test_dedicated_local_guarded_keeps_explicit_friction_flags() -> None:
    loaded_settings = Settings(
        _env_file=None,
        operator_profile="dedicated_local",
        local_autonomy_mode="guarded",
        require_human_approval_for_external_actions=True,
        approval_require_four_eyes=True,
        mail_require_approval_for_send=True,
        kimi_webbridge_require_approval=True,
        kimi_webbridge_allow_mutations=False,
    )

    assert loaded_settings.require_human_approval_for_external_actions is True
    assert loaded_settings.approval_require_four_eyes is True
    assert loaded_settings.mail_require_approval_for_send is True
    assert loaded_settings.kimi_webbridge_require_approval is True
    assert loaded_settings.kimi_webbridge_allow_mutations is False


def test_parse_int_csv() -> None:
    assert parse_int_csv("1, 2,,3") == [1, 2, 3]
    assert parse_int_csv("") == []
    assert parse_int_csv(["4", 5]) == [4, 5]


def test_parse_str_csv() -> None:
    assert parse_str_csv("a, b,,c") == ["a", "b", "c"]
    assert parse_str_csv("") == []
    assert parse_str_csv(["x", " y "]) == ["x", "y"]


def test_rejects_changeme_in_production() -> None:
    with pytest.raises(ValidationError, match="Production settings cannot use CHANGEME"):
        Settings(_env_file=PROJECT_ROOT / ".env.example", environment="production")


def test_parse_cors_origins() -> None:
    assert parse_cors_origins("") == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3101",
        "http://127.0.0.1:3101",
    ]
    assert parse_cors_origins("https://app.example.test") == ["https://app.example.test"]
    assert parse_cors_origins(" https://a.test , https://b.test ") == [
        "https://a.test",
        "https://b.test",
    ]


def test_rejects_cors_wildcard() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        Settings(jwt_secret="x" * 32, cors_allow_origins="*")


def test_rejects_invalid_mail_digest_schedule() -> None:
    with pytest.raises(ValidationError, match="MAIL_DIGEST_HOURS_LOCAL"):
        Settings(_env_file=None, mail_digest_hours_local="10,25")
    with pytest.raises(ValidationError, match="MAIL_DIGEST_TIMEZONE"):
        Settings(_env_file=None, mail_digest_timezone="Chile/Nowhere")


def test_external_capabilities_require_credentials_when_enabled() -> None:
    # _env_file=None keeps this a hermetic unit test of the validator: it must
    # not read the operator's real ../.env (which may legitimately carry these
    # credentials), only the in-call kwargs.
    with pytest.raises(ValidationError, match="Gmail integration requires"):
        Settings(_env_file=None, gmail_read_enabled=True)
    with pytest.raises(ValidationError, match="Microsoft mail integration requires"):
        Settings(_env_file=None, microsoft_mail_enabled=True)
    with pytest.raises(ValidationError, match="GoDaddy integration requires"):
        Settings(_env_file=None, godaddy_enabled=True)


def test_production_google_writes_require_human_approval() -> None:
    production_secrets = {
        "environment": "production",
        # Hermetic: ignore the operator's real ../.env so the production
        # validators are exercised only against these explicit kwargs (the
        # ambient .env legitimately carries enabled capabilities/keys that
        # would otherwise inject unrelated validation errors).
        "_env_file": None,
        "jwt_secret": "x" * 32,
        "primary_llm_api_key": "primary-key",  # pragma: allowlist secret
        "secondary_llm_api_key": "secondary-key",  # pragma: allowlist secret
        "fallback_llm_api_key": "fallback-key",  # pragma: allowlist secret
        "vision_llm_api_key": "vision-key",  # pragma: allowlist secret
        "embeddings_api_key": "embeddings-key",  # pragma: allowlist secret
        "langsmith_api_key": "langsmith-key",  # pragma: allowlist secret
        "postgres_password": "postgres-password",  # pragma: allowlist secret
        "database_url": "postgresql+asyncpg://cogos:postgres-password@localhost:5432/cognitive_os",  # noqa: E501  # pragma: allowlist secret
        "weaviate_api_key": "weaviate-key",  # pragma: allowlist secret
        "neo4j_password": "neo4j-password",  # pragma: allowlist secret
        "tavily_api_key": "tavily-key",  # pragma: allowlist secret
        "telegram_bot_token": "telegram-token",  # pragma: allowlist secret
        "action_payload_encryption_key": "action-payload-key",
        "action_payload_encryption_required": True,
        "research_persistence_backend": "postgres",
    }

    with pytest.raises(ValidationError, match="Google Calendar writes require human approval"):
        Settings(
            **production_secrets,
            enable_google_calendar_write=True,
            require_human_approval_for_external_actions=False,
        )
    with pytest.raises(ValidationError, match="Google Drive writes require human approval"):
        Settings(
            **production_secrets,
            enable_google_drive_write=True,
            require_human_approval_for_external_actions=False,
        )


def test_production_kimi_webbridge_mutations_require_approval() -> None:
    production_secrets = {
        "environment": "production",
        # Hermetic: ignore the operator's real ../.env so the production
        # validators are exercised only against these explicit kwargs (the
        # ambient .env legitimately carries enabled capabilities/keys that
        # would otherwise inject unrelated validation errors).
        "_env_file": None,
        "jwt_secret": "x" * 32,
        "primary_llm_api_key": "primary-key",  # pragma: allowlist secret
        "secondary_llm_api_key": "secondary-key",  # pragma: allowlist secret
        "fallback_llm_api_key": "fallback-key",  # pragma: allowlist secret
        "vision_llm_api_key": "vision-key",  # pragma: allowlist secret
        "embeddings_api_key": "embeddings-key",  # pragma: allowlist secret
        "langsmith_api_key": "langsmith-key",  # pragma: allowlist secret
        "postgres_password": "postgres-password",  # pragma: allowlist secret
        "database_url": "postgresql+asyncpg://cogos:postgres-password@localhost:5432/cognitive_os",  # noqa: E501  # pragma: allowlist secret
        "weaviate_api_key": "weaviate-key",  # pragma: allowlist secret
        "neo4j_password": "neo4j-password",  # pragma: allowlist secret
        "tavily_api_key": "tavily-key",  # pragma: allowlist secret
        "telegram_bot_token": "telegram-token",  # pragma: allowlist secret
        "action_payload_encryption_key": "action-payload-key",
        "action_payload_encryption_required": True,
        "research_persistence_backend": "postgres",
    }

    with pytest.raises(ValidationError, match="Kimi WebBridge mutations require"):
        Settings(
            **production_secrets,
            enable_kimi_webbridge=True,
            kimi_webbridge_allowed_domains="google.com",
            kimi_webbridge_allow_mutations=True,
            kimi_webbridge_require_approval=False,
        )


def test_action_payload_encryption_required_needs_key() -> None:
    # _env_file=None: hermetic. The operator's real ../.env now carries a valid
    # ACTION_PAYLOAD_ENCRYPTION_KEY; this test asserts the validator logic in
    # isolation (required=true + no key must raise).
    with pytest.raises(ValidationError, match="ACTION_PAYLOAD_ENCRYPTION_KEY"):
        Settings(_env_file=None, action_payload_encryption_required=True)


def test_production_requires_action_payload_encryption() -> None:
    production_secrets = {
        "environment": "production",
        # Hermetic: ignore the operator's real ../.env so the production
        # validators are exercised only against these explicit kwargs (the
        # ambient .env legitimately carries enabled capabilities/keys that
        # would otherwise inject unrelated validation errors).
        "_env_file": None,
        "jwt_secret": "x" * 32,
        "primary_llm_api_key": "primary-key",  # pragma: allowlist secret
        "secondary_llm_api_key": "secondary-key",  # pragma: allowlist secret
        "fallback_llm_api_key": "fallback-key",  # pragma: allowlist secret
        "vision_llm_api_key": "vision-key",  # pragma: allowlist secret
        "embeddings_api_key": "embeddings-key",  # pragma: allowlist secret
        "langsmith_api_key": "langsmith-key",  # pragma: allowlist secret
        "postgres_password": "postgres-password",  # pragma: allowlist secret
        "database_url": "postgresql+asyncpg://cogos:postgres-password@localhost:5432/cognitive_os",  # noqa: E501  # pragma: allowlist secret
        "weaviate_api_key": "weaviate-key",  # pragma: allowlist secret
        "neo4j_password": "neo4j-password",  # pragma: allowlist secret
        "tavily_api_key": "tavily-key",  # pragma: allowlist secret
        "telegram_bot_token": "telegram-token",  # pragma: allowlist secret
        "action_payload_encryption_key": "action-payload-key",
        "research_persistence_backend": "postgres",
    }

    with pytest.raises(ValidationError, match="payload encryption must be required"):
        Settings(**production_secrets)


def test_production_requires_postgres_research_persistence() -> None:
    production_secrets = {
        "environment": "production",
        # Hermetic: ignore the operator's real ../.env so the production
        # validators are exercised only against these explicit kwargs (the
        # ambient .env legitimately carries enabled capabilities/keys that
        # would otherwise inject unrelated validation errors).
        "_env_file": None,
        "jwt_secret": "x" * 32,
        "primary_llm_api_key": "primary-key",  # pragma: allowlist secret
        "secondary_llm_api_key": "secondary-key",  # pragma: allowlist secret
        "fallback_llm_api_key": "fallback-key",  # pragma: allowlist secret
        "vision_llm_api_key": "vision-key",  # pragma: allowlist secret
        "embeddings_api_key": "embeddings-key",  # pragma: allowlist secret
        "langsmith_api_key": "langsmith-key",  # pragma: allowlist secret
        "postgres_password": "postgres-password",  # pragma: allowlist secret
        "database_url": "postgresql+asyncpg://cogos:postgres-password@localhost:5432/cognitive_os",  # noqa: E501  # pragma: allowlist secret
        "weaviate_api_key": "weaviate-key",  # pragma: allowlist secret
        "neo4j_password": "neo4j-password",  # pragma: allowlist secret
        "tavily_api_key": "tavily-key",  # pragma: allowlist secret
        "telegram_bot_token": "telegram-token",  # pragma: allowlist secret
        "action_payload_encryption_key": "action-payload-key",
        "action_payload_encryption_required": True,
    }

    with pytest.raises(ValidationError, match="RESEARCH_PERSISTENCE_BACKEND=postgres"):
        Settings(**production_secrets)


def test_godaddy_rate_limit_is_bounded() -> None:
    with pytest.raises(ValidationError, match="between 1 and 60"):
        Settings(godaddy_max_requests_per_minute=61)


def test_computer_max_files_per_plan_is_bounded() -> None:
    with pytest.raises(ValidationError, match="between 1 and 5000"):
        Settings(computer_max_files_per_plan=5001)
