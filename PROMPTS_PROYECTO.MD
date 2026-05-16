PARA EL SIGUIENTE PROYECTO, QUE TRATA DE AGENTES LANGRAPH Y COGNITIVE OS, TENDREMOS REGLAS QUE TE LAS DOY A CONTINUACION Y UN TOTAL APROXIMADO DE 14 PROMPTS QUE TE LOS IRÉ DANDO EN ORDEN. TODO LO QUE TE VAYA DICIENDO LO ENCONTRARÁS EN EL ARCHIVO LLAMADO PROMPTS_PROYECTO.MD POR SI TE SUGEN DUDAS O LO QUE SEA.


COMENZAMOS:

## Reglas maestras para el agente constructor

Copia estas reglas antes de cualquier prompt de construcción.

```text
REGLAS MAESTRAS DEL PROYECTO COGNITIVE OS

Actúa como ingeniero senior de producción. Tu objetivo no es impresionar: es construir una base estable, testeable y mantenible.

Reglas obligatorias:
1. No inventes APIs. Si una librería no calza con la versión instalada, revisa documentación local, inspecciona tipos o crea una mínima prueba reproducible.
2. No guardes secretos en código, prompts, logs, tests, fixtures ni .env.example.
3. Si detectas secretos en archivos existentes, detente y crea un reporte de seguridad sin repetir el secreto completo.
4. Todo módulo debe tener tests mínimos.
5. Las tareas deterministas deben ser funciones normales, no agentes.
6. Los agentes no pueden ejecutar acciones sensibles sin aprobación humana.
7. Todo trabajo largo debe ser job asíncrono con status consultable.
8. Toda ingesta documental debe preservar trazabilidad: doc_id, page, chunk_id, sha256 y source_path.
9. Todo resultado legal o factual debe incluir citas o marcar incertidumbre.
10. No agregues componentes nuevos si no están pedidos en el prompt actual.
11. No hagas “fix silencioso”: explica qué falló y cómo lo corregiste.
12. Antes de cerrar cada prompt, ejecuta tests y linters indicados.
13. La confirmación final debe ser exactamente la pedida.
```

---

## PROMPT 0 — Auditoría de seguridad y limpieza previa

```text
Actúa como ingeniero senior de seguridad aplicada y DevOps.

Objetivo: preparar el repositorio para construir Cognitive OS sin secretos expuestos ni configuración peligrosa.

Tareas:
1. Verifica si el directorio actual está vacío o si ya existe un repo.
2. Busca secretos en todos los archivos existentes usando patrones simples:
   - sk-
   - api_key
   - API_KEY
   - token
   - bearer
   - password=
   - secret
   - claves largas alfanuméricas de más de 32 caracteres
3. Si encuentras secretos:
   - NO repitas el secreto completo.
   - Muestra solo los primeros 4 y últimos 4 caracteres.
   - Crea `SECURITY_ROTATION_REQUIRED.md` con lista de archivos afectados.
   - Detente y pide al usuario rotar esas credenciales antes de continuar.
4. Crea o actualiza `.gitignore` para excluir:
   - `.env`
   - `.env.*`
   - `!.env.example`
   - `.venv/`
   - `node_modules/`
   - `.mypy_cache/`
   - `.ruff_cache/`
   - `.pytest_cache/`
   - `data/`
   - `models/`
   - `storage/`
   - `*.sqlite`
   - `*.db`
   - `*.pem`
   - `*.key`
5. Agrega `detect-secrets` o `gitleaks` como herramienta de pre-commit. Si no puedes instalarla, deja documentado el comando exacto para instalarla y continúa solo con hooks básicos.
6. Crea `.env.example` SIN claves reales. Solo placeholders `CHANGEME`.
7. Crea `docs/SECURITY.md` con estas reglas:
   - jamás commitear `.env`;
   - rotar claves si aparecen en logs/prompts;
   - no enviar payloads sensibles a servicios externos sin redacción;
   - acciones externas requieren aprobación humana.

Cuando termines, responde exactamente:
"[CONFIRMACIÓN P0]: AUDITORÍA DE SEGURIDAD COMPLETADA. SIN SECRETOS ACTIVOS EN EL REPO. ESPERANDO PROMPT 1."
```

---

## PROMPT 1 — Bootstrap limpio del monorepo

```text
Actúa como ingeniero senior Python/TypeScript.

Objetivo: crear la estructura base del monorepo Cognitive OS, sin implementar lógica todavía.

Tareas:
1. Verifica que el Prompt 0 fue completado. Si existe `SECURITY_ROTATION_REQUIRED.md`, detente.
2. Crea estructura:

cognitive-os/
  backend/
    pyproject.toml
    .python-version
    src/
      cognitive_os/
        __init__.py
        __main__.py
        core/
          __init__.py
        db/
          __init__.py
        memory/
          __init__.py
        ingestion/
          __init__.py
        agents/
          __init__.py
        tools/
          __init__.py
        workers/
          __init__.py
        api/
          __init__.py
    tests/
      __init__.py
      test_smoke.py
  frontend/
    README.md
  infra/
    docker-compose.yml
  scripts/
    README.md
  docs/
    ARCHITECTURE.md
    SECURITY.md
  .env.example
  .gitignore
  .pre-commit-config.yaml
  README.md

3. Configura `backend/pyproject.toml` usando `uv` y Python 3.12.
4. Dependencias base:
   - fastapi>=0.115
   - uvicorn[standard]
   - pydantic>=2
   - pydantic-settings>=2
   - structlog
   - python-dotenv
   - sqlalchemy[asyncio]>=2
   - asyncpg
   - alembic
   - httpx
   - tenacity
5. Dependencias dev:
   - pytest>=8
   - pytest-asyncio
   - pytest-cov
   - ruff
   - mypy
   - pre-commit
   - detect-secrets
6. Configura Ruff:
   - line-length 100
   - target py312
   - reglas: E,F,I,N,UP,B,SIM,RET
7. Configura mypy en modo estricto, pero permite exclusión temporal de migraciones Alembic.
8. Crea `backend/src/cognitive_os/__main__.py` con un arranque mínimo que imprima/loguee "Cognitive OS bootstrap OK".
9. Crea test smoke.
10. Ejecuta:
    - `cd backend && uv sync`
    - `uv run pytest`
    - `uv run ruff check .`
    - `uv run ruff format --check .`
    - `uv run mypy src`

No crees Docker real todavía. El `docker-compose.yml` puede quedar vacío con comentario.

Cuando todo pase, responde exactamente:
"[CONFIRMACIÓN P1]: BOOTSTRAP LIMPIO COMPLETADO. TESTS Y LINTERS OK. ESPERANDO PROMPT 2."
```

---
