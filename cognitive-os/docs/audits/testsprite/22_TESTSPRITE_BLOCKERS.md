# 22 - TestSprite Blockers

Fecha UTC: 2026-05-24

## Blockers de release

Ninguno.

## Incidencias no bloqueantes

| ID | Descripcion | Evidencia | Workaround | Impacto release |
|---|---|---|---|---|
| NB-001 | TestSprite frontend remoto devolvio 500 al ejecutar multi-ID. | Primer batch frontend `TC005,TC007,TC017,TC034` fallo antes de navegador con `Backend error: 500`. | Ejecutar UI/E2E como singles TestSprite. | No bloquea; Final A/B singles pasaron. |
| NB-002 | Runner frontend TestSprite queda vivo hasta 1 hora tras completar. | Logs `Server will remain active for 1 hour`. | Terminar proceso despues de preservar artifacts. | No bloquea. |
| NB-003 | TestSprite puede regenerar casos API peligrosos si el prompt menciona endpoints prohibidos. | `TCAPI006` ejecuto POST mail pese a instrucciones. | Usar casos GET-only `TCAPI015`/`TCAPI016`. | No bloquea; evita side effects. |
| NB-004 | IDs frontend `TC034`/`TC035` devolvieron 500 remoto antes de ejecucion. | Reintentos single-ID fallaron antes de browser; replacements `TC037`/`TC038` ejecutaron y pasaron. | Mantener `TC037`/`TC038` como cobertura canonica equivalente. | No bloquea; cobertura final PASS. |

No se uso BLOCKED para ocultar bugs reales.
