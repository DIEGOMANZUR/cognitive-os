# 21 - TestSprite False Positives

Fecha UTC: 2026-05-24

| ID | Evidencia | PRD que lo justifica | Ajuste aplicado |
|---|---|---|---|
| FP-API-001 | `TCAPI007` fallo al ver `/mail/sync` y `/mail/messages/{id}/ignore` documentados. | `PRD.md` exige no send/no draft; docs canonicos permiten sync/digest read-side. | Se agrego `TCAPI015` GET-only para flags runtime de mail. |
| FP-API-002 | `TCAPI006` ejecuto `/mail/sync/dispatch` pese a instruccion de no POST mail. | Prompt/PRD prohiben writes reales y TestSprite no debe ejecutar sync/digest dispatch en esta auditoria. | Se agrego `TCAPI016` GET-only guard catalog. |
| FP-API-003 | `TCAPI011` fallo por 405 en `POST /code-director/runs`. | 405 en metodo/ruta no soportada es guard seguro, no 5xx ni false success. | Caso ajustado a read-only/status/OpenAPI; rerun PASS. |
| FP-API-004 | `TCAPI002` marco nombres como `jwt_secret` como secretos. | `PRD_BACKEND.md` prohibe valores secretos; nombres de settings/capacidades no son credenciales. | Caso ajustado a detectar valores secret-shaped; rerun PASS. |
| FP-API-005 | `TCAPI009` esperaba `id` en thread. | Contrato backend usa `thread_id` en `ThreadResponse`. | Caso ajustado; rerun PASS. |
| FP-API-006 | `TCAPI016` marco mail normal como secret-like por longitud. | Mensajes, snippets, remitentes e IDs no son API keys/JWT/OAuth secrets. | Caso ajustado; rerun PASS. |
| FP-RUNNER-001 | Frontend multi-ID devolvio 500 remoto TestSprite. | No hay fallo en runtime publico; singles ejecutaron y pasaron. | Final A/B UI/E2E se ejecuto en singles con artifacts por caso. |
| FP-RUNNER-002 | `TC034` y `TC035` devolvieron 500 remoto TestSprite incluso como single-ID antes de ejecutar browser. | El PRD exige cubrir auth/network hygiene y Action Plane/Google Ops guards, no depender de IDs opacos del runner. | Se agregaron replacements equivalentes `TC037`/`TC038`; ambos pasaron con artifacts. |

No se marco como falso positivo ningun fallo sin evidencia y sin referencia a PRD.
