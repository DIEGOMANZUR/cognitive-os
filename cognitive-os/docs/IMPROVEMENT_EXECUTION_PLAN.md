# Plan de perfeccionamiento (configuración, docs, seguridad operativa)

> **Estado actual (2026-05-15, Fase 33):** Fase A/B completas, mail personal
> operativo e infra de datos local-only por defecto. Fase C/D siguen como mejora opcional sin afectar QA.
> La revisión integral (Fase 28 de `task_plan.md`) cerró P0/P1 (secret
> hygiene, mail timeouts/redacción, `/config/public` ampliado, contratos
> frontend, AssistView, tests `/mail/*` y `/config/public`). Lo pendiente
> P2 ya cerró su núcleo comercial en Fase 33: auth/RBAC local explícito,
> cifrado at-rest de `payload_executable` y persistencia durable configurable
> del orquestador de research. Siguen como mejora incremental los controles
> visuales adicionales de variables, salud, colas y riesgos.

Alineado a la visión en `ARCHITECTURE.md` y `PROJECT_GUIDE.md`: **local-first,
auditable, human-in-the-loop** sobre acciones sensibles. Modelo de fusión
OpenHarness + LangGraph + DeepAgents: `OPENHARNESS_FUSION.md`.

## Estado

| Fase | Objetivo | Estado |
|------|----------|--------|
| A | Registro mecánico ENV ↔ `Settings`, checklist de operador, tabla versionada, pruebas de humo del script | **Hecho** |
| B | Comprobar en `pytest` que `SETTINGS_REGISTRY_TABLE.md` coincide con el script (sin deriva) | **Hecho** vía `backend/tests/test_dump_settings_registry.py::test_settings_registry_table_markdown_matches_generated_body`. Si introduces una variable nueva en `Settings` y olvidas regenerar la tabla, el test falla. |
| C | Ampliar mapa «variable → función» con generación parcial (p. ej. `rg` por atributo en pipeline de release) | Pendiente |
| D | Comando único `config doctor` que valide prod vs reglas (CORS, aprobaciones, OpenShell, OpenHarness) sin levantar uvicorn | Pendiente |
| E | Sala de máquinas comercial: exponer configuración no sensible, estado de colas, mail, riesgos y toggles operativos seguros en frontend/backend | Pendiente |

## Fase A (ejecutada)

- Script `backend/scripts/dump_settings_registry.py`: Markdown, `--tsv`, `--secrets`, `--out`.
- `docs/SETTINGS_REGISTRY_TABLE.md` generado con cabecera «no editar».
- `docs/OPERATOR_VARIABLE_CHECKLIST.md` con visión, procedimiento y mapa por subsistema.
- Test `backend/tests/test_dump_settings_registry.py` para no romper el contrato del script.

## Fase B (cerrada)

- `backend/tests/test_dump_settings_registry.py` ejecuta el script y compara
  el cuerpo Markdown contra el archivo versionado. Si añades una variable y
  olvidas correr `uv run python scripts/dump_settings_registry.py --out
  ../docs/SETTINGS_REGISTRY_TABLE.md`, `pytest` falla y el QA bloquea el
  cambio.

## Fase C

- Opcional: script que, dado un atributo `Settings`, liste archivos en
  `backend/src/cognitive_os` que referencian `settings.<attr>`.

## Fase D

- Extraer reglas ya presentes en `reject_changeme_in_production` y chequeos
  similares a una función pura importable desde CLI y desde tests, para
  diagnósticos previos al deploy.

## Fase E

- Diseñar un panel de operación que muestre variables no sensibles, proveedor
  LLM activo, colas Celery (`ingestion`, `agent_longrun`, `maintenance`, `mail`,
  `default`), estado de mail, Weaviate/Neo4j/Redis/Postgres y guardrails.
- Backend: endpoint público-autenticado de configuración operativa que redactor
  secretos y explique por qué una capacidad está `disabled`, `blocked`,
  `configured` o `ready`.
- Frontend: convertir `Configuration`/`Health`/`Mail` en una sala de máquinas:
  cards de estado, checklists de variables faltantes, acciones seguras (sync,
  dispatch, abrir logs) y enlaces a runbooks.
- QA: tests con providers fake, sin secretos y sin escribir fuera de storage
  local allow-listed.
