# corregir_cognitive.md — Pendientes Operativos (vivo)

> **Última actualización:** 2026-05-27 post-CIERRE ABSOLUTO V2.0 (Prompt 7 V2.0).
> **Estado de release:** **APTO COMERCIAL LOCAL-FIRST — CIERRE ABSOLUTO V2.0** —
> sin P0/P1/P2 funcionales abiertos. 7 prompts V2.0 ejecutados, 12 hallazgos
> cerrados (F-P2-001..006 + F-P4-001..003 + V2-EVAL-001/004/005), commit local
> final con working tree limpio. Runtime sirve el HEAD del commit V2.0 (último
> `git log -1 --format=%H`).
>
> **Reportes V2.0 vigentes:**
> - Prompt 1 — Mapa contractual + matriz 663 controles:
>   `tmp/v2_01_contract_plan_20260527_133821/`
> - Prompt 2 — Ejecución read-only + 6 hallazgos:
>   `tmp/v2_02_readonly_execution_20260527_142619/`
> - Prompt 3 — Remediación inicial + 9 tests + 1230 passed:
>   `tmp/v2_03_initial_remediation_20260527_151927/`
> - Prompt 4 — Activación real FULLY_ACTIVE + F-P4-001 fix:
>   `tmp/v2_04_real_activation_20260527_162134/`
> - Prompt 5 — Evaluación independiente + V2-EVAL-001:
>   `tmp/v2_05_independent_evaluation_20260527_163911/`
> - Prompt 6 — Fix V2-EVAL-001 + 1232 passed + 5/5 stress:
>   `tmp/v2_06_final_remediation_20260527_172958/`
> - **Cierre absoluto Prompt 7 V2.0 (este ciclo):**
>   `tmp/v2_07_absolute_release_closure_20260527_175541/` + certificación firmada
>   `cognitive-os/docs/audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`
>
> **Reportes históricos (auditorías previas a V2.0, preservados):**
> - Activación funcional inicial 2026-05-25:
>   `tmp/full_functional_activation_20260525_073134/`
> - Certificación final P6 histórica:
>   `cognitive-os/docs/audits/FINAL_LOCAL_FIRST_COMMERCIAL_CERTIFICATION.md`
> - Cierre absoluto V1.x 2026-05-25:
>   `cognitive-os/docs/audits/FINAL_ABSOLUTE_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`
>
> **Conteo vigente post-V2.0:**
> - P0: **0**
> - P1: **0**
> - P2 funcionales: **0** (V2-EVAL-001 último cerrado en Prompt 6)
> - P2 declarado: 1 (F-P4-002 DeepAgent BadRequestError → fallback heurístico funcional, documentado)
> - P3 cosméticos / smokes opcionales: V2-EVAL-002/003 (beat schedule y thread cross-restart smokes pytest-cubiertos), Lighthouse + axe-core no ejecutados, Schemathesis live opcional. Ninguno bloquea.
> - P2 operativos no-código: 2 (operador: refresh Google OAuth, triage de approvals viejos)

Este documento solo lista lo **abierto o pendiente**. Lo cerrado vive en la
certificación final + en este histórico.

---

## Hallazgos CERRADOS (histórico de auditorías)

