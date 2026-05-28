# Seguridad

> **Estado V2.0 (2026-05-27, post cierre absoluto Prompt 7 V2.0).**
> Cognitive OS quedó certificado como **APTO COMERCIAL LOCAL-FIRST** para
> PC dedicado. Working tree limpio sobre commit V2.0 (`git log -1`). Gates V2.0:
> `full-qa.sh` **1232 passed**, `stress-qa.sh 5` **5/5 verde × 1232 × 2 ciclos**
> (flakiness 0%), `npx playwright test` **44 passed × 2 ciclos**,
> `full-qa-live.sh` **8 passed**, `openapi_readonly_smoke.py` **70/70**.
> Doc audit firmado: [`cognitive-os/docs/audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`](../audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md).


> **Estado actual (2026-05-22):** estas reglas raíz siguen protegiendo
> secretos y repositorio, pero no describen el objetivo operativo principal
> de Cognitive OS en este PC dedicado. Diego priorizó fricción casi nula por
> sobre seguridad estricta: Edge real/Kimi WebBridge, filesystem local y
> auto-resolución en `dedicated_local/full` son decisiones aceptadas. Lo que
> no se relaja: no guardar secretos en Markdown, no romper trazabilidad, no
> ocultar fallos y no enviar correos/drafts en el flujo normal.
>
> **Histórico (2026-05-15, Fase 33):** reglas raíz del workspace
> OpenCode/Cognitive OS. Los secretos viven exclusivamente en `.env`,
> `.env.local`, gestores de secretos o servicios locales con permisos
> restrictivos; nunca en Markdown ni `opencode.json`. Auditoría más reciente
> confirma que los MCPs usan `{env:VAR}` y que las acciones externas no deben
> rodear aprobación humana. Google Calendar/Drive writes reales pasan por
> `ActionRequest` + aprobación; Postgres/Redis/Weaviate/Neo4j quedan ligados a
> `127.0.0.1` por defecto. Fase 33 añade RBAC explícito, cifra payloads
> ejecutables de `ActionRequest` en producción y permite persistir runs de
> research en Postgres. Los wrappers en `.opencode/bin/` ya usan `{env:VAR}` o
> variables del entorno sin fallback secreto.

## Reglas obligatorias

- Jamas commitear `.env` ni archivos derivados con credenciales reales.
- Rotar claves si aparecen en logs, prompts, reportes, tickets o cualquier otro registro.
- No enviar payloads sensibles a servicios externos sin redaccion previa.
- Las acciones externas requieren aprobacion humana explicita en `strict`;
  en `dedicated_local/full` pueden auto-resolverse si el backend lo permite
  y el operador acepta ese riesgo.
- Mail es excepción: lectura/digest/propuestas por defecto; no drafts ni
  envío automático.
- Producción exige `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true` y una
  `ACTION_PAYLOAD_ENCRYPTION_KEY` real.
- Admin se concede por roles/IDs explícitos; nunca por `ADMIN_USER_IDS` vacío.
- `opencode.json` debe usar referencias `{env:VAR}` para MCPs y nunca tokens inline.
- No documentar contraseñas de OpenChamber, tokens MCP, claves LLM, SMTP/IMAP ni OAuth.
- Si un token apareció en un archivo versionado o visible en logs, rotarlo aunque luego se haya saneado.

## Pre-commit

Este repositorio queda preparado para usar `gitleaks` mediante pre-commit.

Instalacion local sugerida si las herramientas no estan disponibles:

```bash
python -m pip install pre-commit
# Instalar gitleaks: https://github.com/gitleaks/gitleaks#installing
pre-commit install
pre-commit run --all-files
```

## Estado 2026-05-15

- **Wrappers MCP saneados**: `.opencode/bin/weaviate-mcp.sh`,
  `tavily-mcp.sh`, `exa-mcp.sh` cargan `.env.local` y resuelven flags en
  runtime. Sin secretos inline.
- **`opencode.json`**: usa `{env:VAR}` para todos los MCPs (`huggingface`,
  `supermemory`, `context7`, `langsmith`, `github-official`, `tavily`,
  `brave-search`, `exa`, `weaviate`, `neo4j`).
- **Mail GoDaddy/Gmail**: la contraseña IMAP/SMTP vive solo en
  `cognitive-os/.env` (ignorado, permisos `600`); nunca en docs ni progreso.
- **Política Action Plane**: `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`,
  `ENABLE_BROWSER_AUTOMATION` y `ENABLE_COMPUTER_ACTIONS` arrancan en `false`
  o requieren aprobación humana antes de ejecución real.
- **Google Ops**: Calendar/Drive writes directos están bloqueados; usar endpoints
  `/request` aprobables. Producción exige aprobación humana si los write flags
  de Google están activos.
- **Infra local-only**: Postgres, Redis, Weaviate y Neo4j publican sólo en
  `127.0.0.1` en `cognitive-os/infra/docker-compose.yml`.
- **Reglas OpenCode endurecidas**: lecturas por bash (`cat/find/rg/grep`)
  movidas a `ask`; `deny` cubre `rm -rf`, `git reset --hard`,
  `git push --force`, `docker system prune`, `terraform destroy`,
  `kubectl delete`.
- **Fase 33**: `payload_executable` queda cifrable con Fernet y requerido en
  producción; `/langsmith/*` queda admin-gated por defecto; `research` puede
  persistir snapshots/eventos en Postgres con `RESEARCH_PERSISTENCE_BACKEND`.
