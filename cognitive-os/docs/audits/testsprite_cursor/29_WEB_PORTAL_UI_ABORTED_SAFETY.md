# 29 — Web Portal UI Aborted For Safety

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha: **2026-05-26**  
Fuente QA: **TestSprite Web Portal**  
Proyecto TestSprite abortado: `cognitive_os_ui_spa_full`  
URL abortada: `https://www.testsprite.com/dashboard/tests/5b552b41-06bc-449a-bbe7-57321d9084a9`  
Estado: **ABORTED_FOR_SAFETY / BLOCKED**

## Qué ocurrió

Se creó una suite UI desde el portal usando:

- PRD/Product Description: `COGNITIVE_OS_TESTSPRITE_FULL_UPLOAD.md`
- Test type: `Frontend (URLs)`
- Website URL: `https://cognitive.doctormanzur.com/`
- Test account: vacío
- Instrucciones: SPA root only, seed `localStorage` via `POST /auth/local-token`, no rutas internas directas, no acciones destructivas.

La exploración inicial completó `10/10 features` y produjo evidencia útil:

- sidebar navigation: succeeded;
- hotkeys `1`, `3`, `9`: succeeded;
- `Ctrl+K` command palette navigation: succeeded;
- responsive: skipped por presupuesto de pasos;
- TopBar/global status observado como `degraded`, aunque la app se mantuvo operativa tras reload.

## Motivo del aborto

Antes de generar, se detectaron casos mutantes/peligrosos y se intentó reescribirlos como guard-only/read-only. Sin embargo, al pulsar **Generate Tests**, el portal creó una corrida de 47 tests que conservaba títulos peligrosos en ejecución, incluyendo:

- `Code Director: Create a code plan and review its budget`
- `Research: Start a research run`
- `Research: Cancel a research run`
- `Documents and Document Analysis: Run a document analysis mode`
- `Documents and Document Analysis: Start document ingestion from Documents`
- `Action Plane: Dispatch a dry-run action`

Dado que el contrato TestSprite prohíbe side effects reales, se usó **Delete Creation** y se confirmó el borrado para detener el run.

## Clasificación

| ID | Evidencia | Clasificación |
|---|---|---|
| `WEB-UI-ABORT-001` | 47 UI tests comenzaron con títulos que podían ejecutar mutaciones reales | **BLOCKED / ABORTED_FOR_SAFETY** |
| `WEB-UI-EXPLORE-001` | Navegación sidebar/hotkeys/Ctrl+K succeeded durante exploración | **Evidencia parcial positiva** |
| `WEB-UI-EXPLORE-002` | Global status observado como `degraded` | **Requiere triage focal**; no PASS verde |

## Próximo intento seguro

Reiniciar UI como suite mínima read-only, con casos acotados:

1. Bootstrap + localStorage seed + no localhost.
2. Sidebar navigation.
3. Hotkeys.
4. Command palette.
5. Responsive.
6. Health view read-only.
7. Dashboard read-only.
8. Mail read-only guard.
9. Documents list/detail read-only.
10. Audit read-only.

Excluir desde el plan cualquier caso con:

- create;
- approve/reject;
- cancel;
- dispatch;
- start run;
- submit ingestion;
- upload;
- send/draft/sync.

## Veredicto

No hay PASS UI. La corrida se abortó correctamente por seguridad antes de aceptar un plan potencialmente mutante.