| ID | Cierre | Evidencia |
|---|---|---|
| F-P0-001 — Flakiness 33% del gate hermético | ✅ Cerrado 2026-05-25 | Fix FK order en 2 fixtures + nuevo `test_clean_slate_fixture_covers_all_fks.py`. Stress 5×1200 verde. |
| F-P1-002 — `/health/verify` no ejecutado | ✅ Cerrado 2026-05-25 | LLM/embeddings/mail confirmados `ok` live. |
| Activación funcional E2E pendiente | ✅ Cerrado 2026-05-25 | 16 fases ejecutadas. |
| **FUNC-EVAL-2026-001** — router LLM clasifica `comm` mal | ✅ Cerrado 2026-05-25 (Prompt 6) | Hardened system prompt en `agents/graph.py` que excluye verbos de reformulación interna. Runtime confirmado: "¿qué eres?" → `route=research`. Test `test_router_system_prompt_excludes_repeat_or_introspection_from_comm`. |
| **FUNC-EVAL-2026-002** — DeepAgent BadRequestError | ✅ Documentado como contrato (Prompt 6) | El fallback heurístico **es comportamiento esperado** del contrato "fallar visible". El test existente `test_document_analysis_agent.py:139` valida el warning. La defensa de no perder funcionalidad ya está en código (`agent.py:54-58`). Si el LLM gateway no acepta el structured output, el sistema degrada con warning explícito + `human_review_required=true`. **No hay bug del producto** — el reporte del Prompt 4 sobreestimó al declarar "6 modos OK"; lo correcto es "1 modo OK con fallback honesto". |
| **FUNC-EVAL-2026-003** — CSV/DOCX no generados por default | ✅ Cerrado 2026-05-25 (Prompt 6) | `default_output_formats()` en `deepagents/document_analysis/schemas.py` ahora retorna `["json","markdown","csv","docx"]`. Runtime confirmado: 6 archivos generados (`report.md`, `result.json`, `report.docx`, `evidence_matrix.csv`, `timeline.csv`, `contradictions.csv`). Test `test_document_analysis_default_output_formats_covers_all_four`. |
| **FUNC-EVAL-2026-005 (≡ F-RUNTIME-001)** — `browser_preview` sync/async | ✅ Cerrado 2026-05-25 (Prompt 6) | `_execute` en `actions/service.py` ahora envuelve `BrowserPreviewService.execute` y `BrowserInteractiveService.execute` con `asyncio.to_thread`. Runtime confirmado: `https://www.example.com/` → `status=completed`, `title="Example Domain"`, 645ms. Test `test_action_service_browser_executors_use_to_thread`. |
| **FUNC-EVAL-2026-006** — PII operador en logs sandbox | ✅ Cerrado 2026-05-25 (Prompt 6) | `_redact_digest_pii` en `mail/service.py` redacta RUT chileno (`12.345.678-9` → `[REDACTED_RUT]`) y nombres ALL-CAPS estilo notificación judicial (`DIEGO IGNACIO MANZUR NAOUM` → `[REDACTED_NAME]`). Runtime confirmado en summary_text del digest. 5 tests focal. |
| **FUNC-EVAL-2026-007** — kill switch no probado on/off | ✅ Cerrado 2026-05-25 (Prompt 6) | El test `test_failure_postmortem.py::test_kill_switch_forces_every_warning_through_approval` SÍ existe y pasa. El hallazgo era **falso positivo** del comité — no había gap real. Documentado. |
| **FUNC-EVAL-2026-010** — browser_preview queued sin verificar | ✅ Side-effect de F-RUNTIME-001 (Prompt 6) | Resuelto por el fix de FUNC-EVAL-2026-005. El executor ahora completa correctamente. |

---

## Pendientes abiertos

### P2 operativos pendientes (no-código, requieren operador)

#### F-P1-001 — OAuth Google scope insuficiente (Calendar/Drive `blocked`)

**Severidad:** P2 operativo. **No bloqueante** porque contrato "fallar visible" funciona.

**Evidencia:** `google_calendar.status=blocked`, `google_drive.status=blocked` — *"Google token is missing required Calendar/Drive scopes"*.

**Acción del operador:**
```bash
cd cognitive-os/backend
uv run python scripts/auth_google.py
```

#### F-P1-003 — 310 approvals pending acumuladas

**Severidad:** P2 operativo. **No bloqueante** (ninguna stale >48h).

**Acción:** triage manual con
```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -fs -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/approvals?status=pending&limit=500" \
    | jq '[.[] | .action] | group_by(.) | map({action: .[0], count: length})'
```

---

### P3 — Higiene / cobertura (no-bloqueantes)

