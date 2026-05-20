from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def parse_int_csv(value: object) -> list[int]:
    """Parse comma-separated integer IDs from environment variables."""
    if value is None or value == "":
        return []

    if isinstance(value, str):
        raw_items: Sequence[object] = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, Sequence) and not isinstance(value, bytes):
        raw_items = value
    else:
        msg = "Expected a comma-separated string or sequence of integer IDs."
        raise TypeError(msg)

    parsed: list[int] = []
    for item in raw_items:
        try:
            if isinstance(item, int):
                parsed.append(item)
            elif isinstance(item, str):
                parsed.append(int(item))
            else:
                msg = f"Invalid integer ID: {item!r}"
                raise ValueError(msg)
        except (TypeError, ValueError) as exc:
            msg = f"Invalid integer ID: {item!r}"
            raise ValueError(msg) from exc
    return parsed


def parse_cors_origins(value: object) -> list[str]:
    """Parse comma-separated browser origins; empty uses local Next.js dev defaults.

    Default covers both :3000 (legacy) and :3001 (current default since the
    operator's OpenChamber occupies :3000) so a clean checkout works without
    editing .env. Operator overrides via CORS_ALLOW_ORIGINS still win.
    """
    default = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    )
    if value is None or value == "":
        return list(default)
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items if items else list(default)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items if items else list(default)
    msg = "Expected a comma-separated string or sequence of origin URLs."
    raise TypeError(msg)


