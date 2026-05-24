# 05 Zero-Friction Repair Plan

Plan de reparacion de esta pasada. Se ejecuta sin confirmacion adicional porque
los cambios son hermeticos, locales y alineados con el contrato
`dedicated_local/full`.

## Hallazgos accionables

| ID | Severidad | Evidencia | Causa raiz probable | Test que debe fallar | Reparacion propuesta | Archivos a tocar | Riesgo de regresion | Comando de validacion | Criterio de aceptacion |
|---|---|---|---|---|---|---|---|---|---|
| R-001 | P1 | `full-qa-live.sh` tenia `export LIVE_TESTS_ENABLED=1` | el script asumio consentimiento por estar en carril live | nuevo test estatico de script | exigir env externo; mensaje claro; exit 2 sin tocar pytest | `scripts/full-qa-live.sh`, `test_frontend_static_assets.py`, docs QA | bajo | `bash scripts/full-qa-live.sh` sin env; pytest puntual | sin env no contacta proveedores; con env conserva comando pytest |
| R-002 | P1 | `full-e2e.sh` usaba `create_access_token` | bypass local para comodidad del runner | test estatico que prohibe mint directo | quitar mint; documentar `_global-setup.ts` como dueño del token | `scripts/full-e2e.sh`, tests, scripts docs | medio: si global setup falla, E2E debe fallar | pytest puntual; Playwright cuando stack este vivo | E2E prueba `/auth/local-token` en vez de saltarlo |
| R-003 | P2 | USER_GUIDE prometia "tema claro/oscuro" | doc stale | test docs/frontend dark-only | corregir texto a dark-only | `docs/USER_GUIDE.md`, test estatico | bajo | pytest puntual | docs no prometen toggle |
| R-004 | P2 | guias con 944/+3/484 viejos | drift posterior a gates | sync/check y grep | actualizar conteos secundarios | `COGNITIVE_OS_GUIDE.md`, `AGENT_LEARNING_PLAN.md`, `scripts/README.md` | bajo | `sync_doc_counts --check`, grep | no quedan conteos contradictorios en guias tocadas |

## Orden de ejecucion

1. Registrar alcance, matriz, inventario, gaps y failure log.
2. Aplicar fixes R-001 a R-004.
3. Correr tests estaticos puntuales.
4. Verificar guard live sin `LIVE_TESTS_ENABLED=1`.
5. Correr `git diff --check` y `sync_doc_counts --check`.
6. Ejecutar gates de area factibles: ruff/format si se tocan tests Python.
7. Actualizar `06_IMPLEMENTATION_LOG.md`, `07_TESTSPRITE_AND_PLAYWRIGHT_PLAN.md`
   y `08_FINAL_COMMERCIAL_REPORT.md` con resultados reales.

## Stop conditions

No cerrar como PASS si:

- `full-qa-live.sh` sigue auto-habilitando live;
- `full-e2e.sh` vuelve a mintar JWT directo;
- USER_GUIDE vuelve a prometer toggle claro;
- tests puntuales fallan;
- se detecta P0/P1 nuevo durante validacion.
