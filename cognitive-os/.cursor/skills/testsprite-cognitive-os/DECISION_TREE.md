# Árbol de decisión — TestSprite Cognitive OS

Usar **antes** de invocar cualquier tool MCP o comando shell ad-hoc.

```mermaid
flowchart TD
  A[¿Usuario pide TestSprite / audit Prompt 1?] -->|sí| W{¿Pidió Web Portal / frontend website / Edge?}
  W -->|sí| WEB[STOP MCP — usar testsprite-web-portal-cognitive-os]
  W -->|no| B[¿Leíste SKILL.md + MISTAKES.md?]
  B -->|no| STOP1[STOP — leer ambos]
  B -->|sí| C[¿Vas a usar testsprite_generate_code_and_execute?]
  C -->|sí| D{¿testIds tiene al menos 1 ID explícito?}
  D -->|no / vacío| STOP2[STOP — usar testsprite_audit.sh]
  D -->|sí| E{¿Es plan completo 28 casos?}
  E -->|sí| STOP3[STOP — solo full-testsprite via audit.sh]
  E -->|no, subset ≤3| F[prepare.sh + validate + MCP con production]
  C -->|no| G[¿Comando es bash scripts/testsprite_audit.sh?]
  G -->|no| H{¿Es node generateCodeAndExecute directo?}
  H -->|sí| STOP4[STOP — full-testsprite.sh]
  H -->|no| I{¿Es full-testsprite sin prepare previo?}
  I -->|sí| STOP5[STOP — prepare + validate primero]
  I -->|no| J[Ejecutar y revisar STOP strings]
  G -->|sí| J
  J --> K{¿Smoke warnings=0 y sin Target connect failed?}
  K -->|no| STOP6[STOP — recovery prepare, no full plan]
  K -->|sí| L[Continuar fase siguiente]
```

## Preguntas de 5 segundos (responder en voz alta)

1. ¿El usuario pidió explícitamente Web Portal/frontend de TestSprite? Si sí → usar `testsprite-web-portal-cognitive-os`, no MCP.
2. ¿Mi comando es **`bash scripts/testsprite_audit.sh`**? Si no y es MCP/local → parar.
3. ¿`testIds` está **vacío** en algún JSON MCP? Si sí → parar.
4. ¿Corrí **prepare + validate** en esta sesión? Si no → parar.
5. ¿Hay **URLs** en `additionalInstruction` para MCP? Si sí → parar.
6. ¿Voy a declarar **PASS** sin contar 28 en batched_results o sin reporte portal limpio? Si sí → parar.

## Veredictos permitidos

| Evidencia | Veredicto TestSprite |
|---|---|
| 28/28 PASSED, warnings=0 | PASS |
| Subset OK (ej. TC001 smoke) | PARTIAL (documentar scope) |
| Tunnel bug / sin key / abort | BLOCKED + fallback QA |
| pytest verde pero TestSprite no | PASS producto, BLOCKED TestSprite |
