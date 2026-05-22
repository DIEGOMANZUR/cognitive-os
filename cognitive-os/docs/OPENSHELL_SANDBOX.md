# OpenShell Sandbox (referencia técnica)

> **Estado actual (2026-05-22):** integración separada e independiente,
> documentada para el modelo local dedicado. Aunque el producto prioriza
> fricción casi nula por sobre seguridad estricta, OpenShell sigue siendo
> un sandbox opcional: si se enciende, debe fallar de forma explícita,
> registrar JobEvents/AuditEvents y no simular que ejecutó cuando el vendor,
> Docker o gateway no están disponibles.
>
> **Histórico (2026-05-20, Fase 74):** integración separada e independiente
> de OpenHarness y del carril mail. OpenShell se ejecuta vía un *vendor*
> externo dentro de Docker; OpenHarness corre en proceso del backend
> cuando se activa el extra. Worker dedicado:
> `cognitive_os.run_openshell_task` (queue `agent_longrun`). El frontend
> `SandboxView` envía el campo `purpose` requerido por el endpoint y
> consume estados reales (`pending`, `running`, `completed`, `failed`).
> Off por default (`ENABLE_OPENSHELL_SANDBOX=false`).
>
> **Fase 71-D:** el dispatch de OpenShell desde la decisión de approval
> (`_decide_approval` en REST y Telegram) pasa ahora por el helper
> compartido `dispatch_celery_with_audit` — emite un `JobEvent`
> `openshell_dispatch_submitted` o `_dispatch_failed`, de modo que un
> broker caído nunca deja la aprobación decidida y el job en silencio.
> Si te confunden los nombres, leé primero "Qué no es" y
> `docs/OPENHARNESS_FUSION.md`.

OpenShell DeepAgent es un sandbox opcional para ejecutar codigo o comandos controlados desde
Cognitive OS. Cognitive OS sigue siendo la torre de control: decide si una tarea puede entrar al
sandbox, registra auditoria, crea jobs y exige aprobacion humana cuando hay riesgo.

## Que no es

OpenShell no reemplaza el orquestador LangGraph, DeepAgents Python, Celery, Postgres, RAG ni el
panel de aprobaciones. **OpenHarness** (opcional, ruta `research`) es otra integración de ejecución
de herramientas; ver `OPENHARNESS_FUSION.md`. Tampoco recibe acceso al repo completo, al home del usuario, a `.env` ni a
carpetas sensibles.

## Arquitectura

- API/Celery reciben una `OpenShellTask`.
- `openshell_policy.py` valida red, rutas, limites y archivos sensibles.
- `OpenShellAdapter` revisa si el sandbox esta habilitado, si existe el vendor oficial y si Docker
  / gateway estan disponibles.
- Si la tarea requiere aprobacion, se crea `HumanApproval` y no se ejecuta nada.
- Si esta aprobada y disponible, la ejecucion se delega al gateway/CLI oficial de OpenShell con
  argumentos en lista, timeout y salida truncada.

## Variables

Las variables estan documentadas en `.env.example` bajo `OpenShell Sandbox`.

- `ENABLE_OPENSHELL_SANDBOX=false` mantiene la integracion apagada por defecto.
- `OPENSHELL_PROJECT_DIR=./experiments/openshell-deepagent` ubica el experimento aislado.
- `OPENSHELL_SANDBOX_NAME=cognitive-os-sandbox` nombra el sandbox.
- `OPENSHELL_GATEWAY_URL` puede apuntar a un gateway local si se conoce el puerto.
- `OPENSHELL_ALLOW_NETWORK=false` bloquea red por defecto.
- `OPENSHELL_REQUIRE_HUMAN_APPROVAL=true` exige aprobacion por defecto.
- `NVIDIA_API_KEY=CHANGEME` queda como placeholder. No commitear claves reales.

OpenShell puede soportar otros modelos/proveedores mediante su configuracion propia. Esa
configuracion debe vivir fuera del repo o en archivos locales ignorados, nunca con secretos
versionados.

## Clonar e instalar

El vendor oficial va en:

```bash
git clone --depth 1 https://github.com/langchain-ai/openshell-deepagent \
  experiments/openshell-deepagent/vendor/openshell-deepagent
bash scripts/openshell_setup.sh
```

Si el clone falla, Cognitive OS sigue funcionando. El adaptador devolvera
`OpenShellDeepAgentNotInstalled`.

## Gateway y estado

Comandos inspeccionados del repo oficial:

```bash
bash scripts/openshell_start_gateway.sh
bash scripts/openshell_status.sh
bash scripts/openshell_stop_gateway.sh
```

El repo oficial tambien expone:

```bash
cd experiments/openshell-deepagent/vendor/openshell-deepagent
uv run openshell sandbox create --name cognitive-os-sandbox --keep
uv run openshell policy get cognitive-os-sandbox --full > policy.yaml
uv run openshell policy set cognitive-os-sandbox --policy policy.yaml --wait
```

Para ejecutar el agente real, el README oficial indica levantar la app LangGraph del vendor:

```bash
cd experiments/openshell-deepagent/vendor/openshell-deepagent
uv run langgraph dev --allow-blocking
```

El adaptador de Cognitive OS no inventa un comando one-shot si la CLI instalada no lo expone.
Primero valida politica, aprobacion, Docker/gateway y vendor; la ejecucion real debe conectarse a
un gateway/app explicito.

## Policy YAML

La plantilla esta en:

```text
experiments/openshell-deepagent/policy/sandbox_policy.template.yaml
```

La plantilla deshabilita red, limita lectura a `/sandbox/input` y escritura a `/sandbox/output` y
`/sandbox/work`, y bloquea rutas de home/root y archivos de entorno o claves. Si la policy real de
OpenShell cambia, exportar una policy real con el comando oficial y adaptar la plantilla.

## Archivos permitidos

Los inputs deben estar bajo `OPENSHELL_ALLOWED_INPUT_DIR`. Los outputs permitidos se copian o
registran bajo `OPENSHELL_ALLOWED_OUTPUT_DIR`. Cualquier path traversal, ruta absoluta externa,
symlink peligroso o archivo sensible se bloquea.

## Smoke Test

```bash
cd backend
uv run python ../scripts/openshell_run_smoke.py
```

Con la configuracion por defecto el resultado sera `not_enabled` o `needs_approval`; eso es
esperado. Para ejecucion real hay que habilitar el sandbox, arrancar Docker/gateway y aprobar la
tarea segun politica.

## API

- `GET /sandbox/openshell/status`
- `POST /sandbox/openshell/run`

Ambos requieren JWT. Para aprobar o rechazar se usa el flujo central:

- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`

## Troubleshooting

- `not_enabled`: `ENABLE_OPENSHELL_SANDBOX=false`.
- `vendor_missing`: falta el clone oficial.
- `gateway_unavailable`: Docker no corre o el gateway no esta activo.
- `blocked`: la policy rechazo red, rutas, secretos, documentos sensibles o limites excesivos.
- `needs_approval`: revisar la bandeja de aprobaciones.

## Riesgos conocidos

OpenShell habilita ejecucion de codigo dentro de un sandbox. Aun con sandboxing, se trata como una
accion sensible. No se habilita red libre por defecto, no se monta el repo completo y no se pasan
secretos.

## OpenShell nunca debe recibir documentos judiciales/personales sin aprobación humana explícita

Esta regla es absoluta salvo aprobación humana explícita y trazable en `HumanApproval`.
