# 33 · Release Candidate Package — Cognitive OS

> **Estado del release candidate: APROBADO** para uso comercial
> local-first en PC dedicado mono-operador.
>
> Branch: `codex/commercial-zero-friction-hardening` · ver `git log -1`
> para el commit certificado. Snapshot canónico:
> `docs/audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`.

## 1. Perfil recomendado

```env
OPERATOR_PROFILE=dedicated_local
LOCAL_AUTONOMY_MODE=full
CODE_DIRECTOR_BUDGET_MODE=soft
```

## 2. Comandos para levantar

```bash
# Una sola línea (Linux/Wayland)
~/Escritorio/Levantar\ Cognitive\ OS.sh

# Reset limpio
~/Escritorio/Reiniciar\ Cognitive\ OS.sh

# Estado actual
~/Escritorio/Estado\ Cognitive\ OS.sh

# Apagar todo
~/Escritorio/Detener\ Cognitive\ OS.sh
```

Equivalente CLI maestro:
`/home/jgonz/Escritorio/cognitive-os.sh {start|restart|stop|status|doctor|logs <comp>}`.

## 3. Comandos para verificar tras arranque

```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
      python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -s http://127.0.0.1:8000/system/info -H "Authorization: Bearer $JWT" | python3 -m json.tool
curl -s http://127.0.0.1:8000/system/readiness -H "Authorization: Bearer $JWT" | python3 -m json.tool
curl -s http://127.0.0.1:8000/system/mcp -H "Authorization: Bearer $JWT" | python3 -m json.tool
curl -sI http://localhost:3001/ | head -3
```

## 4. Comandos QA

```bash
cd /home/jgonz/Escritorio/PROYECTO\ COGNITIVE\ OS/cognitive-os

# Gate principal (947+3 = 950 passed esperado)
bash scripts/full-qa.sh

# Stress (3 pasadas, debe ser estable)
bash scripts/stress-qa.sh 3

# E2E frontend (zero-friction: no exportar COGOS_JWT)
cd frontend && unset COGOS_JWT && npx playwright test --reporter=list

# Launchers
bash scripts/verify_desktop_launchers.sh

# Live read-only (opt-in)
LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh
```

## 5. Cómo revisar health

```bash
# Pasivo (no quema tokens)
curl -s http://127.0.0.1:8000/health/dashboard -H "Authorization: Bearer $JWT"

# Live (gasta tokens; click "Verificar en vivo" en UI o:)
curl -sX POST http://127.0.0.1:8000/health/verify -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -d '{}'
```

`overall=configured` es **honesto** cuando los probes live no se ejecutaron.
`overall=ok` requiere que cada componente con `verify_live` haya pasado
prueba real.

## 6. Cómo revisar logs

```bash
# Per-componente
tail -100 ~/.cognitive-os/logs/api.log
tail -100 ~/.cognitive-os/logs/worker.log
tail -100 ~/.cognitive-os/logs/beat.log
tail -100 ~/.cognitive-os/logs/frontend.log
tail -100 ~/.cognitive-os/logs/telegram.log
tail -100 ~/.cognitive-os/logs/kimi.log

# Via launcher
~/Escritorio/cognitive-os.sh logs api
~/Escritorio/cognitive-os.sh logs worker
~/Escritorio/cognitive-os.sh logs beat
```

## 7. Cómo operar frontend

URL: `http://localhost:3001`

- JWT se autoprovisiona (no necesitas pegarlo).
- 20 tabs en sidebar; `localStorage["cogos.tab"]` persiste activa.
- Command palette `Ctrl/Cmd+K` desde cualquier foco.
- Notificaciones: botón header. ESC para cerrar.
- PWA instalable: el navegador ofrece "Instalar Cognitive OS".

## 8. Cómo operar Telegram

- Bot `@Socio_dimn_bot` (configurado en `.env`).
- `TELEGRAM_AUTHORIZED_USER_IDS` debe contener tu user_id.
- 37 slash commands + modo conversacional sin slash en `dedicated_local`.
- `/help` lista comandos disponibles.

## 9. Cómo operar Action Plane

1. Capabilities: `GET /actions/capabilities`.
2. Preview (read-only): `POST /actions/{tipo}/preview` o `/preview/request`.
3. Request (con persistencia): `POST /actions/{tipo}/request`.
4. Approve: `POST /approvals/{id}/approve` (auto en reversibles).
5. Dispatch: automático tras approve (o explícito vía endpoint).
6. Audit: `GET /audit/events?limit=N`.

## 10. Cómo operar mail sin envío (contrato)

- `POST /mail/sync/dispatch` — encola sync read-only.
- `POST /mail/digest/preview` — genera digest desde mensajes locales (sin
  sync; `sync_first=false`).
- `POST /mail/digest/dispatch` — encola digest en worker.
- **Para enviar**: requiere **simultáneamente**
  `ENABLE_EMAIL_SEND=true` + `MAIL_ALLOW_EXPLICIT_SEND=true` +
  body con `explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`.

## 11. Cómo correr Document Analysis

```bash
JOB_ID=$(uuidgen)
curl -sX POST http://127.0.0.1:8000/document-analysis/run \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$JOB_ID\",\"thread_id\":\"manual\",
       \"doc_ids\":[\"<uuid del doc>\"],\"query\":\"...\",
       \"modes\":[\"evidence_matrix\",\"timeline\",\"contradictions\"]}"
```