def parse_str_csv(value: object) -> list[str]:
    """Parse comma-separated strings from environment variables."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item).strip() for item in value if str(item).strip()]
    msg = "Expected a comma-separated string or sequence of strings."
    raise TypeError(msg)


IntegerIDList = Annotated[list[int], NoDecode, BeforeValidator(parse_int_csv)]
CORSOriginsList = Annotated[list[str], NoDecode, BeforeValidator(parse_cors_origins)]
StringList = Annotated[list[str], NoDecode, BeforeValidator(parse_str_csv)]


class LLMConfig(BaseModel):
    """Provider-agnostic LLM endpoint configuration."""

    model_config = ConfigDict(frozen=True)

    provider: str
    base_url: str
    api_key: SecretStr
    model: str


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    # Operator profile (Fase 68b, GPT-5.5 + operator request).
    #
    # `strict` (default): the historical posture — approvals/four-eyes,
    # narrow allow-lists, short TTLs, sanitised env for adapters. Right
    # for shared machines or remote ops.
    #
    # `dedicated_local`: this PC is dedicated to the agent and the
    # operator's real browser profile (Edge with logged sessions) is on
    # it. The profile relaxes friction wherever it doesn't cause
    # irreversible damage: four-eyes off, longer approval TTL, computer
    # roots covering the home directory, adapter env not sanitised by
    # default. Browser/WebBridge wildcards and mail autosend are NOT
    # silent defaults — the operator still needs to set them
    # (`KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*`, `MAIL_REQUIRE_APPROVAL_FOR_SEND=false`)
    # so the choice is visible in `/health/dashboard`, but the profile
    # documents and recommends them for a dedicated PC. See
    # `_apply_operator_profile_defaults()`.
    operator_profile: Literal["strict", "dedicated_local"] = Field(
        default="strict",
        alias="OPERATOR_PROFILE",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    jwt_secret: SecretStr = Field(default=SecretStr("CHANGEME"), alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, alias="JWT_EXPIRE_MINUTES")
    admin_user_ids: IntegerIDList = Field(default_factory=list, alias="ADMIN_USER_IDS")
    auth_default_roles: StringList = Field(
        default_factory=lambda: ["operator"],
        alias="AUTH_DEFAULT_ROLES",
        description="Roles assigned by the local token helper when no roles are supplied.",
    )
    auth_admin_roles: StringList = Field(
        default_factory=lambda: ["admin"],
        alias="AUTH_ADMIN_ROLES",
        description="JWT roles that grant admin privileges in addition to ADMIN_USER_IDS.",
    )
    cors_allow_origins: CORSOriginsList = Field(default_factory=list, alias="CORS_ALLOW_ORIGINS")

    primary_llm_provider: str = Field(default="openai_compatible", alias="PRIMARY_LLM_PROVIDER")
    primary_llm_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="PRIMARY_LLM_BASE_URL",
    )
    primary_llm_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="PRIMARY_LLM_API_KEY",
    )
    primary_llm_model: str = Field(default="deepseek-v4-pro", alias="PRIMARY_LLM_MODEL")
    primary_llm_reasoning_effort: str | None = Field(
        default="high",
        alias="PRIMARY_LLM_REASONING_EFFORT",
    )
    primary_llm_thinking_enabled: bool = Field(
        default=True,
        alias="PRIMARY_LLM_THINKING_ENABLED",
    )
    # DeepAgents/structured-output need a model that supports a *forced*
    # tool_choice. DeepSeek's reasoner (what `deepseek-v4-pro` maps to) returns
    # HTTP 400 "deepseek-reasoner does not support this tool_choice", which
    # silently degraded every DeepAgent run to the RAG fallback. The agent lane
    # therefore uses a tool-capable model (DeepSeek `deepseek-chat` by default)
    # while plain chat keeps the reasoner. Reuses the primary provider/base/key
    # unless explicitly overridden.
    agent_llm_model: str = Field(default="deepseek-chat", alias="AGENT_LLM_MODEL")
    agent_llm_base_url: str = Field(default="", alias="AGENT_LLM_BASE_URL")
    agent_llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="AGENT_LLM_API_KEY",
    )

    secondary_llm_provider: str = Field(default="openai_compatible", alias="SECONDARY_LLM_PROVIDER")
    secondary_llm_base_url: str = Field(
        # Fase 68b: NO usar api.kimi.com/coding/v1 como default — ese endpoint
        # da HTTP 403 a clientes HTTP (Kimi-for-Coding solo coding agents).
        # La cadena verificada usa el gateway openai-compatible del operador.
        default="https://your-openai-compatible-gateway/v1",
        alias="SECONDARY_LLM_BASE_URL",
    )
    secondary_llm_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="SECONDARY_LLM_API_KEY",
    )
    secondary_llm_model: str = Field(default="gemini-3.1-pro-low", alias="SECONDARY_LLM_MODEL")

    fallback_llm_provider: str = Field(default="openai_compatible", alias="FALLBACK_LLM_PROVIDER")
    fallback_llm_base_url: str = Field(
        # Idem: nunca default a Kimi HTTP (403). Cadena verificada = gateway.
        default="https://your-openai-compatible-gateway/v1",
        alias="FALLBACK_LLM_BASE_URL",
    )
    fallback_llm_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="FALLBACK_LLM_API_KEY",
    )
    fallback_llm_model: str = Field(default="gemini-3.1-pro-low", alias="FALLBACK_LLM_MODEL")

    vision_llm_provider: str = Field(default="openai_compatible", alias="VISION_LLM_PROVIDER")
    vision_llm_base_url: str = Field(
        default="https://api.z.ai/api/coding/paas/v4",
        alias="VISION_LLM_BASE_URL",
    )
    vision_llm_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="VISION_LLM_API_KEY")
    vision_llm_model: str = Field(default="glm-4.6v", alias="VISION_LLM_MODEL")

    # Secondary vision model. When the primary vision provider errors (quota,
    # outage, model retired), `create_vision_chat_model(fallback=True)` builds
    # this one. Fase 68b: default a GLM-4.6v (verificado HTTP 200), NO a Kimi
    # HTTP (403). Kimi-for-Coding solo funciona vía el adapter CLI del Code
    # Director, nunca como endpoint ChatOpenAI.
    vision_fallback_llm_provider: str = Field(
        default="openai_compatible",
        alias="VISION_FALLBACK_LLM_PROVIDER",
    )
    vision_fallback_llm_base_url: str = Field(
        default="https://api.z.ai/api/coding/paas/v4",
        alias="VISION_FALLBACK_LLM_BASE_URL",
    )
    vision_fallback_llm_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="VISION_FALLBACK_LLM_API_KEY",
    )
    vision_fallback_llm_model: str = Field(
        default="glm-4.6v",
        alias="VISION_FALLBACK_LLM_MODEL",
    )

    embeddings_provider: str = Field(default="gemini", alias="EMBEDDINGS_PROVIDER")
    embeddings_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        alias="EMBEDDINGS_BASE_URL",
    )
    embeddings_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="EMBEDDINGS_API_KEY")
    embeddings_model: str = Field(default="gemini-embedding-001", alias="EMBEDDINGS_MODEL")
    embeddings_dimension: int = Field(default=1536, alias="EMBEDDINGS_DIMENSION")
    embeddings_task_type_document: str = Field(
        default="RETRIEVAL_DOCUMENT", alias="EMBEDDINGS_TASK_TYPE_DOCUMENT"
    )
    embeddings_task_type_query: str = Field(
        default="RETRIEVAL_QUERY", alias="EMBEDDINGS_TASK_TYPE_QUERY"
    )
    embeddings_fallback_api_keys: str = Field(default="", alias="EMBEDDINGS_FALLBACK_API_KEYS")
    reranker_enabled: bool = Field(default=False, alias="RERANKER_ENABLED")
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")

    @property
    def embeddings_api_keys(self) -> list[SecretStr]:
        """Primary key + comma-separated fallback keys, deduped, in order."""
        primary = self.embeddings_api_key.get_secret_value().strip()
        keys: list[str] = []
        if primary and primary != "CHANGEME":
            keys.append(primary)
        for raw in self.embeddings_fallback_api_keys.split(","):
            cleaned = raw.strip()
            if cleaned and cleaned != "CHANGEME" and cleaned not in keys:
                keys.append(cleaned)
        return [SecretStr(value) for value in keys]

    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="LANGSMITH_API_KEY")
    langsmith_personal_access_token: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="LANGSMITH_PERSONAL_ACCESS_TOKEN",
    )
    langsmith_project: str = Field(default="cognitive_os", alias="LANGSMITH_PROJECT")
    langsmith_endpoints_require_admin: bool = Field(
        default=True,
        alias="LANGSMITH_ENDPOINTS_REQUIRE_ADMIN",
        description=(
            "When True, HTTP routes under /langsmith/* require ADMIN_USER_IDS to be set "
            "or the JWT to carry an admin role."
        ),
    )
    trace_redact_pii: bool = Field(default=True, alias="TRACE_REDACT_PII")
    trace_full_payloads: bool = Field(default=False, alias="TRACE_FULL_PAYLOADS")
    action_payload_encryption_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="ACTION_PAYLOAD_ENCRYPTION_KEY",
        description=(
            "Fernet key or high-entropy passphrase used to encrypt executable "
            "ActionRequest payloads at rest."
        ),
    )
    action_payload_encryption_required: bool = Field(
        default=False,
        alias="ACTION_PAYLOAD_ENCRYPTION_REQUIRED",
        description=(
            "When True, executable ActionRequest payloads must be encrypted and "
            "legacy plaintext payloads are rejected at execution time."
        ),
    )
    approval_require_four_eyes: bool = Field(
        default=True,
        alias="APPROVAL_REQUIRE_FOUR_EYES",
        description=(
            "When True, the user that approves or rejects a HumanApproval must "
            "be different from the user that requested the underlying action. "
            "Default True enforces the standard commercial human-in-the-loop "
            "contract; set False only for single-operator dev/test setups."
        ),
    )
    approval_pending_max_hours: int = Field(
        default=48,
        ge=1,
        le=24 * 14,
        alias="APPROVAL_PENDING_MAX_HOURS",
        description=(
            "Hours a HumanApproval may stay 'pending' before the reaper flips it "
            "to 'expired'. Linked Jobs and ActionRequests transition to "
            "'rejected' so the audit trail stays coherent. Prevents a stale "
            "approval from being decided long after the operator forgot it."
        ),
    )
    rate_limit_backend: Literal["memory", "redis"] = Field(
        default="memory",
        alias="RATE_LIMIT_BACKEND",
        description=(
            "Backend for the per-(user, bucket) rate limiter on hot endpoints. "
            "'memory' is single-replica only; switch to 'redis' for any "
            "multi-replica deployment so all API instances vote against the "
            "same window state."
        ),
    )
    rate_limit_redis_url: str = Field(
        default="",
        alias="RATE_LIMIT_REDIS_URL",
        description=(
            "Redis URL for the rate limiter backend. When empty, the limiter "
            "falls back to REDIS_URL (the generic broker URL). The limiter "
            "fails open if Redis is unreachable so a transient outage never "
            "blocks legit traffic."
        ),
    )
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")
    http_max_retries: int = Field(default=2, alias="HTTP_MAX_RETRIES")
    circuit_breaker_failure_threshold: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    )
    circuit_breaker_reset_seconds: float = Field(
        default=60.0,
        alias="CIRCUIT_BREAKER_RESET_SECONDS",
    )

    postgres_user: str = Field(default="cogos", alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(default=SecretStr("CHANGEME"), alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="cognitive_os", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: str = Field(
        default="postgresql+asyncpg://cogos@localhost:5432/cognitive_os",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )
    celery_task_soft_time_limit_seconds: int = Field(
        default=300,
        alias="CELERY_TASK_SOFT_TIME_LIMIT_SECONDS",
    )
    celery_task_time_limit_seconds: int = Field(
        default=360,
        alias="CELERY_TASK_TIME_LIMIT_SECONDS",
    )
    celery_result_expires_seconds: int = Field(
        default=3600,
        alias="CELERY_RESULT_EXPIRES_SECONDS",
    )
    weaviate_url: str = Field(default="http://localhost:8080", alias="WEAVIATE_URL")
    weaviate_http_port: int = Field(default=8081, alias="WEAVIATE_HTTP_PORT")
    weaviate_grpc_port: int = Field(default=50052, alias="WEAVIATE_GRPC_PORT")
    weaviate_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="WEAVIATE_API_KEY")
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_http_port: int = Field(default=7475, alias="NEO4J_HTTP_PORT")
    neo4j_bolt_port: int = Field(default=7688, alias="NEO4J_BOLT_PORT")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(default=SecretStr("CHANGEME"), alias="NEO4J_PASSWORD")

    storage_backend: str = Field(default="filesystem", alias="STORAGE_BACKEND")
    local_storage_dir: str = Field(default="./storage", alias="LOCAL_STORAGE_DIR")
    document_ingest_allowed_prefixes: StringList = Field(
        default_factory=list,
        alias="DOCUMENT_INGEST_ALLOWED_PREFIXES",
        description=(
            "Extra directories (in addition to LOCAL_STORAGE_DIR) from which "
            "`POST /documents/ingest` may read PDFs. Comma-separated paths."
        ),
    )
    backup_dir: str = Field(default="./backups", alias="BACKUP_DIR")

    tavily_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="TAVILY_API_KEY")
    web_search_enabled: bool = Field(default=False, alias="WEB_SEARCH_ENABLED")

    enable_openharness_research: bool = Field(
        default=False,
        alias="ENABLE_OPENHARNESS_RESEARCH",
        description=(
            "If true and the optional `openharness-ai` extra is installed, the research route "
            "uses OpenHarness QueryEngine (proven tool loop) before DeepAgents/RAG fallback."
        ),
    )
    openharness_max_turns: int = Field(default=16, ge=1, le=128, alias="OPENHARNESS_MAX_TURNS")
    openharness_workspace: Path = Field(
        default=Path("./storage/openharness_workspace"),
        alias="OPENHARNESS_WORKSPACE",
    )
    openharness_include_file_tools: bool = Field(
        default=False,
        alias="OPENHARNESS_INCLUDE_FILE_TOOLS",
        description="Allow read_file in OpenHarness (paths relative to OPENHARNESS_WORKSPACE).",
    )
    openharness_web_tools: bool = Field(
        default=True,
        alias="OPENHARNESS_WEB_TOOLS",
        description="Register OpenHarness web_search / web_fetch (HTTP) in the harness loop.",
    )
    openharness_query_timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=7200,
        alias="OPENHARNESS_QUERY_TIMEOUT_SECONDS",
        description="Hard timeout for one OpenHarness QueryEngine run (wall clock).",
    )

    openharness_research_pipeline: Literal["short_circuit", "prelude_merge"] = Field(
        default="prelude_merge",
        alias="OPENHARNESS_RESEARCH_PIPELINE",
        description=(
            "`short_circuit`: si OpenHarness responde, no se llama DeepAgent. "
            "`prelude_merge`: siempre se llama DeepAgent; el resultado de OpenHarness va "
            "como contexto inicial (fusión Cognitive OS > OH + DeepAgents solos)."
        ),
    )
    openharness_toolkit_preset: Literal["minimal", "research", "full"] = Field(
        default="research",
        alias="OPENHARNESS_TOOLKIT_PRESET",
        description=(
            "`minimal`: solo grep/glob y web opcional. "
            "`research`: kit expandido (archivos, skills, bash, MCP auth, cron, equipo, todo). "
            "`full`: `create_default_tool_registry` de upstream OpenHarness (sin MCP remoto)."
        ),
    )
    openharness_workspace_mode: Literal["sandbox", "deepagent_mirror"] = Field(
        default="deepagent_mirror",
        alias="OPENHARNESS_WORKSPACE_MODE",
        description=(
            "`deepagent_mirror`: mismo workspace que DeepAgents en `research`. "
            "`sandbox`: usa `OPENHARNESS_WORKSPACE`."
        ),
    )

    perplexity_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="PERPLEXITY_API_KEY",
    )
    perplexity_base_url: str = Field(
        default="https://api.perplexity.ai",
        alias="PERPLEXITY_BASE_URL",
    )
    exa_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="EXA_API_KEY")
    serper_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="SERPER_API_KEY")
    brave_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="BRAVE_API_KEY")
    brave_answer_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="BRAVE_ANSWER_API_KEY",
    )
    brave_search_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="BRAVE_SEARCH_API_KEY",
    )
    brave_free_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="BRAVE_FREE_API_KEY",
    )

    telegram_enabled: bool = Field(default=False, alias="TELEGRAM_ENABLED")
    telegram_bot_token: SecretStr = Field(default=SecretStr("CHANGEME"), alias="TELEGRAM_BOT_TOKEN")
    telegram_authorized_user_ids: IntegerIDList = Field(
        default_factory=list,
        alias="TELEGRAM_AUTHORIZED_USER_IDS",
    )
    enable_personal_assistant_api: bool = Field(
        default=True,
        alias="ENABLE_PERSONAL_ASSISTANT_API",
    )
    enable_personal_reminder_delivery: bool = Field(
        default=False,
        alias="ENABLE_PERSONAL_REMINDER_DELIVERY",
    )
    telegram_assist_user_map: StringList = Field(
        default_factory=list,
        alias="TELEGRAM_ASSIST_USER_MAP",
    )
    telegram_reminder_chat_map: StringList = Field(
        default_factory=list,
        alias="TELEGRAM_REMINDER_CHAT_MAP",
    )
    telegram_gmail_digest_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_GMAIL_DIGEST_ENABLED",
    )
    telegram_gmail_digest_chat_ids: IntegerIDList = Field(
        default_factory=list,
        alias="TELEGRAM_GMAIL_DIGEST_CHAT_IDS",
        description=(
            "Chats Telegram que deben recibir el digest automatizado; vacío ⇒ "
            "`TELEGRAM_AUTHORIZED_USER_IDS`."
        ),
    )
    telegram_gmail_digest_hour_utc: int = Field(
        default=8,
        alias="TELEGRAM_GMAIL_DIGEST_HOUR_UTC",
        ge=0,
        le=23,
    )
    telegram_gmail_digest_lookback_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        alias="TELEGRAM_GMAIL_DIGEST_LOOKBACK_HOURS",
    )

    tools_readonly_mode: bool = Field(default=True, alias="TOOLS_READONLY_MODE")
    require_human_approval_for_external_actions: bool = Field(
        default=True,
        alias="REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS",
    )
    enable_browser_automation: bool = Field(default=False, alias="ENABLE_BROWSER_AUTOMATION")
    enable_computer_actions: bool = Field(default=False, alias="ENABLE_COMPUTER_ACTIONS")
    enable_email_send: bool = Field(default=False, alias="ENABLE_EMAIL_SEND")
    enable_social_posting: bool = Field(default=False, alias="ENABLE_SOCIAL_POSTING")
    allow_dangerous_tools: bool = Field(default=False, alias="ALLOW_DANGEROUS_TOOLS")
    computer_allowed_roots: StringList = Field(
        default_factory=list,
        alias="COMPUTER_ALLOWED_ROOTS",
    )
    computer_organize_dry_run_only: bool = Field(
        default=True,
        alias="COMPUTER_ORGANIZE_DRY_RUN_ONLY",
    )
    computer_max_files_per_plan: int = Field(default=500, alias="COMPUTER_MAX_FILES_PER_PLAN")
    enable_document_generation: bool = Field(
        default=True,
        alias="ENABLE_DOCUMENT_GENERATION",
    )
    document_output_root: Path = Field(
        default=Path("./storage/documents"),
        alias="DOCUMENT_OUTPUT_ROOT",
    )
    document_asset_roots: StringList = Field(
        default_factory=list,
        alias="DOCUMENT_ASSET_ROOTS",
    )
    document_max_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        alias="DOCUMENT_MAX_SIZE_BYTES",
    )
    browser_automation_provider: Literal["playwright", "camoufox"] = Field(
        default="playwright",
        alias="BROWSER_AUTOMATION_PROVIDER",
    )
    browser_headless_default: bool = Field(default=True, alias="BROWSER_HEADLESS_DEFAULT")
    browser_allow_headed: bool = Field(default=False, alias="BROWSER_ALLOW_HEADED")
    browser_allow_vision: bool = Field(default=False, alias="BROWSER_ALLOW_VISION")
    browser_allowed_domains: StringList = Field(
        default_factory=list,
        alias="BROWSER_ALLOWED_DOMAINS",
    )
    browser_profile_dir: Path = Field(
        default=Path("./storage/browser/profiles"),
        alias="BROWSER_PROFILE_DIR",
    )
    browser_download_dir: Path = Field(
        default=Path("./storage/browser/downloads"),
        alias="BROWSER_DOWNLOAD_DIR",
    )
    browser_session_ttl_seconds: int = Field(default=900, alias="BROWSER_SESSION_TTL_SECONDS")
    browser_max_pages_per_task: int = Field(default=5, alias="BROWSER_MAX_PAGES_PER_TASK")
    browser_screenshot_dir: Path = Field(
        default=Path("./storage/browser/screenshots"),
        alias="BROWSER_SCREENSHOT_DIR",
    )
    browser_navigation_timeout_ms: int = Field(
        default=20000,
        alias="BROWSER_NAVIGATION_TIMEOUT_MS",
    )
    browser_screenshot_max_bytes: int = Field(
        default=5 * 1024 * 1024,
        alias="BROWSER_SCREENSHOT_MAX_BYTES",
    )
    enable_browser_ssrf_check: bool = Field(
        default=True,
        alias="ENABLE_BROWSER_SSRF_CHECK",
        description=(
            "When True, resolve the browser target hostname and refuse private/loopback "
            "IPs before navigating. Defends against DNS rebinding and internal-hostname "
            "collisions. Disable only in tests or hermetic environments without DNS."
        ),
    )
    action_request_running_max_minutes: int = Field(
        default=60,
        ge=1,
        alias="ACTION_REQUEST_RUNNING_MAX_MINUTES",
        description=(
            "Maximum age in minutes that an ActionRequest may remain in `running` "
            "before the reaper task marks it `failed`. A Celery worker that crashed "
            "mid-execution would otherwise leave the row stuck forever."
        ),
    )

    enable_research_orchestrator: bool = Field(
        default=True,
        alias="ENABLE_RESEARCH_ORCHESTRATOR",
    )
    research_max_parallel_workers: int = Field(
        default=4,
        alias="RESEARCH_MAX_PARALLEL_WORKERS",
        ge=1,
        le=16,
    )
    research_max_time_budget_seconds: int = Field(
        default=300,
        alias="RESEARCH_MAX_TIME_BUDGET_SECONDS",
        ge=5,
        le=3600,
    )
    research_max_subtasks: int = Field(
        default=8,
        alias="RESEARCH_MAX_SUBTASKS",
        ge=1,
        le=32,
    )
    research_persistence_backend: Literal["memory", "postgres"] = Field(
        default="memory",
        alias="RESEARCH_PERSISTENCE_BACKEND",
        description=(
            "`memory` is for local/dev tests. Production must use `postgres` so "
            "research run snapshots and event history survive process restarts."
        ),
    )

    gmail_read_enabled: bool = Field(default=False, alias="GMAIL_READ_ENABLED")
    gmail_send_enabled: bool = Field(default=False, alias="GMAIL_SEND_ENABLED")
    gmail_client_id: str = Field(default="CHANGEME", alias="GMAIL_CLIENT_ID")
    gmail_client_secret: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="GMAIL_CLIENT_SECRET",
    )
    gmail_token_dir: Path = Field(default=Path("./storage/oauth/gmail"), alias="GMAIL_TOKEN_DIR")
    gmail_scopes: StringList = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/gmail.readonly"],
        alias="GMAIL_SCOPES",
    )

    # Shared Google OAuth "Desktop app" client used by Calendar and Drive. It is
    # the same credential as GMAIL_CLIENT_ID/SECRET; keeping a dedicated alias
    # keeps the Calendar/Drive code decoupled from the Gmail-mail lane.
    google_client_id: str = Field(default="CHANGEME", alias="GOOGLE_CLIENT_ID")
    google_client_secret: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="GOOGLE_CLIENT_SECRET",
    )
    google_token_dir: Path = Field(
        default=Path("./storage/oauth/google"),
        alias="GOOGLE_TOKEN_DIR",
    )
    enable_google_calendar: bool = Field(default=False, alias="ENABLE_GOOGLE_CALENDAR")
    enable_google_calendar_write: bool = Field(
        default=False,
        alias="ENABLE_GOOGLE_CALENDAR_WRITE",
        description=(
            "Promote Calendar from read-only to allow event creation. The endpoint "
            "still requires an explicit `dry_run=false` per request — the operator "
            "must opt in twice (settings + per-call) before a real event is created."
        ),
    )
    google_calendar_scopes: StringList = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.freebusy",
        ],
        alias="GOOGLE_CALENDAR_SCOPES",
    )
    enable_google_drive: bool = Field(default=False, alias="ENABLE_GOOGLE_DRIVE")
    enable_google_drive_write: bool = Field(
        default=False,
        alias="ENABLE_GOOGLE_DRIVE_WRITE",
        description=(
            "Promote Drive from read-only to approved file uploads and file moves. "
            "Uploads still require explicit `dry_run=false` and only accept sources "
            "under DOCUMENT_OUTPUT_ROOT, LOCAL_STORAGE_DIR/workspaces, "
            "OPENSHELL_ALLOWED_OUTPUT_DIR, or COMPUTER_ALLOWED_ROOTS."
        ),
    )
    google_drive_scopes: StringList = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/drive"],
        alias="GOOGLE_DRIVE_SCOPES",
    )
    google_drive_upload_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1024,
        alias="GOOGLE_DRIVE_UPLOAD_MAX_BYTES",
    )
    google_drive_deliverables_folder_name: str = Field(
        default="Cognitive OS Deliverables",
        alias="GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME",
        min_length=1,
        max_length=400,
    )
    google_maps_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="GOOGLE_MAPS_API_KEY",
    )
    google_maps_base_url: str = Field(
        default="https://maps.googleapis.com",
        alias="GOOGLE_MAPS_BASE_URL",
    )
    enable_maps_routing: bool = Field(default=False, alias="ENABLE_MAPS_ROUTING")
    maps_default_travel_mode: Literal["driving", "walking", "bicycling", "transit"] = Field(
        default="driving",
        alias="MAPS_DEFAULT_TRAVEL_MODE",
    )

    microsoft_mail_enabled: bool = Field(default=False, alias="MICROSOFT_MAIL_ENABLED")
    microsoft_tenant_id: str = Field(default="common", alias="MICROSOFT_TENANT_ID")
    microsoft_client_id: str = Field(default="CHANGEME", alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="MICROSOFT_CLIENT_SECRET",
    )
    microsoft_token_dir: Path = Field(
        default=Path("./storage/oauth/microsoft"),
        alias="MICROSOFT_TOKEN_DIR",
    )
    microsoft_mail_scopes: StringList = Field(
        default_factory=lambda: ["Mail.ReadBasic", "offline_access"],
        alias="MICROSOFT_MAIL_SCOPES",
    )

    mail_enabled: bool = Field(default=False, alias="MAIL_ENABLED")
    mail_default_sender: str = Field(
        default="diego@doctormanzur.com",
        alias="MAIL_DEFAULT_SENDER",
    )
    mail_require_approval_for_send: bool = Field(
        default=True,
        alias="MAIL_REQUIRE_APPROVAL_FOR_SEND",
    )
    mail_poll_interval_seconds: int = Field(
        default=120,
        alias="MAIL_POLL_INTERVAL_SECONDS",
        ge=30,
        le=3600,
    )
    mail_imap_timeout_seconds: int = Field(
        default=30,
        alias="MAIL_IMAP_TIMEOUT_SECONDS",
        ge=5,
        le=300,
    )
    mail_smtp_timeout_seconds: int = Field(
        default=30,
        alias="MAIL_SMTP_TIMEOUT_SECONDS",
        ge=5,
        le=300,
    )
    mail_fetch_max_per_folder: int = Field(
        default=25,
        alias="MAIL_FETCH_MAX_PER_FOLDER",
        ge=1,
        le=200,
    )
    mail_gmail_label: str = Field(default="TODOS", alias="MAIL_GMAIL_LABEL")
    mail_godaddy_enabled: bool = Field(default=False, alias="MAIL_GODADDY_ENABLED")
    mail_godaddy_imap_host: str = Field(
        default="imap.secureserver.net",
        alias="MAIL_GODADDY_IMAP_HOST",
    )
    mail_godaddy_imap_port: int = Field(default=993, alias="MAIL_GODADDY_IMAP_PORT")
    mail_godaddy_smtp_host: str = Field(
        default="smtpout.secureserver.net",
        alias="MAIL_GODADDY_SMTP_HOST",
    )
    mail_godaddy_smtp_port: int = Field(default=465, alias="MAIL_GODADDY_SMTP_PORT")
    mail_godaddy_username: str = Field(
        default="diego@doctormanzur.com",
        alias="MAIL_GODADDY_USERNAME",
    )
    mail_godaddy_password: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="MAIL_GODADDY_PASSWORD",
    )
    mail_godaddy_monitor_folders: StringList = Field(
        default_factory=lambda: ["INBOX", "Bulk Mail", "Junk Email", "Spam"],
        alias="MAIL_GODADDY_MONITOR_FOLDERS",
    )

    godaddy_enabled: bool = Field(default=False, alias="GODADDY_ENABLED")
    godaddy_base_url: str = Field(default="https://api.godaddy.com", alias="GODADDY_BASE_URL")
    godaddy_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="GODADDY_API_KEY")
    godaddy_api_secret: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="GODADDY_API_SECRET",
    )
    godaddy_allowed_domains: StringList = Field(
        default_factory=list,
        alias="GODADDY_ALLOWED_DOMAINS",
    )
    godaddy_dns_dry_run_only: bool = Field(
        default=True,
        alias="GODADDY_DNS_DRY_RUN_ONLY",
    )
    godaddy_allow_production_writes: bool = Field(
        default=False,
        alias="GODADDY_ALLOW_PRODUCTION_WRITES",
    )
    godaddy_max_requests_per_minute: int = Field(
        default=60,
        alias="GODADDY_MAX_REQUESTS_PER_MINUTE",
    )

    # Code Director budget enforcement mode.
    #  - "soft" (default): the budget is a guideline. The current subtask
    #    always runs to its natural boundary (one CLI invocation up to the
    #    adapter wall-clock timeout); exceeding the budget ends the BUILD as
    #    `partial` between subtasks but never kills work mid-subtask. This is
    #    the right default for a dedicated local PC (let the agent finish;
    #    don't add friction).
    #  - "hard": the budget is checked BEFORE every adapter call; if a cap is
    #    already exceeded the subtask aborts immediately without spending the
    #    next call, and the adapter wall-clock timeout is clamped to the
    #    remaining runtime budget.
    code_director_budget_mode: Literal["soft", "hard"] = Field(
        default="soft", alias="CODE_DIRECTOR_BUDGET_MODE"
    )

    # Stability cap for `_package_workspace`. A long-running subtask could
    # leave a workspace with thousands of files and tens of GB of generated
    # content; uncapped `rglob('*') + tar.add` would either hang packaging
    # or fill the document_output volume. The reaper fails the build with a
    # clear error if either threshold is exceeded — we never truncate
    # silently.
    # How long a job can stay queued/running before the stale-jobs reaper
    # gives up on it. Surfaces zombie jobs (worker crashed before transitioning
    # to terminal) without forever-skewing /knowledge/stats. (Fase 72 C.)
    stale_job_max_hours: int = Field(default=24, ge=1, le=168, alias="STALE_JOB_MAX_HOURS")

    # MCP client (Fase 73). When enabled, the DeepAgent dynamically loads
    # tools from operator-declared MCP servers (Supermemory, GitHub, etc.)
    # in addition to the 21 built-in tools.
    #
    # `MCP_SERVERS` syntax (CSV of declarations):
    #
    #   <name>:<transport>:<target>[:<extra>=<value>,...]
    #
    # Transports:
    #   - `sse`        → target is a URL  (e.g. `mem:sse:http://localhost:9001/sse`)
    #   - `streamable_http` → target is a URL of an HTTP streaming MCP server
    #   - `stdio`      → target is the command to run (shell-style;
    #                     extras `cwd=`, `env_KEY=VAL`)
    #
    # The MCP allow-list per agent role lets the operator decide which
    # servers reach which subgraph. Empty list = ALL configured servers.
    enable_mcp_client: bool = Field(default=False, alias="ENABLE_MCP_CLIENT")
    mcp_servers: StringList = Field(default_factory=list, alias="MCP_SERVERS")
    mcp_call_timeout_seconds: int = Field(
        default=30, ge=1, le=600, alias="MCP_CALL_TIMEOUT_SECONDS"
    )
    mcp_allowed_for_research: StringList = Field(
        default_factory=list, alias="MCP_ALLOWED_FOR_RESEARCH"
    )
    mcp_allowed_for_document_analysis: StringList = Field(
        default_factory=list, alias="MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS"
    )

    code_director_package_max_files: int = Field(
        default=10_000, ge=1, alias="CODE_DIRECTOR_PACKAGE_MAX_FILES"
    )
    code_director_package_max_bytes: int = Field(
        default=500 * 1024 * 1024,
        ge=1,
        alias="CODE_DIRECTOR_PACKAGE_MAX_BYTES",
    )

    # When True the action service auto-approves a whitelist of *reversible*
    # action types (drive_ensure_folder, drive_upload) so the operator does not
    # have to click /approve on actions that cannot harm anyone but the agent's
    # own workspace. Mail send, drive_organize_files, browser, openshell and
    # code_build stay manual — they are irreversible or touch others. Default
    # False; flipped to True by `apply_operator_profile_defaults` when
    # `OPERATOR_PROFILE=dedicated_local` and the operator did not set it.
    auto_approve_reversible_actions: bool = Field(
        default=False, alias="AUTO_APPROVE_REVERSIBLE_ACTIONS"
    )

    enable_openshell_sandbox: bool = Field(default=False, alias="ENABLE_OPENSHELL_SANDBOX")
    openshell_project_dir: Path = Field(
        default=Path("./experiments/openshell-deepagent"),
        alias="OPENSHELL_PROJECT_DIR",
    )
    openshell_sandbox_name: str = Field(
        default="cognitive-os-sandbox",
        alias="OPENSHELL_SANDBOX_NAME",
    )
    openshell_gateway_url: str | None = Field(default=None, alias="OPENSHELL_GATEWAY_URL")
    openshell_gateway_tls_verify: bool = Field(
        default=True,
        alias="OPENSHELL_GATEWAY_TLS_VERIFY",
        description=(
            "Verify TLS certificates when probing OPENSHELL_GATEWAY_URL. "
            "Set false only for local dev with self-signed gateways."
        ),
    )
    openshell_max_runtime_seconds: int = Field(
        default=300,
        alias="OPENSHELL_MAX_RUNTIME_SECONDS",
    )
    openshell_max_output_bytes: int = Field(default=200000, alias="OPENSHELL_MAX_OUTPUT_BYTES")
    openshell_allow_network: bool = Field(default=False, alias="OPENSHELL_ALLOW_NETWORK")
    openshell_require_human_approval: bool = Field(
        default=True,
        alias="OPENSHELL_REQUIRE_HUMAN_APPROVAL",
    )
    openshell_allowed_input_dir: Path = Field(
        default=Path("./storage/sandbox_inputs"),
        alias="OPENSHELL_ALLOWED_INPUT_DIR",
    )
    openshell_allowed_output_dir: Path = Field(
        default=Path("./storage/sandbox_outputs"),
        alias="OPENSHELL_ALLOWED_OUTPUT_DIR",
    )
    nvidia_api_key: SecretStr | None = Field(default=None, alias="NVIDIA_API_KEY")
    nvidia_api_key_2: SecretStr | None = Field(default=None, alias="NVIDIA_API_KEY_2")
    nvidia_api_key_3: SecretStr | None = Field(default=None, alias="NVIDIA_API_KEY_3")

    elevenlabs_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="ELEVENLABS_API_KEY",
    )
    voice_enabled: bool = Field(default=False, alias="VOICE_ENABLED")
    voice_stt_model: str = Field(default="scribe_v1", alias="VOICE_STT_MODEL")
    voice_tts_model: str = Field(
        default="eleven_multilingual_v2",
        alias="VOICE_TTS_MODEL",
    )
    voice_tts_voice_id: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        alias="VOICE_TTS_VOICE_ID",
    )
    voice_max_audio_bytes: int = Field(
        default=25 * 1024 * 1024,
        alias="VOICE_MAX_AUDIO_BYTES",
        ge=1024,
    )
    voice_default_language: str = Field(default="es", alias="VOICE_DEFAULT_LANGUAGE")
    elevenlabs_base_url: str = Field(
        default="https://api.elevenlabs.io",
        alias="ELEVENLABS_BASE_URL",
    )

    # === Kimi WebBridge ===
    # Cognitive OS talks only to the local daemon (default 127.0.0.1:10086). The
    # daemon authenticates with the Kimi cloud separately; no Kimi key lives here.
    enable_kimi_webbridge: bool = Field(default=False, alias="ENABLE_KIMI_WEBBRIDGE")
    kimi_webbridge_url: str = Field(
        default="http://127.0.0.1:10086",
        alias="KIMI_WEBBRIDGE_URL",
    )
    kimi_webbridge_require_approval: bool = Field(
        default=True,
        alias="KIMI_WEBBRIDGE_REQUIRE_APPROVAL",
        description=(
            "When True, every mutating WebBridge call (click/fill/evaluate/upload/"
            "close) must go through an approved ActionRequest path; direct mutation "
            "endpoints are refused while this is true. Default True is the safe stance "
            "because the daemon drives the user's real browser."
        ),
    )
    kimi_webbridge_allowed_domains: StringList = Field(
        default_factory=list,
        alias="KIMI_WEBBRIDGE_ALLOWED_DOMAINS",
        description=(
            "Host names the agent may navigate. Empty = block everything. Match "
            "is exact or subdomain (e.g. 'google.com' covers 'mail.google.com')."
        ),
    )
    kimi_webbridge_allow_mutations: bool = Field(
        default=False,
        alias="KIMI_WEBBRIDGE_ALLOW_MUTATIONS",
        description=(
            "Promote WebBridge from read-only (navigate/snapshot/screenshot) to "
            "full control (click/fill/evaluate/upload). Independent gate on top "
            "of the domain allow-list."
        ),
    )
    kimi_webbridge_request_timeout_seconds: int = Field(
        default=20,
        ge=2,
        le=120,
        alias="KIMI_WEBBRIDGE_REQUEST_TIMEOUT_SECONDS",
    )

    # === CapSolver (captcha solving for any browser navigation lane) ===
    enable_captcha_solving: bool = Field(default=False, alias="ENABLE_CAPTCHA_SOLVING")
    capsolver_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="CAPSOLVER_API_KEY",
    )
    capsolver_base_url: str = Field(
        default="https://api.capsolver.com",
        alias="CAPSOLVER_BASE_URL",
    )
    capsolver_poll_interval_seconds: float = Field(
        default=3.0,
        ge=1.0,
        le=15.0,
        alias="CAPSOLVER_POLL_INTERVAL_SECONDS",
    )
    capsolver_max_poll_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        alias="CAPSOLVER_MAX_POLL_SECONDS",
        description=(
            "Hard ceiling for token-captcha polling (reCAPTCHA/hCaptcha/Turnstile). "
            "ImageToText returns inline and ignores this."
        ),
    )
    notion_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="NOTION_API_KEY")
    youtube_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="YOUTUBE_API_KEY")
    agentmail_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="AGENTMAIL_API_KEY",
    )
    admapix_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="ADMAPIX_API_KEY")
    maton_api_key: SecretStr = Field(default=SecretStr("CHANGEME"), alias="MATON_API_KEY")
    openrouter_api_key: SecretStr = Field(
        default=SecretStr("CHANGEME"),
        alias="OPENROUTER_API_KEY",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )

    deepagents_enable_skills: bool = Field(default=True, alias="DEEPAGENTS_ENABLE_SKILLS")
    deepagents_enable_subagents: bool = Field(default=True, alias="DEEPAGENTS_ENABLE_SUBAGENTS")
    deepagents_enable_memory: bool = Field(default=True, alias="DEEPAGENTS_ENABLE_MEMORY")
    deepagents_memory_require_approval: bool = Field(
        default=True,
        alias="DEEPAGENTS_MEMORY_REQUIRE_APPROVAL",
    )
    deepagents_core_skills_dir: Path = Field(
        default=Path("./backend/src/cognitive_os/deepagents/skills/core"),
        alias="DEEPAGENTS_CORE_SKILLS_DIR",
    )
    deepagents_user_skills_dir: Path = Field(
        default=Path("./storage/deepagents/skills/user"),
        alias="DEEPAGENTS_USER_SKILLS_DIR",
    )
    deepagents_memory_dir: Path = Field(
        default=Path("./storage/deepagents/memory"),
        alias="DEEPAGENTS_MEMORY_DIR",
    )
    deepagents_episodic_memory_enabled: bool = Field(
        default=True,
        alias="DEEPAGENTS_EPISODIC_MEMORY_ENABLED",
    )
    deepagents_memory_max_items_per_user: int = Field(
        default=500,
        alias="DEEPAGENTS_MEMORY_MAX_ITEMS_PER_USER",
    )
    deepagents_memory_consolidation_enabled: bool = Field(
        default=True,
        alias="DEEPAGENTS_MEMORY_CONSOLIDATION_ENABLED",
    )
    deepagents_memory_consolidation_cron: str = Field(
        default="0 3 * * *",
        alias="DEEPAGENTS_MEMORY_CONSOLIDATION_CRON",
    )
    deepagents_memory_redact_pii: bool = Field(
        default=True,
        alias="DEEPAGENTS_MEMORY_REDACT_PII",
    )

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Fase 79.1 — Responses API + prompt caching (24h gateway-side retention).
    #
    # The operator's gateway (`PRIMARY_LLM_BASE_URL` :8317) implements the
    # OpenAI Responses API at `/v1/responses` with `prompt_cache_retention`
    # of 24h. Enabling Responses API mode in `langchain-openai` lets us:
    # * Reuse a stable `prompt_cache_key` per role so the system prompt +
    #   few-shots only get billed once per 24h window (huge win for the
    #   recipe extractor and the router LLM which reuse long prompts).
    # * Use `text.format=json_schema` for structured output instead of
    #   forced tool_choice (cleaner, no model-family footguns).
    # * Surface reasoning summaries on the agent lane via `reasoning.summary`.
    #
    # Default ON because the gateway already speaks the protocol. Operators
    # who point a non-Responses-capable provider can flip the flag to false.
    # ------------------------------------------------------------------
    llm_use_responses_api: bool = Field(
        default=True,
        alias="LLM_USE_RESPONSES_API",
    )
    llm_prompt_cache_enabled: bool = Field(
        default=True,
        alias="LLM_PROMPT_CACHE_ENABLED",
    )
    # Stable namespace prepended to the per-role `prompt_cache_key`. Bump this
    # when you make a non-trivial change to the system prompt of any lane so
    # the gateway treats it as a fresh cache entry instead of serving stale
    # cached tokens.
    llm_prompt_cache_namespace: str = Field(
        default="cognitive-os-v1",
        alias="LLM_PROMPT_CACHE_NAMESPACE",
    )

    # Fase 78 — Recipe extractor (Fase A of the agent learning plan).
    # Distils successful long-running jobs into procedural memory
    # proposals. All defaults match docs/AGENT_LEARNING_PLAN.md so the
    # extractor can ship with no environment overrides.
    # ------------------------------------------------------------------
    recipe_extractor_enabled: bool = Field(
        default=True,
        alias="RECIPE_EXTRACTOR_ENABLED",
    )
    recipe_extractor_cron: str = Field(
        default="*/30 * * * *",
        alias="RECIPE_EXTRACTOR_CRON",
    )
    recipe_extractor_min_tool_calls: int = Field(
        default=5,
        alias="RECIPE_EXTRACTOR_MIN_TOOL_CALLS",
    )
    recipe_extractor_min_duration_seconds: int = Field(
        default=30,
        alias="RECIPE_EXTRACTOR_MIN_DURATION_SECONDS",
    )
    recipe_extractor_max_per_cycle: int = Field(
        default=20,
        alias="RECIPE_EXTRACTOR_MAX_PER_CYCLE",
    )
    # Job types worth distilling. Empty list = consider every job_type
    # (useful for tests). The default list excludes infra/maintenance
    # jobs (health_check, cleanup_old_jobs, reap_*, mail_sync) because
    # they don't represent reusable agent procedures. Comma-separated
    # in env (parsed by `StringList`) — matches the existing convention.
    # ------------------------------------------------------------------
    # Fase 79.3 — Failure post-mortems (Fase D of the agent learning plan).
    #
    # Daily Celery sweep that scans recently completed jobs for
    # tool_failed → tool_succeeded patterns and proposes warning memories
    # so future runs skip the broken first attempt. Auto-promotes when the
    # same (agent_role, tool_name) pattern fires `AUTOPROMOTE_THRESHOLD`
    # times without operator rejection.
    # ------------------------------------------------------------------
    failure_postmortem_enabled: bool = Field(
        default=True,
        alias="FAILURE_POSTMORTEM_ENABLED",
    )
    failure_postmortem_cron: str = Field(
        default="35 3 * * *",  # daily, 03:35 UTC (after stale-jobs-reaper)
        alias="FAILURE_POSTMORTEM_CRON",
    )
    failure_postmortem_max_per_cycle: int = Field(
        default=200,
        alias="FAILURE_POSTMORTEM_MAX_PER_CYCLE",
    )
    failure_postmortem_autopromote_threshold: int = Field(
        default=3,
        alias="FAILURE_POSTMORTEM_AUTOPROMOTE_THRESHOLD",
        description=(
            "Number of times the same (agent_role, tool_name) failure-recovery "
            "pattern must be observed before the scanner auto-promotes the "
            "warning without operator approval."
        ),
    )
    failure_postmortem_max_rejections: int = Field(
        default=2,
        alias="FAILURE_POSTMORTEM_MAX_REJECTIONS",
        description=(
            "If the operator has rejected this many prior proposals for the "
            "same pattern, the scanner stops creating new ones — silent "
            "deference to the operator's judgement."
        ),
    )

    # ------------------------------------------------------------------
    # Fase 79.4 — Tool effectiveness scorecard (Fase C of the learning plan).
    #
    # Daily Celery aggregator that rolls up tool_invoked/succeeded/failed
    # events into per-(agent_role, tool_name, day) counters with a derived
    # reliability score. Powers the future "Reliability of tools" section
    # of the system prompt and the new "Aprendizaje" UI tab.
    # ------------------------------------------------------------------
    tool_scorecard_enabled: bool = Field(
        default=True,
        alias="TOOL_SCORECARD_ENABLED",
    )
    tool_scorecard_cron: str = Field(
        default="15 4 * * *",  # daily, 04:15 UTC (after failure-postmortem)
        alias="TOOL_SCORECARD_CRON",
    )

    recipe_extractor_eligible_job_types: StringList = Field(
        default=[
            "deepagent_research",
            "document_analysis",
            "openshell_sandbox",
            "code_build",
            "external_action",
        ],
        alias="RECIPE_EXTRACTOR_ELIGIBLE_JOB_TYPES",
    )

    _production_secret_fields: ClassVar[tuple[str, ...]] = (
        "jwt_secret",
        "primary_llm_api_key",
        "secondary_llm_api_key",
        "fallback_llm_api_key",
        "vision_llm_api_key",
        "embeddings_api_key",
        "langsmith_api_key",
        "action_payload_encryption_key",
        "postgres_password",
        "database_url",
        "weaviate_api_key",
        "neo4j_password",
        "tavily_api_key",
        "telegram_bot_token",
    )

    @property
    def primary_llm(self) -> LLMConfig:
        return LLMConfig(
            provider=self.primary_llm_provider,
            base_url=self.primary_llm_base_url,
            api_key=self.primary_llm_api_key,
            model=self.primary_llm_model,
        )

    @property
    def secondary_llm(self) -> LLMConfig:
        return LLMConfig(
            provider=self.secondary_llm_provider,
            base_url=self.secondary_llm_base_url,
            api_key=self.secondary_llm_api_key,
            model=self.secondary_llm_model,
        )

    @property
    def fallback_llm(self) -> LLMConfig:
        return LLMConfig(
            provider=self.fallback_llm_provider,
            base_url=self.fallback_llm_base_url,
            api_key=self.fallback_llm_api_key,
            model=self.fallback_llm_model,
        )

    @property
    def vision_llm(self) -> LLMConfig:
        return LLMConfig(
            provider=self.vision_llm_provider,
            base_url=self.vision_llm_base_url,
            api_key=self.vision_llm_api_key,
            model=self.vision_llm_model,
        )

    @model_validator(mode="after")
    def apply_operator_profile_defaults(self) -> Self:
        """Soften defaults for `operator_profile=dedicated_local`.

        Only fields still at their factory default are overridden — any
        explicit value the operator put in `.env` wins (we never silently
        flip an operator-set flag). Safe to chain with the production
        validator: production reads the *final* values, so dedicated_local
        + production still fails if approval gates were softened too far.

        Decisions:
          - approval_require_four_eyes      → False  (PC dedicado, un solo aprobador)
          - approval_pending_max_hours      → 168h   (1 semana)
          - require_human_approval_for_external_actions → False
          - mail_require_approval_for_send  → True   (kept, sender mistakes are irreversible)
          - browser_allowed_domains         → []     (kept, operator's choice to widen)
          - kimi_webbridge_allowed_domains  → []     (idem)
        Doc: docs/USER_GUIDE.md "Perfiles de operación".
        """
        if self.operator_profile != "dedicated_local":
            return self
        # `model_fields_set` is pydantic's authoritative "did the caller set
        # this explicitly" — works whether the caller passed it positionally,
        # by alias from `.env`, or via env vars. Comparing against the default
        # value would silently override an explicit `True` that equals the
        # default `True`.
        explicit: set[str] = self.model_fields_set

        def _at_default(field: str) -> bool:
            return field not in explicit

        # In-place mutation: pydantic-settings models are not `frozen` here
        # and `model_validator(mode="after")` runs during construction, so
        # mutating attributes is the supported way to apply derived defaults.
        if _at_default("approval_require_four_eyes"):
            self.approval_require_four_eyes = False
        if _at_default("approval_pending_max_hours"):
            self.approval_pending_max_hours = 168
        if _at_default("require_human_approval_for_external_actions"):
            self.require_human_approval_for_external_actions = False
        if _at_default("code_director_budget_mode"):
            self.code_director_budget_mode = "soft"
        if _at_default("auto_approve_reversible_actions"):
            self.auto_approve_reversible_actions = True
        # Kimi WebBridge is the carril principal en PC dedicado (operator's
        # real Edge with sessions). Default off across profiles for safety;
        # dedicated_local opts in unless the operator forced it off.
        if _at_default("enable_kimi_webbridge"):
            self.enable_kimi_webbridge = True
        return self

    @model_validator(mode="after")
    def reject_changeme_in_production(self) -> Self:
        if self.environment != "production":
            return self

        invalid_fields = [
            field_name
            for field_name in self._production_secret_fields
            if self._is_placeholder(getattr(self, field_name))
        ]
        if invalid_fields:
            joined_fields = ", ".join(sorted(invalid_fields))
            msg = f"Production settings cannot use CHANGEME for: {joined_fields}"
            raise ValueError(msg)
        if not self.action_payload_encryption_required:
            msg = "Production ActionRequest payload encryption must be required."
            raise ValueError(msg)
        if self.enable_openshell_sandbox:
            if not self.openshell_require_human_approval:
                msg = "Production OpenShell sandbox requires human approval."
                raise ValueError(msg)
            if self.openshell_max_runtime_seconds > 900:
                msg = "Production OpenShell max runtime must be <= 900 seconds."
                raise ValueError(msg)
            if self.openshell_allow_network:
                msg = "Production OpenShell network access must be disabled."
                raise ValueError(msg)
        if self.deepagents_enable_memory and not self.deepagents_memory_require_approval:
            msg = "Production DeepAgents memory requires human approval."
            raise ValueError(msg)
        if self.enable_browser_automation:
            if not self.require_human_approval_for_external_actions:
                msg = "Production browser automation requires human approval."
                raise ValueError(msg)
            if not self.browser_headless_default:
                msg = "Production browser automation must default to headless."
                raise ValueError(msg)
        if (
            self.enable_kimi_webbridge
            and self.kimi_webbridge_allow_mutations
            and not self.kimi_webbridge_require_approval
        ):
            msg = (
                "Production Kimi WebBridge mutations require KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true."
            )
            raise ValueError(msg)
        if self.enable_computer_actions and not self.require_human_approval_for_external_actions:
            msg = "Production computer actions require human approval."
            raise ValueError(msg)
        if self.gmail_send_enabled and not self.require_human_approval_for_external_actions:
            msg = "Production Gmail send requires human approval."
            raise ValueError(msg)
        if self.enable_email_send and not self.require_human_approval_for_external_actions:
            msg = "Production email send requires human approval."
            raise ValueError(msg)
        if self.mail_enabled and not self.mail_require_approval_for_send:
            msg = "Production personal mail send requires human approval."
            raise ValueError(msg)
        if self.godaddy_enabled and not self.require_human_approval_for_external_actions:
            msg = "Production GoDaddy actions require human approval."
            raise ValueError(msg)
        if (
            self.enable_google_calendar_write
            and not self.require_human_approval_for_external_actions
        ):
            msg = "Production Google Calendar writes require human approval."
            raise ValueError(msg)
        if self.enable_google_drive_write and not self.require_human_approval_for_external_actions:
            msg = "Production Google Drive writes require human approval."
            raise ValueError(msg)
        if self.enable_research_orchestrator and self.research_persistence_backend != "postgres":
            msg = "Production Research Orchestrator requires RESEARCH_PERSISTENCE_BACKEND=postgres."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_external_capability_settings(self) -> Self:
        if self.action_payload_encryption_required and self._is_placeholder(
            self.action_payload_encryption_key
        ):
            msg = "Action payload encryption requires ACTION_PAYLOAD_ENCRYPTION_KEY."
            raise ValueError(msg)
        if self.browser_session_ttl_seconds < 30:
            msg = "Browser session TTL must be at least 30 seconds."
            raise ValueError(msg)
        if self.browser_max_pages_per_task < 1:
            msg = "Browser max pages per task must be positive."
            raise ValueError(msg)
        if self.computer_max_files_per_plan < 1 or self.computer_max_files_per_plan > 5000:
            msg = "Computer max files per plan must be between 1 and 5000."
            raise ValueError(msg)
        if self.godaddy_max_requests_per_minute < 1 or self.godaddy_max_requests_per_minute > 60:
            msg = "GoDaddy max requests per minute must be between 1 and 60."
            raise ValueError(msg)
        if (self.gmail_read_enabled or self.gmail_send_enabled) and (
            self._is_placeholder(self.gmail_client_id)
            or self._is_placeholder(self.gmail_client_secret)
        ):
            msg = "Gmail integration requires GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET."
            raise ValueError(msg)
        if self.microsoft_mail_enabled and (
            self._is_placeholder(self.microsoft_client_id)
            or self._is_placeholder(self.microsoft_client_secret)
        ):
            msg = (
                "Microsoft mail integration requires MICROSOFT_CLIENT_ID and "
                "MICROSOFT_CLIENT_SECRET."
            )
            raise ValueError(msg)
        if (
            self.mail_enabled
            and self.mail_godaddy_enabled
            and self._is_placeholder(self.mail_godaddy_password)
        ):
            msg = "MAIL_GODADDY_PASSWORD is required when personal GoDaddy mail is enabled."
            raise ValueError(msg)
        if self.godaddy_enabled and (
            self._is_placeholder(self.godaddy_api_key)
            or self._is_placeholder(self.godaddy_api_secret)
        ):
            msg = "GoDaddy integration requires GODADDY_API_KEY and GODADDY_API_SECRET."
            raise ValueError(msg)
        if (self.enable_google_calendar or self.enable_google_drive) and (
            self._is_placeholder(self.google_client_id)
            or self._is_placeholder(self.google_client_secret)
        ):
            msg = "Google Calendar/Drive require GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            raise ValueError(msg)
        if self.enable_maps_routing and self._is_placeholder(self.google_maps_api_key):
            msg = "Maps routing requires a real GOOGLE_MAPS_API_KEY."
            raise ValueError(msg)
        if self.voice_enabled and self._is_placeholder(self.elevenlabs_api_key):
            msg = "Voice (VOICE_ENABLED) requires a real ELEVENLABS_API_KEY."
            raise ValueError(msg)
        if self.enable_captcha_solving and self._is_placeholder(self.capsolver_api_key):
            msg = "Captcha solving (ENABLE_CAPTCHA_SOLVING) requires a real CAPSOLVER_API_KEY."
            raise ValueError(msg)
        if self.enable_kimi_webbridge:
            from urllib.parse import urlparse

            parsed = urlparse(self.kimi_webbridge_url)
            host = (parsed.hostname or "").lower()
            if host not in {"127.0.0.1", "localhost", "::1"}:
                msg = (
                    "KIMI_WEBBRIDGE_URL must target localhost (the daemon is local). "
                    f"Refusing host {host!r}."
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_deepagents_memory_limits(self) -> Self:
        if self.deepagents_memory_max_items_per_user < 1:
            msg = "DeepAgents memory max items per user must be positive."
            raise ValueError(msg)
        if not self.deepagents_memory_consolidation_cron.strip():
            msg = "DeepAgents memory consolidation cron cannot be empty."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_cors_allow_origins(self) -> Self:
        """Wildcard origins are incompatible with credential cookies Authorization header flows."""
        if any(origin == "*" for origin in self.cors_allow_origins):
            msg = "CORS_ALLOW_ORIGINS must not contain '*' because credentials are enabled."
            raise ValueError(msg)
        return self

    @staticmethod
    def _is_placeholder(value: object) -> bool:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        return isinstance(value, str) and "CHANGEME" in value


settings = Settings()
