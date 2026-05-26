# 13 — Guard Results

Fecha: **2026-05-26**  
Suite objetivo: **Forbidden Guards**  
Estado suite: **BLOCKED / NOT RUN**

## Razón de bloqueo

La suite Guard incluye probes negativos sobre endpoints potencialmente sensibles. Aunque el PRD permite verificar bloqueo controlado, el smoke API `TCAPI001` no ejecutó ningún caso en TestSprite (`test_results.json` vacío). Sin una ejecución API válida, correr guards habría sido inseguro para la auditoría:

- No hay garantía de que TestSprite use solo los endpoints permitidos.
- No hay garantía de que use el Bearer JWT correcto.
- No hay garantía de que respete la lista de side effects prohibidos.

## Casos planificados no ejecutados

| ID | Guard | Estado |
|---|---|---|
| `TG001` | Mail send blocked | BLOCKED |
| `TG002` | Mail draft blocked | BLOCKED |
| `TG002b` | Mail sync/digest POST blocked in guard window | BLOCKED |
| `TG003` | DNS write blocked/dry-run | BLOCKED |
| `TG004` | Destructive sandbox blocked | BLOCKED |
| `TG005` | Dangerous tools blocked | BLOCKED |
| `TG006` | Safety flag mutation blocked | BLOCKED |
| `TG007` | Invalid approval handled | BLOCKED |
| `TG008` | Double approve handled | BLOCKED |
| `TG009` | Duplicate submit/idempotency | BLOCKED |
| `TG010` | Forbidden endpoint 4xx not 5xx | BLOCKED |
| `TG011` | UI blocked capability banner | BLOCKED |

## Expected según PRD

Cuando esta suite se ejecute correctamente, los resultados válidos son:

- 400 / 403 / 409 controlado.
- `detail` tipo `feature_disabled`, `dry_run_only`, `forbidden` o equivalente.
- Nunca 5xx.
- Nunca efecto externo real.
- Nunca draft.
- Nunca send.
- Nunca DNS write.

## Artifacts

No TestSprite Guard artifacts fueron generados porque no se ejecutó la suite.

## Decisión

**No ejecutar guards hasta que la configuración API de TestSprite ejecute al menos un smoke público real.**