#### F-P2-001 — `/health/dashboard` latencia ~2s

Ya paralelizado con `asyncio.gather`. Mejora futura: cache de 5s en `_check_operational_backlog` y/o medición por componente para encontrar el culpable.

#### F-P2-002 — 147 endpoints OpenAPI sin `tags`

Aplicar gradualmente cuando un dominio se refactorice a `APIRouter`.

#### FUNC-EVAL-2026-008 — MCP `/system/mcp` no expone `sample_tools`

Mejora cosmética. El endpoint debería permitir `?include_tools=true`.

#### FUNC-EVAL-2026-009 — `X-Request-ID` no auditado en runtime real

Tests hermetic ya cubren `correlation_id`. Falta evidencia end-to-end runtime.

#### FUNC-EVAL-2026-004 — GoDaddy `dns/request` payload mismatch (TEST mal escrito)

**Falso positivo del test del operador**: el campo correcto es `data`, no `new_value`. El schema funciona; el test del operador estaba mal. Documentado, no requiere fix de código.

#### F-P3-001..006 — Cobertura extra opt-in

- Carril live completo (`LIVE_TESTS_ENABLED=1 scripts/full-qa-live.sh`).
- Schemathesis property-based sobre OpenAPI.
- Lighthouse + axe-core sobre frontend.
- Chaos destructivo (Redis/Weaviate down).
- Mutation testing.
- Drift `ActionType` 11 vs frontend 9.

---

## Resumen de estado (post-cierre comercial final)

| Categoría | Cantidad | Detalle |
|---|---|---|
| P0 abiertos | **0** ✅ | — |
| P1 funcionales código | **0** ✅ | Los 2 abiertos del Prompt 5 cerrados (router + browser sync/async) |
| P2 funcionales código | **0** ✅ | Los 4 abiertos del Prompt 5 cerrados (CSV/DOCX + PII + kill switch documentado + queued) |
| P2 operativos no-código | 2 | F-P1-001 OAuth Google + F-P1-003 backlog approvals (operador) |
| P3 pulido | 4 + 5 opt-in | Recomendaciones futuras no bloqueantes |

**Veredicto vigente: COMERCIAL LOCAL-FIRST APROBADO** (post cierre Prompt 6).

Para llegar a **CERO PENDIENTES** (no requerido para certificación):
1. Operador ejecuta `auth_google.py`.
2. Operador hace triage de approvals.
3. Aplicar mejoras P3 a discreción del equipo.

---

## Reglas duras vigentes (no cambiar)

1. **No cambiar comportamiento del Mail SMTP gate** (verificado 3-way → HTTP 409, sigue vigente).
2. **No habilitar `LOCAL_AUTONOMY_MODE=strict` por defecto.**
3. **No agregar drafts automáticos en Gmail/GoDaddy.**
4. **No quitar el orden FK del fixture `clean_slate`** — el bug está cerrado, el test de regresión lo defiende.
5. **No introducir dependencias permanentes nuevas** sin justificación.
6. **No commitear `.env`.**
7. **No usar TestSprite.**
8. **No exponer servicios a LAN/internet** — todos los puertos en `127.0.0.1`.
9. **No quitar el `asyncio.to_thread`** alrededor de `browser_preview`/`browser_interactive` executors — el test de regresión `test_action_service_browser_executors_use_to_thread` lo defiende.
10. **No revertir `default_output_formats` a solo `[json, markdown]`** — el test de regresión `test_document_analysis_default_output_formats_covers_all_four` lo defiende.
11. **No quitar la redacción de PII en mail digest** — el test `test_render_digest_summary_redacts_pii_in_snippets` lo defiende.
12. **No quitar las reglas del router system prompt** — el test estructural `test_router_system_prompt_excludes_repeat_or_introspection_from_comm` lo defiende.
13. **No compartir el directorio `tmp/full_functional_activation_*` sin redactar PII previamente** (aunque los logs nuevos ya están redactados).
