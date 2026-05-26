# 28 — Web Portal API Results

Fecha: **2026-05-26**  
Fuente QA: **TestSprite Web Portal**  
Proyecto TestSprite: `backend_api`  
Run/TestSprite URL: `https://www.testsprite.com/dashboard/tests/36b5b87d-b80b-4d67-90c7-50fdbb131f51/report`  
Estado: **PARTIAL / FAIL API CONTRACT**

## Resultado bruto

| Métrica | Valor |
|---|---:|
| APIs probadas | 38 |
| Features | 16 |
| Test cases | 158 |
| Passed | 111 |
| Failed | 22 |
| Blocked | 25 |

Nota: el texto narrativo del portal menciona 27 blocked, pero el gráfico y el contador de issues muestran **25 blocked**. Se toma 111 + 22 + 25 = 158 como conteo consistente.

## Bugs reales probables

| ID | Evidencia TestSprite | Clasificación |
|---|---|---|
| `WEB-API-001` | `GET /actions`, `/actions/{id}/dispatch`, `/actions/{id}/preview`, `/actions/{id}/request`, `/actions/{id}/validate` devuelven 404 o quedan blocked por no poder obtener `action_id` | **Real / contract drift probable**: namespace documentado no expuesto en público |
| `WEB-API-002` | `/research` devuelve 404 para lectura y guards | **Real / contract drift probable** |
| `WEB-API-003` | `/config` devuelve 404 para snapshot y auth guards | **Real / contract drift probable** |
| `WEB-API-004` | `/assist` devuelve 404 | **Real / contract drift probable** |
| `WEB-API-005` | `/voice` devuelve 404 | **Real / contract drift probable** |
| `WEB-API-006` | `/deepagents` devuelve 404 | **Real / contract drift probable** |
| `WEB-API-007` | `/knowledge` devuelve 404 | **Real / contract drift probable** |
| `WEB-API-008` | `/document-analysis` devuelve 404 | **Real / contract drift probable** |
| `WEB-API-009` | `/sandbox` devuelve 404 para status/invalid-token guard | **Real / contract drift probable** |
| `WEB-API-010` | `/langsmith` devuelve 404 para invalid-token guard | **Real / contract drift probable** |
| `WEB-API-011` | `POST /health/verify` acepta `{}` y devuelve health report completo | **Real API validation bug probable** |
| `WEB-API-012` | `GET /threads/00000000-0000-0000-0000-000000000000` devuelve 200 con error payload | **Real API status semantics bug probable** |

## No contar aún como bug real

| Evidencia TestSprite | Motivo |
|---|---|
| `/system/credentials-status`, `/system/mcp`, `/health/dashboard` devuelven 200 en tests de insufficient role/expired token | El credential aplicado globalmente era un JWT fresco con rol `admin`; TestSprite no demostró que haya usado token no-admin o expirado. Requiere rerun focal con credenciales negativas reales. |
| Casos blocked que requieren `action_id` | TestSprite no pudo construir precondición sin ruta de catálogo/fixture. Esto queda blocked hasta exponer un fixture seguro o seleccionar solo guard tests sin side effects. |
| `Open an existing document` | El reporte solo indica mismatch y muestra lista de documentos. Requiere inspección focal para saber si es expectativa incorrecta, bug de schema, o posible exposición no deseada de `source_path`. |

## Áreas sanas observadas

El resumen de TestSprite marca como sanas varias superficies ejecutables: `jobs`, `mail`, `chat`, `approvals`, `audit`, `health/readiness`, `/docs`, `/redoc` y `/openapi.json`.

## Próximo paso recomendado

1. Triar router/deployment drift de los namespaces documentados que devuelven 404.
2. Corregir validación de `POST /health/verify`.
3. Corregir semántica de `GET /threads/{thread_id}` para recursos inexistentes.
4. Preparar rerun focal TestSprite para:
   - rutas 404 corregidas;
   - `health/verify`;
   - nonexistent thread;
   - auth negative real con token no-admin, token inválido y token expirado.

## Veredicto

No hay PASS TestSprite. La corrida web sí desbloqueó cobertura API pública frente al bloqueo del MCP, pero deja **22 failed** y **25 blocked**. El estado correcto es **PARTIAL / FAIL API CONTRACT**, pendiente de reparación y rerun focal.
