"""Operator readiness diagnostic.

Each operator profile (`strict`, `dedicated_local`) implies a *target capability
posture*. Many `.env` flags can silently disable capabilities the operator
expects — the readiness diagnostic surfaces them as a punch-list with the
exact env variable to flip + the capability it unlocks.

`LOCAL_AUTONOMY_MODE=full` now auto-flips the dedicated-local friction flags
inside the typed settings layer. This diagnostic remains useful as a live
punch-list for capabilities that still depend on credentials, external daemons
or an explicit operator opt-in.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings


class ReadinessGap(BaseModel):
    env_var: str = Field(description="Exact env variable to set in .env")
    current_value: str = Field(description="Current effective value")
    suggested_value: str = Field(description="Value that unlocks the capability")
    capability: str = Field(description="What you get by flipping this")
    severity: Literal["info", "suggestion", "warning"] = Field(
        default="suggestion",
        description="`info` = expected for this profile (no action). "
        "`suggestion` = capability available but the operator hasn't opted in. "
        "`warning` = the current value contradicts the profile's intent.",
    )


class ReadinessReport(BaseModel):
    operator_profile: str
    local_autonomy_mode: str
    summary: str
    target_capabilities_unlocked: int
    target_capabilities_total: int
    gaps: list[ReadinessGap]


def _gap_if(
    cond: bool,
    *,
    env_var: str,
    current: str,
    suggested: str,
    capability: str,
    severity: Literal["info", "suggestion", "warning"] = "suggestion",
) -> ReadinessGap | None:
    return (
        ReadinessGap(
            env_var=env_var,
            current_value=current,
            suggested_value=suggested,
            capability=capability,
            severity=severity,
        )
        if cond
        else None
    )


def compute_readiness(app_settings: Settings | None = None) -> ReadinessReport:
    """Build the readiness report for the active operator profile."""
    s = app_settings or settings
    profile = s.operator_profile
    autonomy_mode = getattr(s, "local_autonomy_mode", "guarded")

    gaps: list[ReadinessGap | None] = []

    if profile == "dedicated_local":
        # In dedicated_local the operator runs the agent on their own PC, with
        # their own credentials. The "no friction" intent means most read-only
        # capabilities should be on and several writes should be reachable
        # without per-action approval. The flags below are SUGGESTIONS — the
        # operator decides.
        gaps += [
            _gap_if(
                s.tools_readonly_mode,
                env_var="TOOLS_READONLY_MODE",
                current="true",
                suggested="false",
                capability=(
                    "Permite que el agente ejecute acciones write reales "
                    "(en dedicated_local/full se auto-aprueban y despachan)."
                ),
            ),
            _gap_if(
                not s.enable_browser_automation,
                env_var="ENABLE_BROWSER_AUTOMATION",
                current="false",
                suggested="true",
                capability=(
                    "Playwright headless para navegar dominios autorizados "
                    "(BROWSER_ALLOWED_DOMAINS)."
                ),
            ),
            _gap_if(
                not s.browser_allowed_domains,
                env_var="BROWSER_ALLOWED_DOMAINS",
                current="",
                suggested="*",
                capability="Playwright puede navegar cualquier host en PC dedicado.",
            ),
            _gap_if(
                not s.enable_computer_actions,
                env_var="ENABLE_COMPUTER_ACTIONS",
                current="false",
                suggested="true",
                capability=("computer_inventory / computer_organize sobre COMPUTER_ALLOWED_ROOTS."),
            ),
            _gap_if(
                not s.enable_google_calendar_write,
                env_var="ENABLE_GOOGLE_CALENDAR_WRITE",
                current="false",
                suggested="true",
                capability="Crear eventos en Google Calendar.",
            ),
            _gap_if(
                not s.enable_google_drive_write,
                env_var="ENABLE_GOOGLE_DRIVE_WRITE",
                current="false",
                suggested="true",
                capability=("Drive upload + ensure folder + organize (auto-aprueba reversibles)."),
            ),
            _gap_if(
                bool(s.kimi_webbridge_require_approval),
                env_var="KIMI_WEBBRIDGE_REQUIRE_APPROVAL",
                current="true",
                suggested="false",
                capability="Kimi WebBridge muta el Edge real sin approval intermedio.",
            ),
            _gap_if(
                not s.kimi_webbridge_allowed_domains,
                env_var="KIMI_WEBBRIDGE_ALLOWED_DOMAINS",
                current="",
                suggested="*",
                capability="Kimi WebBridge puede navegar cualquier host en el Edge real.",
            ),
            _gap_if(
                not s.kimi_webbridge_allow_mutations,
                env_var="KIMI_WEBBRIDGE_ALLOW_MUTATIONS",
                current="false",
                suggested="true",
                capability=("Kimi WebBridge puede hacer click/fill/evaluate en tu Edge real."),
            ),
            _gap_if(
                s.research_persistence_backend != "postgres",
                env_var="RESEARCH_PERSISTENCE_BACKEND",
                current=s.research_persistence_backend,
                suggested="postgres",
                capability=("Research runs persisten entre reinicios (memoria los pierde)."),
            ),
            _gap_if(
                not s.mail_enabled,
                env_var="MAIL_ENABLED",
                current="false",
                suggested="true",
                capability="Digest read-only de correo personal y propuestas de respuesta.",
            ),
            _gap_if(
                not s.mail_digest_enabled,
                env_var="MAIL_DIGEST_ENABLED",
                current="false",
                suggested="true",
                capability="Digest programado 10:00/20:00 Chile para los últimos 50 correos.",
            ),
            _gap_if(
                not s.enable_mcp_client,
                env_var="ENABLE_MCP_CLIENT",
                current="false",
                suggested="true",
                capability=(
                    "Cliente MCP: el DeepAgent carga tools dinámicas desde "
                    "servidores MCP declarados en MCP_SERVERS (Supermemory, "
                    "GitHub, filesystem propio, etc.)."
                ),
            ),
        ]
        if s.enable_kimi_webbridge:
            try:
                from cognitive_os.actions.kimi_webbridge import KimiWebBridgeService

                webbridge_status = KimiWebBridgeService(app_settings=s).status()
                gaps.append(
                    _gap_if(
                        webbridge_status.status != "ready",
                        env_var="KIMI_WEBBRIDGE_RUNTIME",
                        current=webbridge_status.status,
                        suggested="ready",
                        capability=(
                            webbridge_status.reason
                            or "Kimi WebBridge must have daemon and browser extension connected."
                        ),
                        severity="warning",
                    )
                )
            except Exception as exc:  # noqa: BLE001 - readiness must degrade visibly
                gaps.append(
                    ReadinessGap(
                        env_var="KIMI_WEBBRIDGE_RUNTIME",
                        current_value="error",
                        suggested_value="ready",
                        capability=f"Kimi WebBridge readiness probe failed: {type(exc).__name__}",
                        severity="warning",
                    )
                )
    else:
        # strict: las gaps son a la inversa — alertamos si algo se aflojó.
        gaps += [
            _gap_if(
                s.auto_approve_reversible_actions,
                env_var="AUTO_APPROVE_REVERSIBLE_ACTIONS",
                current="true",
                suggested="false",
                capability=("En strict, auto-approve no debería estar activo (multi-tenant)."),
                severity="warning",
            ),
            _gap_if(
                not s.require_human_approval_for_external_actions,
                env_var="REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS",
                current="false",
                suggested="true",
                capability=("Approval obligatorio para acciones externas en strict."),
                severity="warning",
            ),
        ]

    real_gaps: list[ReadinessGap] = [g for g in gaps if g is not None]
    target_total = len([g for g in gaps if g is None]) + len(real_gaps)
    unlocked = target_total - len(real_gaps)

    if profile == "dedicated_local":
        summary = (
            f"{unlocked}/{target_total} capacidades habilitadas. "
            f"Resolvé {len(real_gaps)} gap(s) de configuración/runtime "
            "para desbloquear el resto."
        )
        if not real_gaps:
            summary = "Sin fricción. Todas las capacidades del perfil están activas."
    else:
        summary = (
            "Strict profile activo."
            if not real_gaps
            else f"{len(real_gaps)} configuración(es) afloja(s) más de lo deseable "
            "para un perfil strict."
        )

    return ReadinessReport(
        operator_profile=profile,
        local_autonomy_mode=autonomy_mode,
        summary=summary,
        target_capabilities_unlocked=unlocked,
        target_capabilities_total=target_total,
        gaps=real_gaps,
    )
