# Cognitive OS Frontend

> **Estado actual (2026-05-20, Fase 74):** Next.js 16.2.6, React 19,
> ESLint 9.39.4, TypeScript 5.8. **20 vistas** en `app/views/*.tsx`:
> `ChatView`, `DashboardView`, `SettingsView`, `ApprovalsView` (con
> import/export `workflow.v1`), `MemoryView`, `JobsView`, `SandboxView`,
> `DocumentsView`, `DocumentAnalysisView`, `ConfigurationView`,
> `MailInboxView`, `LangSmithView`, `AgentsView`, `SkillsView`,
> `HealthView`, `AuditView`, `AssistView`, `GoogleOpsView`,
> `ResearchView` (plan animado sobre SSE) y `CodeDirectorView`
> (delegación de builds con aprobación humana + descarga `tar.gz`).
> Componentes: `Sidebar.tsx`, `TopBar.tsx`, `CommandPalette.tsx`,
> `PWA.tsx`, `ErrorBoundary.tsx`.
>
> **Novedades Fase 71-74 en el frontend:**
> - **JWT persistente** en `localStorage` (`useLocalState`, Fase 71-H) —
>   ya no hay que re-pegarlo al recargar.
> - **`SettingsView`** muestra el tile **"Capacidades bloqueadas"**
>   (`/system/readiness`) y el tile **"MCP servers"** (`/system/mcp`).
> - **`ConfigurationView`** invierte la semántica de "danger" según el
>   `operator_profile` (en `dedicated_local`, no tener una capacidad write
>   no es alarma — es capacidad faltante).
> - **`GoogleOpsView`** deshabilita los botones de write cuando
>   `write_enabled=false` y muestra `missing_scopes` con el comando de
>   re-autorización.
> - **`HealthView`** lista metadata como key=value (no JSON crudo); 17
>   componentes incluido `mcp_client`.
> - **`ChatView`** muestra `tg…<sufijo>` para threads de Telegram.
>
> El `ApiClient` normaliza tokens con prefijo `Bearer`, omite
> `Content-Type` en requests sin body y soporta `AbortSignal`. Next.js
> añade headers de seguridad; el service worker mantiene las APIs
> network-only; `PWA.tsx` cubre install/offline/update. Corre en `:3001`
> (`:3000` lo ocupa OpenChamber). QA: `npm run lint` 0 warnings,
> `npm run build` verde.

Consola operativa en Next.js para usar Cognitive OS: chat, documentos, jobs,
aprobaciones, salud, memoria, skills, sandbox, mail personal, Google Ops y estado
del action plane.

## Desarrollo

```bash
npm ci          # reproducible (preferido)
npm run dev     # dev server con Turbopack
npm run lint    # eslint (--max-warnings 0)
npm run build   # build estática para producción
```

Configura `NEXT_PUBLIC_API_BASE_URL` (o ajustes en la UI) si la API no está en
`http://127.0.0.1:8000`. La consola valida JWT antes de pegar a la API.
Por seguridad, el JWT queda en estado de sesión React y no se persiste
automáticamente en `localStorage`; al recargar la página hay que pegarlo de
nuevo o implementar un flujo auth real.
