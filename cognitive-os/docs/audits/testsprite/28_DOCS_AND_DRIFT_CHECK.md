# 28 · Docs and Drift Check — Cierre Absoluto

Fecha: 2026-05-23 07:25 UTC-4

## 1. Conteos canónicos vs código

`scripts/sync_doc_counts.py --check` → **OK: conteos canónicos sincronizados**.

Verificado live: 147 endpoints, 23 tareas Celery, 5 colas, 13 jobs beat,
20 migraciones (head `202605200003`), 20 vistas frontend, 37 commands
Telegram, 18 componentes health, 5/5 MCP servers (67 tools).

## 2. Drift cazado y corregido en esta fase

| Drift | Detectado en | Estado |
|---|---|---|
| `947 passed` (de pass 2) vs `950 passed` (real tras pass 3 con +3 tests health timeout) | 19 archivos canónicos | **CORREGIDO**: bulk sed en `README.md`, `CURRENT_STATE.md`, `USER_GUIDE.md`, `PROJECT_GUIDE.md`, `RUNBOOK.md`, `ARCHITECTURE.md`, `COGNITIVE_OS_GUIDE.md`, `FRONTEND_ARCHITECTURE.md`, `ZERO_FRICTION_OPERATING_MODEL.md`, `AGENT_LEARNING_PLAN.md`, `PERSONAL_ASSISTANT_ROADMAP.md`, `qa/MAP.md`, `qa/RUNBOOK.md`, `qa/FINAL_AUDIT_REPORT.md`, `ACCEPTANCE_CHECKLIST.md`, `AGENTS.md` (root), `docs/README.md`, `scripts/README.md`, `frontend/README.md` |
| "944 + 3 nuevos" → ahora son "944 históricos + 6 nuevos: 3 `eager_defaults` + 3 `health_llm_probe_timeout`" | mismos archivos | **CORREGIDO** |

Tras el sed, `sync_doc_counts.py --check` sigue OK.

## 3. Sweep de drift por tipo

### 3.1 Conteos numéricos

```bash
grep -rn "947 passed" cognitive-os/ AGENTS.md 2>/dev/null | \
  grep -v "audits/testsprite/\|test-results/\|.venv\|node_modules"
# → vacío (clean)
```

### 3.2 Conteos de tests del bloque histórico

`CURRENT_STATE.md` líneas 113-114 contienen `944 passed` dentro del bloque
**histórico `5953b40`** — correcto: era el snapshot de ese commit. Otros
`944 passed` con disclaimer histórico permanecen igual.

### 3.3 Referencias a 3/3 TestSprite advisory

`ACCEPTANCE_CHECKLIST.md:185` aún tiene `3/3 passed en smoke advisory` —
es contexto histórico documentado dentro del bloque "Verificado -
2026-05-22 (remediación audit comercial AUDIT-2026-A..H)". Decisión
consciente: mantenerlo como evidencia histórica. El header arriba ya
documenta la cobertura TestSprite acumulada actual (15 TC ejecutados).

### 3.4 Endpoints, scripts, variables documentados que no existen

Verificación cruzada `frontend ↔ backend OpenAPI`: **23/23 endpoints
matchean** (verificado en pass 2 con `OPENAPI_VS_FRONTEND.py`).

Scripts documentados en RUNBOOK: todos presentes (`scripts/full-qa.sh`,
`scripts/dev_up.sh`, etc.).

Variables `.env.example`: incluyen el nuevo `HEALTH_LLM_PROBE_TIMEOUT_SECONDS=10`
(pass 3).

Registry `docs/SETTINGS_REGISTRY_TABLE.md`: regenerado automáticamente
desde `core/config.py` con `scripts/dump_settings_registry.py`. Sin drift.

### 3.5 Modelos LLM / gateway documentados

| Documento | Modelo declarado | Real (`/config/public`) | Estado |
|---|---|---|---|
| `USER_GUIDE.md` header | gpt-5.5 primary+agent, gemini-3.1-pro-low secondary, glm-4.6v vision | gpt-5.5 + gemini-3.1-pro-low + glm-4.6v | ✓ |
| `CURRENT_STATE.md` | mismo | mismo | ✓ |

### 3.6 Tablas de comandos Telegram

`USER_GUIDE.md §5` lista 37 commands → matchea `ALL_TELEGRAM_COMMANDS` en
`tests/test_telegram_bot.py`. Sin drift.

### 3.7 Postura cero-fricción

Todos los docs canónicos declaran `dedicated_local/full` como perfil
principal y `strict` como secundario. Sin contradicción.

### 3.8 Mail contract

Todos los docs canónicos declaran read-only/no-draft/no-send + escape
hatch 3-flags. Verificado live en F-08 (HTTP 409 con mensaje exacto).

## 4. Resultado

**Cero drift documental** tras el bulk-fix del 947→950. `sync_doc_counts
--check` OK. Cobertura código↔docs total.
