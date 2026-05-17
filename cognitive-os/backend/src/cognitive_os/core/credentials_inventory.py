"""Live inventory of credentials Cognitive OS expects from the operator.

The endpoint `/system/credentials-status` reads this list and reports for each
entry whether the credential is configured, which capability becomes
available when set, and where to obtain it. Values are NEVER returned — only
booleans and provenance — so the endpoint is safe to call from the operator
panel.

Adding a new credential: append a `CredentialSpec` here, run the test
suite, and the endpoint picks it up automatically. The matrix in
`docs/RUNBOOK.md` is documentation; this module is the runtime source.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, SecretStr

from cognitive_os.core.config import Settings
from cognitive_os.core.config import settings as default_settings
from cognitive_os.core.secrets import PLACEHOLDER


@dataclass(frozen=True)
class CredentialSpec:
    """Declarative description of one operator-supplied credential.

    `setting_attrs` are attributes of `Settings` to consult; `env_vars` are
    raw environment variables consulted when no Settings attribute exists
    (e.g. MCP wrappers exporting tokens directly).
    """

    name: str
    enables: str
    setting_attrs: tuple[str, ...]
    how_to_obtain: str
    optional: bool = True
    env_vars: tuple[str, ...] = field(default_factory=tuple)
    extra_check: Callable[[Settings], bool] | None = None


class CredentialStatus(BaseModel):
    name: str
    configured: bool
    optional: bool
    enables: str
    how_to_obtain: str
    missing_setting_attrs: list[str] = Field(default_factory=list)


class CredentialsInventoryResponse(BaseModel):
    total: int
    configured: int
    missing_required: int
    items: list[CredentialStatus]


# The canonical 21-entry matrix. Kept in the order operators tackle during
# bootstrap (infra → LLM stack → external APIs → optional integrations).
INVENTORY: tuple[CredentialSpec, ...] = (
    CredentialSpec(
        name="PRIMARY_LLM_API_KEY",
        enables="Chat, research, document analysis (DeepSeek by default).",
        setting_attrs=("primary_llm_api_key",),
        how_to_obtain="https://platform.deepseek.com → API keys.",
        optional=False,
    ),
    CredentialSpec(
        name="EMBEDDINGS_API_KEY",
        enables="RAG, semantic search, Weaviate-backed retrieval (Gemini by default).",
        setting_attrs=("embeddings_api_key",),
        how_to_obtain="https://aistudio.google.com/apikey → generar API key Gemini.",
        optional=False,
    ),
    CredentialSpec(
        name="JWT_SECRET",
        enables="JWT firma local del cockpit. init_env.sh lo genera automáticamente.",
        setting_attrs=("jwt_secret",),
        how_to_obtain="`bash scripts/init_env.sh` (genera secreto local).",
        optional=False,
    ),
    CredentialSpec(
        name="POSTGRES_PASSWORD",
        enables="Persistencia operacional + LangGraph checkpointer.",
        setting_attrs=("database_url",),
        how_to_obtain="`bash scripts/init_env.sh` (genera secreto local).",
        optional=False,
    ),
    CredentialSpec(
        name="NEO4J_PASSWORD",
        enables="Memoria de grafo / GraphRAG explicable.",
        setting_attrs=("neo4j_password",),
        how_to_obtain="`bash scripts/init_env.sh` (genera secreto local).",
        optional=False,
    ),
    CredentialSpec(
        name="WEAVIATE_API_KEY",
        enables="Búsqueda vectorial / híbrida (RAG).",
        setting_attrs=("weaviate_api_key",),
        how_to_obtain="`bash scripts/init_env.sh` (genera secreto local).",
        optional=False,
    ),
    CredentialSpec(
        name="ACTION_PAYLOAD_ENCRYPTION_KEY",
        enables="Cifrado at-rest del payload ejecutable (obligatorio en producción).",
        setting_attrs=("action_payload_encryption_key",),
        how_to_obtain=(
            'python -c "from cryptography.fernet import Fernet;'
            'print(Fernet.generate_key().decode())"'
        ),
        optional=True,
    ),
    CredentialSpec(
        name="GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET",
        enables="Gmail digest read-only.",
        setting_attrs=("gmail_client_id", "gmail_client_secret"),
        how_to_obtain=(
            "Google Cloud Console → APIs & Services → OAuth 2.0 Desktop client "
            "+ habilitar Gmail API."
        ),
    ),
    CredentialSpec(
        name="GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
        enables="Google Calendar + Drive (operables vía Action Plane).",
        setting_attrs=("google_client_id", "google_client_secret"),
        how_to_obtain=(
            "Google Cloud Console → OAuth 2.0 Desktop client (puede reutilizar "
            "el de Gmail) + habilitar Calendar y Drive APIs."
        ),
    ),
    CredentialSpec(
        name="GOOGLE_MAPS_API_KEY",
        enables="`/actions/maps/route` y geocoding.",
        setting_attrs=("google_maps_api_key",),
        how_to_obtain=(
            "Google Cloud Console → habilitar Maps API + Routes API y generar "
            "una API key restringida."
        ),
    ),
    CredentialSpec(
        name="ELEVENLABS_API_KEY",
        enables="`/voice/speak` y `/voice/transcribe`.",
        setting_attrs=("elevenlabs_api_key",),
        how_to_obtain="https://elevenlabs.io/app/settings/api-keys",
    ),
    CredentialSpec(
        name="GODADDY_API_KEY / GODADDY_API_SECRET",
        enables="`/actions/godaddy/dns/*` (empezar con OTE).",
        setting_attrs=("godaddy_api_key", "godaddy_api_secret"),
        how_to_obtain="https://developer.godaddy.com → Production keys.",
    ),
    CredentialSpec(
        name="MAIL_GODADDY_USERNAME / MAIL_GODADDY_PASSWORD",
        enables="Mail personal IMAP/SMTP GoDaddy con aprobación humana.",
        setting_attrs=("mail_godaddy_username", "mail_godaddy_password"),
        how_to_obtain=(
            "Webmail GoDaddy → IMAP/SMTP credentials (usar app password si la cuenta tiene 2FA)."
        ),
    ),
    CredentialSpec(
        name="TAVILY_API_KEY",
        enables="Búsqueda web (proveedor primario).",
        setting_attrs=("tavily_api_key",),
        how_to_obtain="https://app.tavily.com → API keys.",
    ),
    CredentialSpec(
        name="BRAVE_SEARCH_API_KEY",
        enables="Búsqueda web (fallback).",
        setting_attrs=("brave_search_api_key",),
        how_to_obtain="https://api.search.brave.com/app/keys",
    ),
    CredentialSpec(
        name="EXA_API_KEY",
        enables="Búsqueda semántica web (Exa).",
        setting_attrs=("exa_api_key",),
        how_to_obtain="https://dashboard.exa.ai/api-keys",
    ),
    CredentialSpec(
        name="HF_TOKEN",
        enables="Reranker Hugging Face / acceso a Hub.",
        setting_attrs=(),
        env_vars=("HF_TOKEN",),
        how_to_obtain="https://huggingface.co/settings/tokens (read scope).",
    ),
    CredentialSpec(
        name="LANGSMITH_API_KEY",
        enables="Trazas runtime de LangGraph en LangSmith.",
        setting_attrs=("langsmith_api_key",),
        how_to_obtain="https://smith.langchain.com/settings → API keys.",
    ),
    CredentialSpec(
        name="TELEGRAM_BOT_TOKEN",
        enables="Bot Telegram (slash commands).",
        setting_attrs=("telegram_bot_token",),
        how_to_obtain="@BotFather en Telegram → /newbot.",
    ),
    CredentialSpec(
        name="SUPERMEMORY_API_KEY",
        enables="Memoria personal cross-sesión.",
        setting_attrs=(),
        env_vars=("SUPERMEMORY_API_KEY",),
        how_to_obtain="https://app.supermemory.ai/dashboard.",
    ),
    CredentialSpec(
        name="GITHUB_PERSONAL_ACCESS_TOKEN",
        enables="MCP GitHub remoto.",
        setting_attrs=(),
        env_vars=("GITHUB_PERSONAL_ACCESS_TOKEN",),
        how_to_obtain=("https://github.com/settings/tokens?type=beta con `repo` read."),
    ),
)


def _setting_is_configured(app_settings: Settings, attr: str) -> bool:
    value = getattr(app_settings, attr, None)
    if value is None:
        return False
    if isinstance(value, SecretStr):
        raw = value.get_secret_value()
    elif isinstance(value, str):
        raw = value
    else:
        # Non-secret scalar with a default — treat as configured when truthy.
        return bool(value)
    if not raw:
        return False
    return PLACEHOLDER not in raw


def _env_var_is_configured(name: str) -> bool:
    raw = os.environ.get(name, "")
    return bool(raw) and PLACEHOLDER not in raw


def build_status(
    app_settings: Settings | None = None,
    inventory: Iterable[CredentialSpec] = INVENTORY,
    env: dict[str, str] | None = None,
) -> CredentialsInventoryResponse:
    """Walk the inventory and report which entries the operator still owes."""
    cfg = app_settings or default_settings
    items: list[CredentialStatus] = []
    env_view = env if env is not None else os.environ
    for spec in inventory:
        missing_attrs = [a for a in spec.setting_attrs if not _setting_is_configured(cfg, a)]
        missing_envs: list[str] = []
        if env is None:
            missing_envs = [v for v in spec.env_vars if not _env_var_is_configured(v)]
        else:
            missing_envs = [
                v
                for v in spec.env_vars
                if not env_view.get(v) or PLACEHOLDER in env_view.get(v, "")
            ]
        configured = not missing_attrs and not missing_envs
        if configured and spec.extra_check is not None:
            configured = bool(spec.extra_check(cfg))
        items.append(
            CredentialStatus(
                name=spec.name,
                configured=configured,
                optional=spec.optional,
                enables=spec.enables,
                how_to_obtain=spec.how_to_obtain,
                missing_setting_attrs=(missing_attrs + missing_envs) if not configured else [],
            )
        )
    configured_total = sum(1 for it in items if it.configured)
    missing_required = sum(1 for it in items if not it.configured and not it.optional)
    return CredentialsInventoryResponse(
        total=len(items),
        configured=configured_total,
        missing_required=missing_required,
        items=items,
    )
