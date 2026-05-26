# 01 — Runtime Readiness for TestSprite

Fecha: **2026-05-26**  
Tipo: **runtime availability check** (no es suite de calidad)

## Launcher endurecido

Comandos usados (solo preparación):

```bash
/home/jgonz/Escritorio/cognitive-os.sh status   # OK — stack local UP
/home/jgonz/Escritorio/cognitive-os.sh doctor   # OK — preflight dependencies
```

Estado local (referencia operador):

| Componente | Estado |
|---|---|
| Docker | running |
| API local | `http://127.0.0.1:8000/health` UP |
| Frontend local | `http://localhost:3001` UP |
| Worker / beat / telegram / kimi | running |

Documentación launchers: `/home/jgonz/Escritorio/testsprite/cognitive-os-launchers-README.md` (copiada a `testsprite_tests/tmp/prd_files/`).

## URLs públicas objetivo TestSprite

| URL | Check | Resultado |
|---|---|---|
| `https://cognitive.doctormanzur.com/` | HTTP GET | **200** (~0.51s) |
| `https://cognitive-api.doctormanzur.com/health` | HTTP GET | **200** (~0.36s) |
| `https://cognitive-api.doctormanzur.com/openapi.json` | HTTP GET | **200** (~190 KB) |

## CORS / preflight (availability)

```http
OPTIONS /system/info
Origin: https://cognitive.doctormanzur.com
Access-Control-Request-Method: GET
```

Respuesta observada:

- `access-control-allow-origin: https://cognitive.doctormanzur.com`
- `access-control-allow-credentials: true`
- HTTP **200**

## Auth runtime check (availability)

Con JWT preparado (ver doc 02):

- `GET /system/info` + Bearer → **200**
- `GET /system/info` sin auth → **401**

Esto confirma guards auth en API pública — **no** implica PASS de auditoría.

## UI pública vs localhost

| Pregunta | Estado |
|---|---|
| ¿UI pública carga? | **Sí** (200 HTML) |
| ¿Backend público responde? | **Sí** |
| ¿OpenAPI existe? | **Sí** |
| ¿UI debe usar API pública? | **Sí** — seed `cogos.api=https://cognitive-api.doctormanzur.com` |
| ¿Placeholder local en UI? | **Esperado** — `PRD_FRONTEND.md` §7: placeholder `127.0.0.1:8000` no es bug tras seed |

**Gap a validar en Megaprompt 2:** inspección Network en browser TestSprite para confirmar **cero fetch a `localhost:*`** desde origen público tras seed.

## Mixed content

Origen UI y API son HTTPS → no se observó mixed-content en checks HEAD/OPTIONS. Validación completa queda para ejecución TestSprite (consola del browser).

## Veredicto runtime

| Item | Listo |
|---|---|
| Stack local operador | Sí |
| Stack público TestSprite | **Sí** |
| OpenAPI público | **Sí** |
| CORS frontend→API | **Sí** (preflight OK) |
| JWT funcional en API pública | **Sí** |

**Conclusión:** runtime mínimo **READY** para preparar/ejecutar TestSprite contra despliegue público.