UI: tab "Document Analysis" en frontend.

## 12. Cómo correr Research

```bash
curl -sX POST http://127.0.0.1:8000/research/runs \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"query":"...","modes":[...]}'
```

SSE en `/research/runs/{id}/events`. UI: tab "Research".

## 13. Cómo correr Code Director

```bash
curl -sX POST http://127.0.0.1:8000/code-director/run \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"objective":"...","adapter_preference":{"default_adapter":"claude_code"}}'
```

UI: tab "Code Director".

## 14. Cómo recuperar de fallos

- Worker no procesa: `~/Escritorio/Reiniciar Cognitive OS.sh`.
- ActionRequest stuck: `reap_stuck_action_requests_task.apply()` o
  esperar al reaper automático.
- Approval vencida: `approval_reaper` la marca; volver a generar.
- Health degraded: revisa `/system/readiness.gaps[*].remediation`.
- Conteos drift: `python3 scripts/sync_doc_counts.py` (sin `--check`)
  regenera.

## 15. Qué NO hacer

- No correr `npm ci` en `frontend/` mientras Playwright esté corriendo
  (el guard de `full-qa.sh` ya lo evita).
- No correr tests con `DATABASE_URL` apuntando a producción.
- No exportar `MAIL_ALLOW_EXPLICIT_SEND=true` sin confirmación
  explícita.
- No forzar `GODADDY_ALLOW_PRODUCTION_WRITES=true` sin dominio en
  allow-list.
- No introducir `approval_require_four_eyes=true` en `dedicated_local`
  (rompe cero fricción).
- No tocar `cognitive-os-backup-*/` o `cognitive-os-snapshot-*/`.

## 16. Riesgos residuales

| Riesgo | Mitigación |
|---|---|
| TestSprite plugin satura API en runs completos de 28 TC | Ejecutar en batches de 5–10 TCs (lo aplicamos en pasadas 2/3) |
| MCP adapter upstream con 2 warnings deprecation | Migrar adaptador cuando lib publique fix; no bloqueante |
| `primary_llm` puede tardar > 10s en cold-start extremo | Operador puede subir `HEALTH_LLM_PROBE_TIMEOUT_SECONDS` o reintentar `/health/verify` |

Sin otros riesgos residuales abiertos.

## 17. Checklist de uso diario

- [ ] Stack vivo (`~/Escritorio/Estado Cognitive OS.sh`).
- [ ] `/system/readiness` 14/14 unlocked.
- [ ] `/system/mcp` 5/5 servers.
- [ ] Frontend `http://localhost:3001` carga.
- [ ] Telegram bot responde a `/help`.
- [ ] No hay errores en `~/.cognitive-os/logs/`.

## 18. Checklist de actualización

- [ ] `git status` clean antes de pull.
- [ ] `git pull --ff-only` (no merge automático).
- [ ] `cd backend && uv run alembic upgrade head` si hay nuevas migraciones.
- [ ] `cd frontend && npm ci` si hay cambios en `package-lock.json`.
- [ ] `~/Escritorio/Reiniciar Cognitive OS.sh`.
- [ ] `bash scripts/full-qa.sh` para verificar verde.

## 19. Checklist de rollback

- [ ] `git checkout <commit-conocido-verde>` (ver `git log --oneline`
      para HEADs anteriores certificados).
- [ ] Si Alembic migró: `cd backend && uv run alembic downgrade <revisión-anterior>`.
- [ ] `~/Escritorio/Reiniciar Cognitive OS.sh`.
- [ ] Verificar `/system/info.git_commit` matchea rollback.

## 20. Checklist de cero fricción

- [ ] `OPERATOR_PROFILE=dedicated_local`.
- [ ] `/system/info.require_human_approval_for_external_actions=false`.
- [ ] `/system/info.approval_require_four_eyes=false`.
- [ ] `/system/readiness.target_capabilities_unlocked=14/14`.
- [ ] Playwright corre sin exportar `COGOS_JWT`.

## 21. Checklist de health/readiness

- [ ] `/health/dashboard` 18 componentes.
- [ ] `/health/dashboard.operational_backlog=ok`.
- [ ] `/system/readiness.gaps=[]`.
- [ ] `/system/mcp` 5/5 conectados.

## 22. Checklist de workers/reapers

- [ ] Celery worker activo en 5 queues.
- [ ] Beat activo con 13 jobs.
- [ ] `operational_backlog.metadata.beat_lag_minutes < 120`.
- [ ] `operational_backlog.metadata.action_requests_stuck=0`.

## 23. Checklist de mail read-only

- [ ] `ENABLE_EMAIL_SEND=false` o ausente.
- [ ] `MAIL_ALLOW_EXPLICIT_SEND` ausente.
- [ ] `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`.
- [ ] `POST /mail/messages/.../approve-send` retorna HTTP 409 con
      mensaje exacto.

## 24. Checklist de docs/counts

- [ ] `python3 scripts/sync_doc_counts.py --check` → OK.
- [ ] `CURRENT_STATE.md` snapshot al día.
- [ ] `git diff --check` clean.
